# Plan — SPEC-031

## Resumen tecnico

Eliminar los consumidores heredados solo despues de comprobar que `src/talentia` es independiente;
reducir configuracion y CI al paquete greenfield y verificar desde migracion vacia.

## Arquitectura y limites afectados

- Empaquetado, dependencias, Docker, CI, scripts y documentacion de operacion.
- No cambia dominio, API ni esquema greenfield.

## Flujo de datos

Navegador -> FastAPI/Jinja2/HTMX -> ServicioTalentIA -> UoW SQLAlchemy -> SQLite WAL.

## Decisiones y alternativas

- Se conserva un monolito modular; se descartan microservicios y React.
- Las specs y ADR heredadas permanecen como historial, claramente rotulado.
- MLflow no sera dependencia del piloto; su adaptador greenfield sera opcional de desarrollo.

## Compatibilidad, transicion y reversion

- Tag: `backup/greenfield-before-consolidation-20260914`.
- Reversion: crear una rama desde el tag, sin reset destructivo.
- No se borran ramas remotas ni datos locales.

## Seguridad, privacidad y fallos

- `.env`, bases y storage no se tocan.
- Docker inicia solo el servidor local oficial.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-001 | automatizada | `tests/greenfield/test_api.py` y smoke import |
| AC-002 | automatizada | `scripts/check_repository.py` y `rg` |
| AC-003 | automatizada | `pip check` y metadatos |
| AC-004 | automatizada | Alembic, pytest, Ruff, format y mypy |

## Riesgos y mitigaciones

- Dependencia util solo presente en legacy: inventario y suite antes/despues.
- Documentacion contradictoria: busqueda global de comandos antiguos.

## Aprobacion

- [x] Plan aprobado por la persona responsable mediante el encargo del 2026-09-14.

## Refinamiento CI reproducible aprobado — 2026-09-14

- Mantener rangos compatibles en `pyproject.toml` para consumidores del paquete.
- Resolver los extras opcionales de verificacion con `constraints-ci.txt` en GitHub Actions.
- Las restricciones de CI no se instalan en el runtime base ni convierten LangGraph, LangSmith o
  MLflow en dependencias del piloto.
- Verificar la misma resolucion en un entorno Python 3.12 limpio y exigir `pip check` antes del
  resto de puertas.
