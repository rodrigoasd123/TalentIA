# Verificacion - SPEC-030

Fecha de verificacion: 2026-09-13.

## Evidencia aprobada

- `pytest -q tests/greenfield`: 44 pruebas aprobadas.
- `pytest -q`: 354 pruebas aprobadas; suite historica y greenfield compatibles.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `mypy src/talentia`: 56 archivos sin observaciones.
- Alembic en SQLite desechable: `upgrade head`, `downgrade base`, `upgrade head`; revision final
  persistida `0002_esquema`.
- `python scripts/check_repository.py`: 497 archivos revisados, repositorio seguro.
- FastAPI TestClient: login, cabeceras de seguridad, salud y flujos API aprobados.
- Concurrencia: fusion de campos disjuntos y conflicto de campos solapados aprobados.
- Importaciones: persistencia e idempotencia de candidatos y excolaboradores aprobadas.
- Web: alta con preflight, ficha de 18 campos, derivados y trazabilidad aprobadas.
- Web operativa: los modulos dejaron de ser placeholders y muestran proyecciones reales con alcance
  por cliente y permiso; formularios de escritura distintos del alta de candidatos siguen pendientes.
- Evaluacion/HITL: contexto referencial validado antes de encolar; worker persiste evaluacion y revision
  idempotentes; consulta y resolucion con correcciones quedan auditadas en la misma unidad de trabajo.
- Recuperacion: reservas de trabajo abandonadas por mas de 15 minutos vuelven a estar disponibles.
- Almacen de documentos: escritura atomica, sin sobreescritura y con defensa contra escape de ruta.
- Acceso: asignacion API/web de roles y clientes, auditoria y autoampliacion denegada.
- Corpus golden: 20 CV sinteticos y anonimizados.

## Limitaciones verificadas

- La suite completa se recolecta y pasa. Permanecen dos advertencias de deprecacion de dependencias
  (`Starlette/AnyIO` y serializador de checkpoint de LangGraph), sin fallos funcionales actuales.
- El grafo de evaluacion aun representa la secuencia y checkpoints, pero sus nodos no invocan el lector
  y evaluador reales desde el worker; el fallback actual crea revision humana y no simula una decision.
- `BIZ-001..010` continuan en estado `BLOCKED`; las capacidades afectadas fallan cerrado o exigen
  revision humana. No se asignaron umbrales, vigencias, retenciones ni alcances ficticios.
- La Definition of Done global no puede declararse completa mientras esas decisiones y las tareas
  parciales registradas en `tasks.md` sigan abiertas.
