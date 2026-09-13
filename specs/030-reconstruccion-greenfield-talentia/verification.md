# Verificacion - SPEC-030

Fecha de verificacion: 2026-09-13.

Estado SDD: fase 1 implementada y en verificacion; no se declara `VERIFIED` ni se inicia fase 2.

## Evidencia de fase 1 - lectura documental y AG-02

- `pytest -q tests/greenfield/test_document_extraction.py`: 5 pruebas aprobadas.
- DOCX: texto extraido localmente, PII sanitizada y cuatro sugerencias con pagina y fragmento fuente.
- PDF sin texto: deriva de forma segura a `revision_manual` con `ocr_requerido`; el puerto OCR
  permanece opcional.
- PDF corrupto e instrucciones incrustadas: extraccion bloqueada con codigo seguro, sin texto ni
  sugerencias persistidas.
- Archivo vacio y firma incompatible: rechazados antes del almacenamiento.
- Idempotencia: una segunda solicitud reutiliza la extraccion y conserva una sola fila de extraccion
  y cuatro sugerencias.
- Proveedor remoto: AG-02 es determinista y local en esta fase; no existe un puerto de proveedor en
  el recorrido documental, por lo que los rechazos no pueden consumir tokens.
- `mypy src/talentia`: 58 archivos sin observaciones.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `python scripts/check_repository.py`: 507 archivos revisados, repositorio seguro.

## Evidencia aprobada

- `pytest -q tests/greenfield`: 44 pruebas aprobadas.
- `pytest -q`: 359 pruebas aprobadas; suite historica y greenfield compatibles.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `mypy src/talentia`: 58 archivos sin observaciones.
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
- AG-02 ya puede procesar PDF/DOCX por API y persistir sugerencias, pero el worker todavia no invoca
  ese recorrido. Esa conexion pertenece a la fase 2.
- No se incluyo un motor OCR concreto: el adaptador es opcional y la ausencia de texto deriva a
  revision humana, segun el alcance aprobado de la fase 1.
- `BIZ-001..010` continuan en estado `BLOCKED`; las capacidades afectadas fallan cerrado o exigen
  revision humana. No se asignaron umbrales, vigencias, retenciones ni alcances ficticios.
- La Definition of Done global no puede declararse completa mientras esas decisiones y las tareas
  parciales registradas en `tasks.md` sigan abiertas.
