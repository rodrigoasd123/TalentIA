# Tareas — SPEC-016

- [x] **T-016-001 — Fijar entorno reproducible**
  - Cubre: FR-016-001, FR-016-003, AC-016-001
  - Archivos: `requirements.txt`, `pyproject.toml`, Dockerfile y CI
  - Verificación: instalación CI con Python 3.12 y `pip check`
  - Dependencias: ninguna
- [x] **T-016-002 — Gobernar esquema y fixtures**
  - Cubre: FR-016-004, AC-016-001, AC-016-002
  - Archivos: `alembic.ini`, `migrations/`, `scripts/seed.py`
  - Verificación: `alembic upgrade head` sobre base vacía y seed
  - Dependencias: T-016-001
- [x] **T-016-003 — Documentar ejecución y recuperación**
  - Cubre: FR-016-001, FR-016-003, AC-016-001
  - Archivos: `README.md`, `docs/INSTALACION_WINDOWS.md`
  - Verificación: comandos sin `Activate.ps1`, imports y health
  - Dependencias: T-016-001, T-016-002
- [x] **T-016-004 — Conservar rollback heredado**
  - Cubre: FR-016-002, AC-016-003
  - Archivos: `frontend/streamlit_postulacion.py`, `backend/`, README
  - Verificación: suite heredada y comando de ejecución
  - Dependencias: T-016-001
- [x] **T-016-005 — Aplicar puertas de publicación**
  - Cubre: FR-016-003, AC-016-001–AC-016-003
  - Archivos: `.github/workflows/ci.yml`, `scripts/check_repository.py`
  - Verificación: pytest, Ruff/MyPy focal, migración y scanner
  - Dependencias: T-016-001–T-016-004

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes del laboratorio.
- [x] Existen transición, recuperación y rollback explícitos.
