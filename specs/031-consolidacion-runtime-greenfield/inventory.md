# Inventario de consolidacion — SPEC-031

## KEEP

- `src/talentia/`: producto greenfield oficial.
- `migrations_greenfield/` y `alembic_greenfield.ini`: esquema oficial.
- `tests/greenfield/`: regresion oficial.
- `scripts/start_api.ps1`, `start_worker.ps1`, `seed_greenfield.py`,
  `ejecutar_benchmark_greenfield.py`, `verify_pilot.ps1`, backup/restore compatibles.
- `fixtures/`: datos ficticios que sirven a pruebas y demostracion.
- `docs/`, `specs/` y ADR: evidencia historica, con referencias operativas actualizadas.

## MIGRATE

- Dependencias reales de greenfield desde la lista mixta hacia `pyproject.toml` y
  `requirements.txt` minimos.
- `Dockerfile`, CI, README y scripts hacia `talentia.main:app`.
- Comprobaciones de marca hacia `src/talentia`.

## REMOVE

- `app/`, `ats_frontend/`: ATS FastAPI/Streamlit anterior.
- `frontend/`, `backend/`, `agente_postulacion/`, `streamlit_postulacion.py`: PostulaIA.
- `tests/ats/` y pruebas raiz que importan esos paquetes.
- `migrations/`, `alembic.ini`: esquema anterior.
- `scripts/start_lab.ps1`, `seed.py`, `run_demo.py` y scripts exclusivos del legado.
- `.streamlit/`, `requirements-postulacion.txt`, `README_POSTULACION.md`.

## REQUIRES REVIEW

- `data/`, `storage/`, bases y logs locales: no se eliminan; pueden contener datos del usuario y
  estan fuera del cambio versionado.
- `entregables/`, `output/` y utilidades de generacion: conservar hasta confirmar valor historico.
- Ramas remotas: no eliminar hasta comprobar integracion commit por commit.
