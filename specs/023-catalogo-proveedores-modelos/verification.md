# Verificación — SPEC-023

- Catálogo, credenciales aisladas, fábrica y fallback verificados por la suite automatizada.
- Dependencias instaladas desde `pyproject.toml` en `.venv`.
- No se realizó una llamada facturable real; la prueba de conexión queda bajo acción explícita del administrador.
- Evidencia global: `310 passed`, migraciones y puertas CI aprobadas el 2026-09-12.

## Refinamiento R1 — 2026-09-13

- Catálogo SQLite administrable, migración reversible, proveedores OpenAI-compatible y precios
  opcionales implementados sin sustituir el catálogo estático de respaldo.
- Credenciales cifradas y write-only; los eventos de auditoría solo registran
  `credential_is_set`, nunca el secreto.
- RBAC, validación HTTPS/SSRF, bloqueo optimista y protección del proveedor/modelo activo
  cubiertos por pruebas.
- Migración verificada con `upgrade head → downgrade f747b450b57a → upgrade head`.
- Suite focalizada: `36 passed`; suite global: `401 passed, 2 warnings`.
- Endurecimiento final de auditoría/fallback: `33 passed, 1 warning`.
- Ruff y formato de los 20 archivos Python modificados: aprobados.
- Puertas greenfield: Ruff, formato y mypy aprobados; escáner: `547 archivos revisados`.
- `mypy` sobre el árbol legado `app` conserva errores técnicos preexistentes fuera de la puerta
  greenfield; no se amplió el alcance para refactorizarlos.
