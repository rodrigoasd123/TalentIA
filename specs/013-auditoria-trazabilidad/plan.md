# Plan — SPEC-013

## Resumen técnico

Documentar retrospectivamente la auditoría append-only y el decision trail. Cada evento registra contexto mínimo, enlaza el hash anterior y permite verificar manipulación sin duplicar PII innecesaria.

## Arquitectura y límites afectados

- `app/application/services/audit_service.py` y `decision_trail.py`.
- Entidad/modelo/repositorio de eventos y rutas de auditoría.
- `ats_frontend/pages/9_Auditoria.py` y `tests/ats/test_persistence_and_audit.py`.

## Flujo de datos

Operación relevante → evento mínimo con actor/recurso/cambios/procedencia → hash anterior → inserción append-only → consulta cronológica o verificación de cadena.

## Decisiones y alternativas

- Cadena hash local para detectar alteración; WORM/firma certificada queda fuera de alcance.
- Repositorio sin update/delete desde la aplicación.
- IDs y metadatos mínimos en vez de copiar documentos o secretos.

## Compatibilidad, transición y reversión

No modifica eventos existentes. La auditoría no se revierte ni se borra desde negocio; la extracción documental puede revertirse volviendo a SPEC-004.

## Seguridad, privacidad y fallos

Consulta de solo lectura por permiso. Manipulación o hueco rompe verificación. Exportaciones minimizan PII y no incluyen secretos.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-013-001 | persistencia | génesis, enlace y cadena íntegra |
| AC-013-002 | adversarial | modificación y eliminación detectadas |
| AC-013-003 | integración | decision trail aislado y procedencia |

## Riesgos y mitigaciones

- Alteración silenciosa: verificación de cadena.
- PII excesiva: payload mínimo y pruebas.
- Mezcla de postulaciones: filtro por recurso e historia cronológica.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
