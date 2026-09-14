# Verificacion — SPEC-031

Fecha: 2026-09-14

Estado: `VERIFICANDO`; pendiente confirmar CI remoto verde para declarar `VERIFICADO`.

## Trazabilidad

| Requisito | Criterio | Tarea | Archivo | Prueba o evidencia |
|---|---|---|---|---|
| FR-001, NFR-001 | AC-001 | T-003, T-004 | `src/talentia/main.py`, README, Dockerfile | import ASGI y suite API |
| FR-002, SEC-002 | AC-002 | T-002, T-003 | `inventory.md`, `docs/sdd/proyecto.md` | busqueda global y escaner |
| FR-003, NFR-001 | AC-003 | T-004 | `pyproject.toml`, `requirements.txt` | instalacion limpia y `pip check` |
| FR-004, NFR-002, NFR-003, SEC-001 | AC-004 | T-001, T-005 | migraciones, CI y tag de respaldo | Alembic y regresion |

## Resultados

- Punto de partida: `f6dfef1221eef9033f6cc035e7726f9e7b9ea666`; contiene el tag de respaldo
  `backup/greenfield-before-consolidation-20260914`.
- CI inicial: fallo en Ruff por 55 hallazgos de formato en `scripts/seed_greenfield.py`.
- Primer CI de verificacion: controles estaticos y migracion aprobaron; 14 pruebas que ejercitan
  LangGraph/MLflow fallaron porque el job no instalaba los extras opcionales. El job de desarrollo
  se ajusto a `.[dev,graph,benchmark]` sin cambiar las dependencias del piloto.
- El script se normalizo; Ruff completo aprobo y 89 archivos cumplen formato.
- La documentacion SDD antigua quedo rotulada como historica y sin comandos ejecutables de
  Streamlit o `app.api.main:app`.
- `langgraph` se movio al extra opcional `graph`; el runtime y Docker no instalan LangGraph,
  LangChain, LangSmith ni MLflow.
- Instalacion limpia Python 3.12 con `pip install -e .`: codigo 0. `pip check`: sin dependencias
  rotas. Smoke: `talentia.main:app` importado con titulo `TalentIA`.
- En el entorno limpio, `find_spec` devolvio `None` para `langgraph`, `langchain_core` y `mlflow`.
- Migracion sobre SQLite vacia: `0001_greenfield -> 0002_esquema -> 0003_workflow`, codigo 0.
- `pytest -q tests/greenfield --basetemp=.pytest-tmp/spec31-final -p no:cacheprovider`:
  81 pruebas aprobadas, 2 advertencias, 89,22 segundos.
- `ruff check`: aprobado. `ruff format --check`: 89 archivos conformes.
- `mypy src/talentia`: 65 archivos sin observaciones.
- `check_repository.py`: 341 archivos revisados; repositorio seguro.
- `check_brand_identity.py`: identidad visible TalentIA verificada.
- Dockerfile y Compose apuntan exclusivamente a `talentia.main:app` y exigen secretos por entorno.
  Docker no esta instalado en esta maquina, por lo que no se ejecuto el build local.

## Advertencias y limites

- Starlette/AnyIO y LangGraph emiten dos deprecaciones en el entorno de desarrollo que conserva el
  extra `graph`; no afectan al runtime limpio. Se revisaran mediante actualizacion controlada.
- SPEC-031 no cierra brechas funcionales de la rubrica; se implementan en specs posteriores.
