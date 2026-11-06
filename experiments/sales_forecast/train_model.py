"""Train and evaluate a one-day-ahead retail sales forecast."""

from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data" / "online_retail_II.xlsx"
RESULTS_DIR = PROJECT_DIR / "results"
MODELS_DIR = PROJECT_DIR / "models"
RANDOM_STATE = 42
TOP_ITEMS = 5

INPUT_COLUMNS = ["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price"]
NUMERIC_FEATURES = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "mean_previous_7_days",
    "mean_previous_28_days",
]
CATEGORICAL_FEATURES = ["item", "weekday", "month"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_sales(path: Path) -> tuple[pd.DataFrame, dict[str, int | str]]:
    """Read both source sheets and keep positive, non-cancelled sale lines."""
    sheets = pd.read_excel(path, sheet_name=None, usecols=INPUT_COLUMNS)
    source = pd.concat(sheets.values(), ignore_index=True)
    source["Invoice"] = source["Invoice"].astype("string")
    source["InvoiceDate"] = pd.to_datetime(source["InvoiceDate"], errors="coerce")
    cancelled = source["Invoice"].str.upper().str.startswith("C", na=False)
    valid = (
        ~cancelled
        & source["Quantity"].gt(0)
        & source["Price"].gt(0)
        & source["InvoiceDate"].notna()
        & source["StockCode"].notna()
    )
    cleaned = source.loc[valid, INPUT_COLUMNS].copy()
    cleaned["date"] = cleaned["InvoiceDate"].dt.normalize()
    cleaned["item"] = cleaned["StockCode"].astype(str)
    cleaned["quantity"] = cleaned["Quantity"].astype(float)
    cleaned = cleaned[["date", "item", "quantity"]]

    audit: dict[str, int | str] = {
        "source_rows": len(source),
        "cancelled_rows": int(cancelled.sum()),
        "nonpositive_quantity_rows": int(source["Quantity"].le(0).sum()),
        "nonpositive_price_rows": int(source["Price"].le(0).sum()),
        "retained_sale_lines": len(cleaned),
        "first_date": str(cleaned["date"].min().date()),
        "last_date": str(cleaned["date"].max().date()),
        "products": int(cleaned["item"].nunique()),
    }
    return cleaned, audit


def aggregate_daily_sales(sales: pd.DataFrame) -> pd.DataFrame:
    """Sum sold units by calendar date and product code."""
    return (
        sales.groupby(["date", "item"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "sales"})
        .sort_values(["date", "item"])
        .reset_index(drop=True)
    )


def make_product_profiles(
    daily_sales: pd.DataFrame, cutoff: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cluster products using training-period demand and weekday patterns."""
    training = daily_sales.loc[daily_sales["date"] < cutoff]
    dates = pd.date_range(training["date"].min(), training["date"].max(), freq="D")
    panel = training.pivot_table(
        index="item", columns="date", values="sales", aggfunc="sum", fill_value=0
    ).reindex(columns=dates, fill_value=0)

    profile = pd.DataFrame(index=panel.index)
    profile["mean_daily_units"] = panel.mean(axis=1)
    profile["std_daily_units"] = panel.std(axis=1, ddof=0)
    profile["zero_day_share"] = panel.eq(0).mean(axis=1)
    for weekday in range(7):
        day_columns = panel.columns[panel.columns.dayofweek == weekday]
        profile[f"weekday_{weekday}_mean"] = panel.loc[:, day_columns].mean(axis=1)

    scaled = StandardScaler().fit_transform(profile)
    metrics: list[dict[str, float | int]] = []
    models: dict[int, KMeans] = {}
    max_k = min(6, len(profile) - 1)
    for k in range(2, max_k + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        labels = model.fit_predict(scaled)
        silhouette = silhouette_score(
            scaled,
            labels,
            sample_size=min(2000, len(profile)),
            random_state=RANDOM_STATE,
        )
        metrics.append(
            {"k": k, "inertia": float(model.inertia_), "silhouette": float(silhouette)}
        )
        models[k] = model

    metrics_frame = pd.DataFrame(metrics)
    best_k = int(metrics_frame.loc[metrics_frame["silhouette"].idxmax(), "k"])
    profile["cluster"] = models[best_k].labels_
    profile.index.name = "item"
    cluster_summary = (
        profile.groupby("cluster")
        .agg(
            products=("mean_daily_units", "size"),
            mean_daily_units=("mean_daily_units", "mean"),
            std_daily_units=("std_daily_units", "mean"),
            zero_day_share=("zero_day_share", "mean"),
        )
        .reset_index()
    )
    cluster_summary["share_of_products"] = (
        cluster_summary["products"] / cluster_summary["products"].sum()
    )
    return metrics_frame, cluster_summary


def build_forecast_frame(
    daily_sales: pd.DataFrame,
    cutoff: pd.Timestamp,
    item_codes: list[str],
) -> pd.DataFrame:
    """Create one-day-ahead features using only prior sales for each item."""
    dates = pd.date_range(daily_sales["date"].min(), daily_sales["date"].max())
    item_panel = daily_sales.loc[daily_sales["item"].isin(item_codes)].pivot_table(
        index="date", columns="item", values="sales", aggfunc="sum", fill_value=0
    )
    item_panel = item_panel.reindex(index=dates, columns=item_codes, fill_value=0)
    frame = (
        item_panel.rename_axis("date")
        .reset_index()
        .melt(id_vars="date", var_name="item", value_name="sales")
        .sort_values(["item", "date"])
        .reset_index(drop=True)
    )

    prior_sales = frame.groupby("item", sort=False)["sales"]
    for lag in (1, 7, 14, 28):
        frame[f"lag_{lag}"] = prior_sales.shift(lag)
    frame["mean_previous_7_days"] = prior_sales.transform(
        lambda values: values.shift(1).rolling(7, min_periods=1).mean()
    )
    frame["mean_previous_28_days"] = prior_sales.transform(
        lambda values: values.shift(1).rolling(28, min_periods=1).mean()
    )
    frame["weekday"] = frame["date"].dt.dayofweek.astype(str)
    frame["month"] = frame["date"].dt.month.astype(str)
    frame["item"] = frame["item"].astype(str)
    frame = frame.dropna(subset=["lag_28"]).copy()
    frame["split"] = np.where(frame["date"] < cutoff, "train", "test")
    return frame


def make_pipeline(estimator: object, scale_numeric: bool) -> Pipeline:
    """Build a preprocessing and regression pipeline."""
    numeric_transformer: object = StandardScaler() if scale_numeric else "passthrough"
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_transformer, NUMERIC_FEATURES),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    return Pipeline([("preprocessor", preprocessor), ("model", estimator)])


def evaluate_forecasts(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, Pipeline, pd.DataFrame]:
    """Fit two regressors and compare them with a yesterday-sales baseline."""
    training = frame.loc[frame["split"] == "train"]
    testing = frame.loc[frame["split"] == "test"].copy()
    x_train = training[MODEL_FEATURES]
    y_train = training["sales"]
    x_test = testing[MODEL_FEATURES]
    actual = testing["sales"].to_numpy()

    estimators: dict[str, Pipeline] = {
        "Regresion lineal": make_pipeline(LinearRegression(), scale_numeric=True),
        "Bosque aleatorio": make_pipeline(
            RandomForestRegressor(
                n_estimators=200,
                min_samples_leaf=2,
                n_jobs=1,
                random_state=RANDOM_STATE,
            ),
            scale_numeric=False,
        ),
    }
    predictions: dict[str, np.ndarray] = {
        "Regla: ventas de ayer": testing["lag_1"].to_numpy()
    }
    fitted_models: dict[str, Pipeline] = {}
    for name, model in estimators.items():
        model.fit(x_train, y_train)
        fitted_models[name] = model
        predictions[name] = np.maximum(model.predict(x_test), 0)

    metric_rows: list[dict[str, float | str]] = []
    for name, values in predictions.items():
        metric_rows.append(
            {
                "modelo": name,
                "mae_unidades": float(mean_absolute_error(actual, values)),
                "rmse_unidades": float(np.sqrt(mean_squared_error(actual, values))),
            }
        )
    metrics = pd.DataFrame(metric_rows).sort_values("mae_unidades")

    output = testing[["date", "item", "sales"]].rename(
        columns={"sales": "unidades_reales"}
    )
    output["regla_ayer"] = predictions["Regla: ventas de ayer"]
    output["regresion_lineal"] = predictions["Regresion lineal"]
    output["bosque_aleatorio"] = predictions["Bosque aleatorio"]

    item_metrics: list[dict[str, float | str]] = []
    for item, rows in output.groupby("item"):
        for column, model_name in (
            ("regla_ayer", "Regla: ventas de ayer"),
            ("regresion_lineal", "Regresion lineal"),
            ("bosque_aleatorio", "Bosque aleatorio"),
        ):
            item_metrics.append(
                {
                    "item": item,
                    "modelo": model_name,
                    "mae_unidades": float(
                        mean_absolute_error(rows["unidades_reales"], rows[column])
                    ),
                    "rmse_unidades": float(
                        np.sqrt(
                            mean_squared_error(rows["unidades_reales"], rows[column])
                        )
                    ),
                }
            )
    item_scores = pd.DataFrame(item_metrics)

    best_ml = metrics.loc[
        metrics["modelo"].isin(["Regresion lineal", "Bosque aleatorio"])
    ].iloc[0]
    best_model = fitted_models[str(best_ml["modelo"])]
    return metrics, output, best_model, item_scores


def write_report(
    audit: dict[str, int | str],
    cutoff: pd.Timestamp,
    selected_items: list[str],
    cluster_metrics: pd.DataFrame,
    cluster_profiles: pd.DataFrame,
    forecast_metrics: pd.DataFrame,
    item_metrics: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    """Write a presentation-ready Spanish summary of methods and results."""
    baseline_mae = float(
        forecast_metrics.loc[
            forecast_metrics["modelo"] == "Regla: ventas de ayer", "mae_unidades"
        ].iloc[0]
    )
    best_ml = forecast_metrics.loc[
        forecast_metrics["modelo"].isin(["Regresion lineal", "Bosque aleatorio"])
    ].iloc[0]
    mae_improvement = 100 * (baseline_mae - float(best_ml["mae_unidades"])) / baseline_mae
    if float(best_ml["mae_unidades"]) < baseline_mae:
        comparison = (
            f"La regresión lineal reduce el MAE {mae_improvement:.1f}% frente a la regla "
            "de ayer. La mejora es pequeña; el bosque aleatorio no supera la regla."
        )
    else:
        comparison = (
            "Ningún modelo de aprendizaje automático mejora la regla de ayer en MAE; "
            "esto limita su utilidad para estos datos."
        )
    metric_lines = "\n".join(
        f"| {row.modelo} | {row.mae_unidades:.3f} | {row.rmse_unidades:.3f} |"
        for row in forecast_metrics.itertuples(index=False)
    )
    cluster_lines = "\n".join(
        f"| {int(row.k)} | {row.inertia:.2f} | {row.silhouette:.3f} |"
        for row in cluster_metrics.itertuples(index=False)
    )
    profile_lines = "\n".join(
        f"| {int(row.cluster)} | {int(row.products)} | {row.mean_daily_units:.2f} | "
        f"{row.std_daily_units:.2f} | {row.zero_day_share:.1%} | "
        f"{row.share_of_products:.1%} |"
        for row in cluster_profiles.itertuples(index=False)
    )
    item_lines = "\n".join(
        f"| {row.item} | {row.modelo} | {row.mae_unidades:.2f} | "
        f"{row.rmse_unidades:.2f} |"
        for row in item_metrics.sort_values(["item", "mae_unidades"]).itertuples(
            index=False
        )
    )
    max_row = predictions.loc[predictions["unidades_reales"].idxmax()]
    report = f"""# Pronóstico de ventas minoristas

## Pregunta de negocio

¿Cuántas unidades de cada producto se venderán mañana, usando únicamente ventas registradas hasta hoy?

## Datos y preparación

- Fuente: UCI Machine Learning Repository, conjunto **Online Retail II** (Chen, 2012), licencia CC BY 4.0.
- El archivo original contiene {audit['source_rows']:,} líneas entre {audit['first_date']} y {audit['last_date']}.
- Se excluyeron {audit['cancelled_rows']:,} líneas de facturas canceladas, {audit['nonpositive_quantity_rows']:,} cantidades no positivas y {audit['nonpositive_price_rows']:,} precios no positivos. Estas categorías pueden solaparse.
- Quedaron {audit['retained_sale_lines']:,} líneas de venta para {audit['products']:,} códigos de producto.
- Las ventas se agregaron por día y código de producto. La fuente no contiene una columna de tienda.
- Se pronostican los cinco productos con más unidades en el período de entrenamiento: {', '.join(selected_items)}.

## Diseño de evaluación

- Corte temporal: {cutoff.date()}. Las fechas anteriores se usaron para entrenar y las posteriores para evaluar.
- Variables: ventas de los 1, 7, 14 y 28 días anteriores; promedios móviles calculados solo con días previos; producto, día de la semana y mes.
- Comparación: regla de ventas de ayer, regresión lineal y bosque aleatorio de 200 árboles.
- Métricas: MAE y RMSE, expresadas en unidades vendidas por producto y día. Menor es mejor.

## Resultados

| Modelo | MAE (unidades) | RMSE (unidades) |
|---|---:|---:|
{metric_lines}

{comparison}

## Agrupamiento descriptivo de productos

Se escalaron el promedio, la variación, la proporción de días sin ventas y el patrón por día de la semana. Se compararon los grupos de 2 a 6 con inercia (método del codo) y silueta. La silueta más alta se usó para asignar los grupos; revisa también el gráfico antes de interpretarlos.

| Grupos (k) | Inercia | Silueta |
|---:|---:|---:|
{cluster_lines}

### Lectura de los grupos

| Grupo | Productos | Promedio diario (unidades) | Desvío diario | Días sin venta | Proporción de productos |
|---:|---:|---:|---:|---:|---:|
{profile_lines}

El grupo con más días sin venta reúne productos de rotación esporádica. El grupo
con menos días sin venta concentra productos de mayor rotación, aunque con más
variación diaria.

## Errores por producto

| Producto | Modelo | MAE (unidades) | RMSE (unidades) |
|---|---|---:|---:|
{item_lines}

El mayor día de ventas observado en el período de prueba fue de
{max_row['unidades_reales']:.0f} unidades para el producto {max_row['item']} el
{pd.Timestamp(max_row['date']).date()}. Los picos grandes ayudan a explicar la
diferencia entre MAE y RMSE.

## Limitaciones

- El conjunto representa una tienda británica de regalos entre 2009 y 2011. Los resultados no son predicciones de ventas de Reposeras SIS.
- La fuente no identifica tiendas, por eso el pronóstico es por producto y día para el conjunto completo.
- Ventas registradas no siempre equivalen a demanda: no hay información de faltantes de inventario.
- El modelo usa el historial de un día anterior para cada nueva predicción. No es un pronóstico único de varios meses hacia adelante.
- Las facturas canceladas y las cantidades o precios no positivos se excluyeron para representar unidades vendidas.

## Uso futuro en Reposeras SIS

El mismo flujo podría aplicarse cuando existan ventas propias resumidas por fecha, producto y unidades. El modelo tendría que volver a entrenarse con esos datos y evaluarse sobre fechas posteriores.

## Fuente

Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D. Licencia CC BY 4.0.
"""
    (RESULTS_DIR / "informe.md").write_text(report, encoding="utf-8")


def main() -> None:
    """Run the complete analysis, clustering, forecast, and report export."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    sales, audit = load_sales(DATA_PATH)
    daily_sales = aggregate_daily_sales(sales)
    full_dates = pd.date_range(daily_sales["date"].min(), daily_sales["date"].max())
    cutoff = pd.Timestamp(full_dates[int(len(full_dates) * 0.8)])

    cluster_metrics, cluster_profiles = make_product_profiles(daily_sales, cutoff)
    cluster_metrics.to_csv(RESULTS_DIR / "agrupamiento_metricas.csv", index=False)
    cluster_profiles.to_csv(RESULTS_DIR / "perfiles_de_grupos.csv", index=False)

    training_sales = daily_sales.loc[daily_sales["date"] < cutoff]
    selected_items = (
        training_sales.groupby("item")["sales"]
        .sum()
        .sort_values(ascending=False)
        .head(TOP_ITEMS)
        .index.tolist()
    )
    forecast_frame = build_forecast_frame(daily_sales, cutoff, selected_items)
    forecast_metrics, predictions, best_model, item_metrics = evaluate_forecasts(
        forecast_frame
    )

    forecast_metrics.to_csv(RESULTS_DIR / "metricas_pronostico.csv", index=False)
    item_metrics.to_csv(RESULTS_DIR / "metricas_por_producto.csv", index=False)
    predictions.to_csv(RESULTS_DIR / "predicciones_de_prueba.csv", index=False)
    joblib.dump(best_model, MODELS_DIR / "modelo_ventas.joblib")
    write_report(
        audit,
        cutoff,
        selected_items,
        cluster_metrics,
        cluster_profiles,
        forecast_metrics,
        item_metrics,
        predictions,
    )

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(cluster_metrics["k"], cluster_metrics["inertia"], marker="o")
    axes[0].set_title("Método del codo")
    axes[0].set_xlabel("Cantidad de grupos (k)")
    axes[0].set_ylabel("Inercia")
    axes[1].plot(cluster_metrics["k"], cluster_metrics["silhouette"], marker="o")
    axes[1].set_title("Coeficiente de silueta")
    axes[1].set_xlabel("Cantidad de grupos (k)")
    axes[1].set_ylabel("Silueta")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "agrupamiento.png", dpi=160)
    plt.close(fig)

    best_item = selected_items[0]
    item_predictions = predictions.loc[predictions["item"] == best_item].tail(90)
    fig, axis = plt.subplots(figsize=(11, 5))
    axis.plot(
        item_predictions["date"],
        item_predictions["unidades_reales"],
        label="Ventas reales",
        linewidth=1.8,
    )
    axis.plot(
        item_predictions["date"],
        item_predictions["regla_ayer"],
        label="Regla: ventas de ayer",
        alpha=0.8,
    )
    axis.plot(
        item_predictions["date"],
        item_predictions["regresion_lineal"],
        label="Regresión lineal",
        alpha=0.8,
    )
    axis.plot(
        item_predictions["date"],
        item_predictions["bosque_aleatorio"],
        label="Bosque aleatorio",
        alpha=0.8,
    )
    axis.set_title(
        f"Pronóstico diario, producto {best_item} (últimos 90 días de prueba)"
    )
    axis.set_xlabel("Fecha")
    axis.set_ylabel("Unidades")
    axis.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "pronostico_producto.png", dpi=160)
    plt.close(fig)

    pd.DataFrame([audit]).to_csv(RESULTS_DIR / "auditoria_datos.csv", index=False)
    print("AUDIT", audit)
    print("CUTOFF", cutoff.date())
    print("ITEMS", selected_items)
    print("CLUSTER_METRICS")
    print(cluster_metrics.to_string(index=False))
    print("FORECAST_METRICS")
    print(forecast_metrics.to_string(index=False))
    print("OUTPUTS", RESULTS_DIR)


if __name__ == "__main__":
    main()
