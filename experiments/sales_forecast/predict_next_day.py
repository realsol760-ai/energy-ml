"""Load the trained model and forecast next-day units for known products."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from train_model import DATA_PATH, MODEL_FEATURES, MODELS_DIR, RESULTS_DIR, aggregate_daily_sales, load_sales


def main() -> None:
    """Create a next-calendar-day forecast from the latest available sales."""
    model_path = MODELS_DIR / "modelo_ventas.joblib"
    metrics_path = RESULTS_DIR / "metricas_por_producto.csv"
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de datos: {DATA_PATH}")
    if not model_path.exists() or not metrics_path.exists():
        raise FileNotFoundError("Primero ejecuta train_model.py para generar el modelo.")

    sales, _ = load_sales(DATA_PATH)
    daily = aggregate_daily_sales(sales)
    items = pd.read_csv(metrics_path)["item"].astype(str).drop_duplicates().tolist()
    start = daily["date"].min()
    last_date = daily["date"].max()
    next_date = last_date + pd.Timedelta(days=1)
    dates = pd.date_range(start, last_date, freq="D")
    panel = (
        daily.loc[daily["item"].isin(items)]
        .pivot_table(index="date", columns="item", values="sales", aggfunc="sum", fill_value=0)
        .reindex(index=dates, columns=items, fill_value=0)
    )

    rows: list[dict[str, object]] = []
    for item in items:
        values = panel[item].to_numpy(dtype=float)
        if len(values) < 28:
            raise ValueError(f"No hay 28 días de historial para el producto {item}.")
        row: dict[str, object] = {
            "item": item,
            "weekday": str(next_date.dayofweek),
            "month": str(next_date.month),
            "lag_1": values[-1],
            "lag_7": values[-7],
            "lag_14": values[-14],
            "lag_28": values[-28],
            "mean_previous_7_days": values[-7:].mean(),
            "mean_previous_28_days": values[-28:].mean(),
        }
        rows.append(row)

    features = pd.DataFrame(rows)[MODEL_FEATURES]
    model = joblib.load(model_path)
    result = pd.DataFrame({"fecha": next_date, "producto": items, "unidades_predichas": model.predict(features).clip(min=0)})
    output_path = RESULTS_DIR / "prediccion_siguiente_dia.csv"
    result.to_csv(output_path, index=False)
    print(result.to_string(index=False))
    print(f"Archivo generado: {output_path}")


if __name__ == "__main__":
    main()
