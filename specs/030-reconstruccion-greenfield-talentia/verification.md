# Verificacion - SPEC-030

Fecha de verificacion: 2026-09-13.

## Evidencia aprobada

- `pytest -q tests/greenfield`: 22 pruebas aprobadas.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `mypy src/talentia`: 56 archivos sin observaciones.
- Alembic en SQLite desechable: `upgrade head`, `downgrade base`, `upgrade head`; revision final
  persistida `0002_esquema`.
- `python scripts/check_repository.py`: 496 archivos revisados, repositorio seguro.
- FastAPI TestClient: login, cabeceras de seguridad, salud y flujos API aprobados.
- Concurrencia: fusion de campos disjuntos y conflicto de campos solapados aprobados.
- Importaciones: persistencia e idempotencia de candidatos y excolaboradores aprobadas.
- Web: alta con preflight, ficha de 18 campos, derivados y trazabilidad aprobadas.
- Corpus golden: 20 CV sinteticos y anonimizados.

## Limitaciones verificadas

- La suite historica no se recolecta en el entorno local porque su dependencia declarada
  `langchain_openai` no esta instalada. El runtime greenfield no la necesita y su suite si pasa.
- `BIZ-001..010` continuan en estado `BLOCKED`; las capacidades afectadas fallan cerrado o exigen
  revision humana. No se asignaron umbrales, vigencias, retenciones ni alcances ficticios.
- La Definition of Done global no puede declararse completa mientras esas decisiones y las tareas
  parciales registradas en `tasks.md` sigan abiertas.
