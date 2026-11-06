# Pronóstico de ventas minoristas

## Pregunta de negocio

¿Cuántas unidades de cada producto se venderán mañana, usando únicamente ventas registradas hasta hoy?

## Datos y preparación

- Fuente: UCI Machine Learning Repository, conjunto **Online Retail II** (Chen, 2012), licencia CC BY 4.0.
- El archivo original contiene 1,067,371 líneas entre 2009-12-01 y 2011-12-09.
- Se excluyeron 19,494 líneas de facturas canceladas, 22,950 cantidades no positivas y 6,207 precios no positivos. Estas categorías pueden solaparse.
- Quedaron 1,041,670 líneas de venta para 4,917 códigos de producto.
- Las ventas se agregaron por día y código de producto. La fuente no contiene una columna de tienda.
- Se pronostican los cinco productos con más unidades en el período de entrenamiento: 84077, 21212, 85123A, 23166, 85099B.

## Diseño de evaluación

- Corte temporal: 2011-07-15. Las fechas anteriores se usaron para entrenar y las posteriores para evaluar.
- Variables: ventas de los 1, 7, 14 y 28 días anteriores; promedios móviles calculados solo con días previos; producto, día de la semana y mes.
- Comparación: regla de ventas de ayer, regresión lineal y bosque aleatorio de 200 árboles.
- Métricas: MAE y RMSE, expresadas en unidades vendidas por producto y día. Menor es mejor.

## Resultados

| Modelo | MAE (unidades) | RMSE (unidades) |
|---|---:|---:|
| Regresion lineal | 115.833 | 242.760 |
| Regla: ventas de ayer | 117.593 | 313.250 |
| Bosque aleatorio | 139.510 | 281.617 |

La regresión lineal reduce el MAE 1.5% frente a la regla de ayer. La mejora es pequeña; el bosque aleatorio no supera la regla.

## Agrupamiento descriptivo de productos

Se escalaron el promedio, la variación, la proporción de días sin ventas y el patrón por día de la semana. Se compararon los grupos de 2 a 6 con inercia (método del codo) y silueta. La silueta más alta se usó para asignar los grupos; revisa también el gráfico antes de interpretarlos.

| Grupos (k) | Inercia | Silueta |
|---:|---:|---:|
| 2 | 29875.12 | 0.836 |
| 3 | 23082.00 | 0.767 |
| 4 | 19089.13 | 0.734 |
| 5 | 15250.33 | 0.623 |
| 6 | 13120.86 | 0.628 |

### Lectura de los grupos

| Grupo | Productos | Promedio diario (unidades) | Desvío diario | Días sin venta | Proporción de productos |
|---:|---:|---:|---:|---:|---:|
| 0 | 4425 | 1.97 | 10.22 | 86.6% | 96.4% |
| 1 | 165 | 34.23 | 144.19 | 47.0% | 3.6% |

El grupo con más días sin venta reúne productos de rotación esporádica. El grupo
con menos días sin venta concentra productos de mayor rotación, aunque con más
variación diaria.

## Errores por producto

| Producto | Modelo | MAE (unidades) | RMSE (unidades) |
|---|---|---:|---:|
| 21212 | Regresion lineal | 106.52 | 173.02 |
| 21212 | Regla: ventas de ayer | 107.12 | 214.04 |
| 21212 | Bosque aleatorio | 167.12 | 275.96 |
| 23166 | Regla: ventas de ayer | 26.18 | 53.43 |
| 23166 | Bosque aleatorio | 130.33 | 215.48 |
| 23166 | Regresion lineal | 131.06 | 165.29 |
| 84077 | Regresion lineal | 127.57 | 406.55 |
| 84077 | Bosque aleatorio | 152.06 | 445.96 |
| 84077 | Regla: ventas de ayer | 189.47 | 580.52 |
| 85099B | Regresion lineal | 122.39 | 222.11 |
| 85099B | Bosque aleatorio | 131.25 | 214.05 |
| 85099B | Regla: ventas de ayer | 166.86 | 267.22 |
| 85123A | Regresion lineal | 91.63 | 150.97 |
| 85123A | Regla: ventas de ayer | 98.34 | 183.18 |
| 85123A | Bosque aleatorio | 116.80 | 171.04 |

El mayor día de ventas observado en el período de prueba fue de
4848 unidades para el producto 84077 el
2011-10-27. Los picos grandes ayudan a explicar la
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
