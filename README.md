# energy-ml (antes DiabetesAI-ML)

Identificador de cargas energéticas por **NILM** (*Non-Intrusive Load Monitoring*): a partir del consumo total de un transformador, detecta qué equipos se encienden y se apagan, sin medidores por equipo.

Este repositorio empezó como un clasificador de diabetes (Flask + SVC + Supabase). Se fue **transformando de a poco, con commits atómicos**, para que se pueda seguir la evolución en el historial.

## Cómo funciona

1. **Datos:** potencia activa total cada 5 min, en kW, en `data/input/<medidor>.csv` (columnas `instante,potencia_kw`). Son los dos tableros de la planta piloto, anonimizados como `planta_2_a` y `planta_2_b`.
2. **Eventos:** cada salto |ΔP| ≥ `NILM_UMBRAL_KW` entre muestras consecutivas es un encendido (↑) o un apagado (↓).
3. **Cargas:** DBSCAN agrupa los eventos por magnitud. Cada grupo es una carga candidata con su potencia típica.

En la planta piloto (UPP, 11-09 a 03-10-2026), con los valores por defecto aparece una carga ON/OFF de **~92 kW** en *planta_2_a* (412 encendidos y 380 apagados) y otra de **~88 kW** en *planta_2_b*. El análisis completo está en el informe NILM.

## 🎓 Caso de Estudio del Curso "Procesamiento de Aprendizaje Automático"

