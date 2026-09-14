# Tareas — SPEC-032

- [x] **T-032-001 — Corregir contratos de despliegue y CI**
  - Cubre: FR-032-001, NFR-032-001, NFR-032-003, AC-032-001
  - Archivos: `Dockerfile`, `.github/workflows/ci.yml`
  - Verificación: prueba de contrato, Ruff y CI
  - Dependencias: ninguna

- [x] **T-032-002 — Incorporar medicion HTTP acotada**
  - Cubre: FR-032-002, FR-032-003, NFR-032-002, SEC-032-001, AC-032-002, AC-032-003
  - Archivos: `scripts/medir_rendimiento_piloto.py`
  - Verificación: pruebas con servidor local y casos de error
  - Dependencias: T-032-001

- [x] **T-032-003 — Agregar regresion y documentacion operativa**
  - Cubre: todos, AC-032-001..003
  - Archivos: `tests/greenfield/test_cierre_operabilidad.py`, README, runbook, estado de cierre
  - Verificación: suite greenfield, Ruff, mypy, escaner y revision de diff
  - Dependencias: T-032-001, T-032-002

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes dentro del alcance tecnico.
- [x] No hay migraciones; la reversion es por commit.
