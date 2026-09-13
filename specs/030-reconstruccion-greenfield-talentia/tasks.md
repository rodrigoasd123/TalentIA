# Tareas por fases - SPEC-030

## Estado previo conservado

- [x] **T-030-001 - Bootstrap, CI y configuracion segura**
  - Cubre: FR-030-001, NFR-030-002, OPS-030-001, AC-030-001
  - Evidencia: `verification.md`
- [x] **T-030-003 - Persistencia, migraciones y unidad de trabajo**
  - Cubre: FR-030-003, NFR-030-001, AC-030-003, AC-030-006
  - Evidencia: `verification.md`

## Fase 1 - Lectura documental y AG-02

- [x] **T-030-F1-001 - Implementar extractores PDF/DOCX y fallback OCR**
  - Cubre: FR-030-003, FR-030-004, SEC-030-001, AC-030-003, AC-030-004
  - Archivos: `src/talentia/modules/documents/infrastructure/extractores.py` (nuevo), adaptadores
    existentes de documentos
  - Verificacion: pruebas nuevas `tests/greenfield/test_document_extraction.py`
  - Dependencias: almacenamiento privado existente
- [x] **T-030-F1-002 - Persistir extraccion y sugerencias idempotentes**
  - Cubre: FR-030-003, FR-030-005, AC-030-003, AC-030-005
  - Archivos: puertos, servicio y repositorio SQLAlchemy existentes
  - Verificacion: integracion sobre `document_extractions` y `field_suggestions`
  - Dependencias: T-030-F1-001
- [x] **T-030-F1-003 - Probar PII, inyeccion, firma y documento vacio**
  - Cubre: SEC-030-001, AC-030-004, AC-030-008
  - Archivos: `tests/greenfield/test_document_extraction.py` (nuevo),
    `tests/greenfield/test_storage.py`
  - Verificacion: AG-02 local sin puerto de proveedor remoto; bloqueos persisten codigo seguro y
    cero sugerencias
  - Dependencias: T-030-F1-001

## Fase 2 - AG-03 y LangGraph durable

- [x] **T-030-F2-001 - Implementar nodos reales y estado serializable**
  - Cubre: FR-030-004, NFR-030-001, AC-030-004, AC-030-006
  - Archivos: `src/talentia/ai/workflows/nodos_evaluacion.py` (nuevo),
    `evaluation_graph.py`, `estado.py`
  - Verificacion: diez checkpoints por nodo real, estado con lista blanca serializable y prueba de
    rechazo temprano sin texto ni sugerencias
  - Dependencias: fase 1
- [x] **T-030-F2-002 - Conectar procesador real al worker**
  - Cubre: FR-030-004, FR-030-005, AC-030-004, AC-030-005
  - Archivos: `src/talentia/ai/workflows/procesador_evaluacion.py` (nuevo), `worker.py`
  - Verificacion: AG-02 procesa el documento y AG-03 persiste evaluacion, requisitos, evidencia
    minima verificable y revision humana en una unidad de trabajo
  - Dependencias: T-030-F2-001
- [x] **T-030-F2-003 - Checkpoint, lease, timeout, retry y reinicio**
  - Cubre: FR-030-005, AC-030-005
  - Archivos: worker, repositorio y posible migracion Alembic nueva si el lease exige esquema
  - Verificacion: `tests/greenfield/test_workflow_restart.py` cubre fallo inyectado, reanudacion,
    concurrencia, lease vencido, timeout e idempotencia sin duplicados
  - Dependencias: T-030-F2-002

## Fase 3 - Interfaz de evaluacion y HITL

- [ ] **T-030-F3-001 - Mostrar evaluacion y evidencia navegable**
  - Cubre: FR-030-003, FR-030-004, AC-030-003, AC-030-004
  - Archivos: rutas web y plantillas nuevas de evaluacion
  - Verificacion: prueba web y E2E
  - Dependencias: fase 2
- [ ] **T-030-F3-002 - Resolver revision con correcciones auditadas**
  - Cubre: FR-030-003, SEC-030-001, AC-030-002, AC-030-003
  - Archivos: rutas, plantillas y servicio existentes; plantilla nueva de revision
  - Verificacion: aceptar/corregir/rechazar, comentario, CSRF, RBAC, IDOR y repeticion 409
  - Dependencias: T-030-F3-001
- [ ] **T-030-F3-003 - Polling HTMX y estados de interfaz**
  - Cubre: FR-030-005, NFR-030-002, AC-030-001, AC-030-005
  - Archivos: fragmentos y plantillas Jinja2/HTMX nuevas
  - Verificacion: pendiente, reservado, completado, revision y error
  - Dependencias: T-030-F3-001

## Fase 4 - Formularios operativos

- [ ] **T-030-F4-001 - Formularios de perfiles y versiones**
  - Cubre: FR-030-003, AC-030-003
  - Archivos: rutas/plantillas nuevas y casos de uso existentes
  - Verificacion: alta, version, requisitos, publicacion, RBAC e IDOR
  - Dependencias: fase 3
- [ ] **T-030-F4-002 - Formulario de postulacion y prevencion de duplicados**
  - Cubre: FR-030-003, SEC-030-001, AC-030-002, AC-030-003
  - Archivos: rutas/plantillas nuevas y servicio existente
  - Verificacion: candidato/perfil/fuente, duplicado e identidad cruzada
  - Dependencias: T-030-F4-001
