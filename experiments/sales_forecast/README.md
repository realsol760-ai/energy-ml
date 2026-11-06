# Pronóstico de ventas por producto

Experimento educativo asociado al issue #2 de este repositorio. Predice las
unidades vendidas por producto y día con una separación cronológica de
entrenamiento y evaluación.

## Datos

Se usa **Online Retail II**, del UCI Machine Learning Repository, con licencia
CC BY 4.0. El conjunto registra ventas minoristas de una tienda británica de
regalos entre 2009 y 2011. La fuente no incluye una columna de tienda, por lo
que el modelo pronostica productos para el conjunto completo.

El archivo no se versiona porque supera 10 MB. Descárgalo desde
<https://archive.ics.uci.edu/dataset/502/online%2Bretail> y guárdalo como:

```text
experiments/sales_forecast/data/online_retail_II.xlsx
```

## Preparación y modelos

El programa excluye líneas de facturas canceladas, cantidades no positivas y
precios no positivos; luego agrega unidades por día y código de producto.
Selecciona los cinco productos con más ventas dentro del período de
entrenamiento. La partición es temporal: las fechas anteriores al 15/07/2011 se
usan para entrenar y las fechas posteriores para evaluar.

Compara la regla de ventas del día anterior, una regresión lineal y un bosque
aleatorio. También agrupa perfiles de productos con K-means usando su promedio,
variación, proporción de días sin ventas y patrón por día de la semana.

## Ejecución

Desde la raíz del repositorio:

```powershell
python -m pip install -r experiments/sales_forecast/requirements.txt
python experiments/sales_forecast/train_model.py
python experiments/sales_forecast/predict_next_day.py
```

El primer comando vuelve a entrenar y evaluar los modelos, genera el informe,
las métricas, las predicciones de prueba y los gráficos en `results/`, y guarda
el mejor modelo de aprendizaje automático por MAE en
`models/modelo_ventas.joblib`. El segundo carga ese archivo y predice las
unidades del día siguiente para los cinco productos seleccionados; guarda el
resultado en `results/prediccion_siguiente_dia.csv`. El artefacto incluido fue
entrenado con scikit-learn 1.8.0.

## Resultados de referencia

En la corrida incluida, la regresión lineal obtuvo MAE de 115,83 unidades por
producto y día; la regla de ayer obtuvo 117,59 y el bosque aleatorio 139,51.
La mejora frente a la regla es pequeña y no se repite para todos los productos.
Consulta `results/informe.md` para los resultados por producto y las
limitaciones.

Este modelo es un ejercicio de pronóstico con datos públicos; no estima las
ventas de Reposeras SIS ni el consumo energético de NILM. Para usarlo en SIS
habría que entrenarlo de nuevo con ventas propias.

## Fuente y licencia

Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository.
<https://doi.org/10.24432/C5CG6D>. Licencia CC BY 4.0.
