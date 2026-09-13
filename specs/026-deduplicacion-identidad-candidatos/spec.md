# SPEC-026 — Deduplicación de identidad de candidatos

- **Estado:** VERIFIED
- **Fuente:** Documento TCS, agente 1 y orden operativo propuesto.

## Problema y alcance

TCS y Adecco verifican manualmente si una persona ya fue contactada, evaluada o descartada. TalentIA debe alertar antes de procesar el CV, sin fusionar personas automáticamente.

## Requisitos

- **FR-026-001:** antes de guardar/procesar el CV se comparan documento, correo, teléfono y nombre normalizado contra toda la base.
- **FR-026-002:** las coincidencias muestran identidad enmascarada, procesos previos, estado, fecha y reclutador.
- **FR-026-003:** correo/documento exactos reutilizan la identidad solo con reglas inequívocas; coincidencias aproximadas requieren decisión humana.
- **FR-026-004:** una postulación repetida a la misma vacante se bloquea idempotentemente.
- **NFR-026-001:** la búsqueda debe ser determinista y operar sin LLM.
- **SEC-026-001:** el resultado respeta `candidate:pii:read` y no expone PII a Adecco.
- **SEC-026-002:** toda resolución queda auditada; no hay fusión automática por nombre/teléfono.

## Fuera de alcance y riesgos

No inferir identidad biométrica ni eliminar registros. Los falsos positivos se mitigan con revisión humana. Sin preguntas bloqueantes.