- [ ] **T-030-F4-003 - Carga CV, lanzamiento y seguimiento de trabajo**
  - Cubre: FR-030-003, FR-030-005, AC-030-003, AC-030-005
  - Archivos: rutas, plantillas y fragmentos nuevos
  - Verificacion: E2E sin llamadas API manuales
  - Dependencias: T-030-F4-002

## Fase 5 - Lotes, ex-TCS y exclusiones

- [ ] **T-030-F5-001 - Completar mapeo y correccion de lotes**
  - Cubre: FR-030-003, SEC-030-001, AC-030-003
  - Archivos: rutas/plantillas nuevas y servicio/repositorio existentes
  - Verificacion: staging, errores, correccion, confirmacion y rollback
  - Dependencias: fase 4
- [ ] **T-030-F5-002 - Completar flujo ex-TCS minimizado**
  - Cubre: FR-030-003, SEC-030-001, AC-030-003, AC-030-008
  - Archivos: rutas/plantillas nuevas
  - Verificacion: solo hash persistido, scope y BIZ bloqueadas
  - Dependencias: T-030-F5-001
- [ ] **T-030-F5-003 - Completar exclusiones y descarga**
  - Cubre: FR-030-003, SEC-030-001, AC-030-003, AC-030-008
  - Archivos: rutas/plantillas nuevas y AG-05 existente
  - Verificacion: protegidos ausentes, filtros/hash conservados y auditoria
  - Dependencias: T-030-F5-002

## Fase 6 - Observabilidad, metricas y MLflow

- [ ] **T-030-F6-001 - Persistir telemetria correlacionada y sanitizada**
  - Cubre: FR-030-005, SEC-030-001, AC-030-005
  - Archivos: servicio/repositorio y posible migracion Alembic nueva
  - Verificacion: request-job-nodo-evaluacion reconstruible sin PII
  - Dependencias: fases 2 y 5
- [ ] **T-030-F6-002 - Calcular metricas y percentiles desde eventos reales**
  - Cubre: FR-030-003, AC-030-003
  - Archivos: casos de uso y panel de metricas
  - Verificacion: exactitud p50/p95, vacio y filtros
  - Dependencias: T-030-F6-001, BIZ-006 solo para metrica CV util
- [ ] **T-030-F6-003 - Integrar benchmark greenfield con MLflow**
  - Cubre: FR-030-004, NFR-030-002, AC-030-004
  - Archivos: scripts y pruebas de benchmark nuevos bajo `scripts` y `tests/greenfield`
  - Verificacion: corrida reproducible con corpus sintetico y proveedor opcional
  - Dependencias: T-030-F6-001

## Fase 7 - Endurecimiento y aceptacion tecnica

- [ ] **T-030-F7-001 - Completar matriz security/E2E/restart**
  - Cubre: todos los requisitos y AC-030-001..008
  - Archivos: suites `tests/greenfield` nuevas o ampliadas
  - Verificacion: regresion completa y reporte de cobertura por riesgo
  - Dependencias: fases 1..6
- [ ] **T-030-F7-002 - Verificar migracion, backup, restore e instalacion limpia**
  - Cubre: OPS-030-001, AC-030-001, AC-030-007
  - Archivos: scripts y runbook existentes
  - Verificacion: ejecucion Windows documentada
  - Dependencias: T-030-F7-001
- [ ] **T-030-F7-003 - Cerrar evidencia tecnica de rubrica**
  - Cubre: AC-030-001..008
  - Archivos: `verification.md`, `rubric-gap-review.md`
  - Verificacion: cero P0/P1 tecnicas abiertas no aceptadas
  - Dependencias: T-030-F7-002

## Fase 8 - Decisiones y UAT

- [ ] **T-030-F8-001 - Refinar spec con BIZ-001..010 aprobadas**
  - Cubre: AC-030-008 y requisitos afectados
  - Archivos: artefactos SDD mediante `sdd-refine-es`
  - Verificacion: decisiones, impacto, nuevas pruebas y aprobacion
  - Dependencias: decisiones TCS
- [ ] **T-030-F8-002 - Ejecutar UAT de RR. HH.**
  - Cubre: AC-030-001, AC-030-003, AC-030-004, AC-030-007
  - Archivos: evidencia UAT nueva bajo `specs/030-reconstruccion-greenfield-talentia`
  - Verificacion: escenarios firmados y defectos cerrados
  - Dependencias: fase 7 y T-030-F8-001
- [ ] **T-030-F8-003 - Preparar promocion sin ejecutarla**
  - Cubre: todos los requisitos aprobados
  - Archivos: comparacion de rama y checklist de release
  - Verificacion: PR revisable; merge requiere autorizacion explicita
  - Dependencias: T-030-F8-002

## Puertas de salida

- [ ] Cada fase enlaza requisitos, criterios y evidencia.
- [ ] Cada fase pasa suite greenfield y regresion completa.
- [ ] No hay secretos, PII real, bases locales ni artefactos en Git.
- [ ] Los cambios de esquema tienen upgrade, downgrade y prueba reversible.
- [ ] Las decisiones `BIZ` no aprobadas permanecen bloqueadas o en revision humana.
- [ ] Ninguna fase se mezcla a `main` sin demostracion y aprobacion.