Este proyecto es un **caso de estudio real** del curso **[Procesamiento de Aprendizaje Automático](https://isftn199.com.ar/cursos/procesamiento-aprendizaje-automatico)** del Instituto Superior de Formación Técnica N° 199 de Tigre (ISFT N° 199).

### Mapeo: Lecciones del curso → Código en energy-ml

| Lección | Concepto | Ubicación en energy-ml |
|---------|----------|------------------------|
| **Cap 4.2** — Primer servidor FastAPI | Servir modelos en endpoints REST | `src/infrastructure/fastapi/routes.py` — endpoint `POST /api/v1/identify-loads` |
| **Cap 5.1** — Matriz de confusión, F1-Score | Evaluar precisión de clustering | `src/application/cargas/metricas.py` — evaluación con sklearn.metrics |
| **Cap 3.1** — Entropía, Gini, árboles de decisión | Decisiones basadas en datos | `src/infrastructure/sklearn/clustering.py` — DBSCAN usa densidad para separar clusters |

### ¿Cómo estudiar este proyecto?

1. **Lee el documento de contexto:** [Caso de Estudio: energy-ml — NILM](docs/conexion-curso-isftn199.md)
2. **Sigue la arquitectura limpia:** Domain → Application (DTOs) → Infrastructure (FastAPI + sklearn) → Adapters (presenters)
3. **Mira el mapeo lección-a-código:** Usa la tabla arriba como guía de navegación
4. **Prueba los endpoints:** `curl -X POST http://localhost:8000/api/v1/identify-loads -F "file=@data/input/planta_2_a.csv"`
5. **Audita con agentes:** Lee el árbol de decisión exportado en JSON

---

## Arquitectura

Sigue la plantilla [`datamaq-automation/spec`](https://github.com/datamaq-automation/spec): FastAPI + Clean Architecture. La especificación está en [`docs/srs-spec-backend-fastapi.md`](docs/srs-spec-backend-fastapi.md).

```
src/domain/cargas/                  Medicion, EventoCarga, Carga · detectar_eventos, resumir_cargas · puertos
src/application/cargas/             IdentificarCargasUseCase + DTOs (mediciones_fuente, identificar_cargas)
src/infrastructure/csv/             CsvMedicionRepository (lee data/input/)
src/infrastructure/ssh/             SshMedicionRepository (descarga del VPS via MySQL+SSH)
src/infrastructure/mediciones_factory   Factoría: elige adaptador por MEDICIONES_SOURCE
src/infrastructure/sklearn/         DbscanAgrupador
src/infrastructure/fastapi/
  - routers/cargas.py               POST /api/v1/identify-loads
  - routers/mediciones.py           GET /api/v1/mediciones/fuente (metadatos)
web/energia.html                    Vista servida en /
src/infrastructure/cli/             entrenar_cargas.py, evaluar_cargas.py, supervisar_cargas.py
```

**Patrón:** Un repositorio abstracto (Protocol), dos adaptadores concretos (CSV local, SSH remoto), factoría con caché.


## Uso

### Servidor FastAPI

**Modo Desarrollo (local, datos en data/input/):**
```bash
./run.sh dev                      # Reload automático, datos locales
./run.sh start dev                # Mismo que arriba (explícito)
./run.sh start                    # Default: modo dev
```

**Modo Producción (remoto, datos del VPS via SSH+MySQL):**
```bash
./run.sh start prod               # Descarga datos desde VPS al startup
```

**Verificar fuente de datos en tiempo real:**
```bash
# En modo dev:
curl http://localhost:8000/api/v1/mediciones/fuente
# {"fuente": "local", "medidores": ["planta_2_a", "planta_2_b"], "ultima_descarga": null}

# En modo prod (después de sync):
curl http://localhost:8000/api/v1/mediciones/fuente
# {"fuente": "ssh", "medidores": [...], "ultima_descarga": {"instante": "2026-10-04T12:30:00", "duracion_segundos": 2.4, "filas_por_medidor": {...}}}
```

**Diferencias dev vs prod:**
| Aspecto | Dev | Prod |
|---------|-----|------|
| Fuente | CSVs en `data/input/` | MySQL en VPS via SSH+Tailscale |
| Startup | ~1s (solo levanta app) | ~3s (descarga datos) |
| Datos | Versionados, pedagógicos | Actualizados, en caché |
| Fallback | N/A | `data/prod-cache/` persiste entre sesiones |
| Fail-fast | No | Sí: valida SSH en startup |

### Entrenamientos y análisis

**Modo desarrollo (local):**
```bash
./run.sh train                    # Todos los medidores, todos los datos
./run.sh train planta_2_a         # Un medidor
./run.sh train planta_2_a --desde 2026-09-15 --hasta 2026-09-22
```

**Modo producción (datos del VPS):**
```bash
./run.sh train prod               # Descarga del VPS, luego entrena
./run.sh train prod planta_2_a    # Medidor específico del VPS
```

**Otros comandos:**
```bash
./run.sh test                     # pytest + Guantelete de Restricciones Arquitectónicas
./run.sh simulate                 # Genera data/input/sintetico.csv con cargas conocidas
./run.sh evaluate                 # Compara NILM vs verdad etiquetada
./run.sh supervise                # Entrena árbol de decisión con verdad etiquetada
./run.sh lint                     # Verifica estilo con ruff
./run.sh format                   # Formatea código con ruff
./run.sh gauntlet                 # Ejecuta 11 reglas de Clean Architecture
```

## Evolución (para seguir commit a commit)

| Commit | Qué cambia | Concepto |
| :--- | :--- | :--- |
| `chore: quitar endpoint OCR` | Se borra código ajeno al dominio | Alcance / YAGNI |
| `chore(spec): scaffolding` | Estructura Clean Architecture + validadores | Convivencia de código viejo y nuevo |
| `docs(srs)` | Especificación del nuevo sistema | Spec-Driven Development |
| `feat(domain)` | Entidades y reglas puras, con tests | Dominio sin dependencias |
| `feat(infra): repositorio SQL` | Lectura de MySQL y conversión W→kW | Puertos y adaptadores |
| `feat(application)` | Caso de uso `IdentificarCargas` | Orquestación y DTOs |
| `feat(infra): DBSCAN` | Clustering detrás de un puerto | ML como detalle de infraestructura |
| `feat(api)` | Endpoint REST | Thin controllers, inyección de dependencias |
| `feat(scripts)` / `feat(web)` | Consola y vista web | Varios mecanismos de entrega |
| `refactor: eliminar diabetes` | Se borra el sistema viejo | Strangler fig: reemplazo gradual |
| `feat(web): static file serving` | CSS y JS fuera del HTML, servidos en `/static` | Separación de responsabilidades en el front |
| `feat(data): datasets anonimizados` | Mediciones de UPP en `data/input/*.csv` y `scripts/entrenar_cargas.py` | Datos versionados, resultados reproducibles |
| `feat(csv)` | `CsvMedicionRepository` y 404 para medidores desconocidos | Un segundo adaptador para el mismo puerto |
| `feat(logging)` | Logs `info`/`warning`/`error` en cada paso; el caso de uso recibe el logger por constructor | Inyección de dependencias (puerto `Bitacora`) |
| `feat(dependencies): remove numpy` | sklearn recibe listas; numpy deja de ser dependencia directa | Un adaptador por capacidad, no por librería |
| `feat(refactor): migrate from MySQL to CSV` | Se borra el repositorio SQL; dominio y caso de uso no cambian | Reemplazar un adaptador sin tocar el núcleo |
| `feat(env)` | Toda la configuración en `config.py`; `.env` solo para secretos | Configuración vs. secretos |

Para ver el código en un punto del historial: `git log --oneline` y `git checkout <hash>`.

**Para clase:** los alumnos trabajan con el [cuaderno de trabajo](docs/cuaderno-alumno.md) (también en `/guia` con la app corriendo), con actividades sin respuestas. La [guía docente](docs/guia-docente.md) tiene el detalle técnico, las respuestas verificadas y una secuencia de clases.

## Experimento adicional: pronóstico de ventas

El [experimento del issue #2](experiments/sales_forecast/README.md) compara una
regla de referencia, regresión lineal y bosque aleatorio para estimar unidades
diarias por producto con datos públicos de UCI. Es un experimento independiente
del identificador NILM: no usa consumo eléctrico ni altera los endpoints de la
API. Los datos brutos no se versionan; el informe, las métricas y el modelo
entrenado están en `experiments/sales_forecast/`.

El flujo de ramas se describe en [Control de versiones](docs/control-versiones.md).
