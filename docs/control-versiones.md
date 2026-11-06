# Control de versiones del proyecto

## Ramas

- `main`: versión estable y entregable.
- `develop`: integración de cambios que ya pasaron revisión.
- `feat/<nombre>`: rama temporal para una funcionalidad nueva. Para este
  trabajo: `feat/predictor-ventas`.
- `hotfix/<nombre>`: rama temporal creada desde `main` para una corrección
  urgente. Se integra en `main` y también en `develop`.

No se crea una rama `hotfix` vacía: se abre cuando existe una corrección urgente
concreta.

## Flujo de esta funcionalidad

```text
main → develop → feat/predictor-ventas → develop → main
```

1. Crear `develop` desde `main`.
2. Crear `feat/predictor-ventas` desde `develop`.
3. Hacer commits pequeños y descriptivos en la rama de funcionalidad.
4. Abrir una solicitud de integración hacia `develop` y revisar los cambios.
5. Integrar `develop` en `main` cuando la versión esté lista para entregar.

## Comandos habituales

```bash
git switch main
git pull
git switch -c develop
git push -u origin develop
git switch -c feat/predictor-ventas
git add experiments/sales_forecast docs/control-versiones.md
git commit -m "feat: agregar experimento de pronostico de ventas"
git push -u origin feat/predictor-ventas
```

Para una corrección urgente:

```bash
git switch main
git switch -c hotfix/descripcion-corta
```

Luego de corregir y revisar, se integra el `hotfix` en `main` y en `develop`.
