---
id: SPEC-022
titulo: Integridad operativa de postulaciones
estado: VERIFICANDO
responsable_producto: Rodrigo
creado: 2026-09-11
actualizado: 2026-09-11
---

# SPEC-022 — Integridad operativa de postulaciones

## Problema y resultado esperado

La base histórica contiene postulaciones en etapas avanzadas sin CV asociado y el estado
`human_review` no siempre coincide con la existencia de un caso abierto en la cola. RR. HH.
necesita detectar y corregir datos incompletos, filtrar expedientes y solicitar validaciones
humanas desde la evaluación sin que TalentIA tome decisiones de contratación.

## Usuarios y necesidades

- RR. HH. necesita ubicar postulaciones sin CV y asociar el archivo correcto.
- Revisores necesitan distinguir estado del pipeline de carga real de trabajo.
- Auditores necesitan interpretar una ruptura de integridad sin una reparación destructiva.

## Alcance

### Incluido

- Indicador y filtro de CV asociado en listados, Pipeline y Candidate 360.
- Bandeja de postulaciones sin CV con carga y asociación a una postulación existente.
- Filtros por vacante, estado, candidato y disponibilidad de CV.
- Solicitud idempotente de revisión humana desde Evaluaciones por información no acreditada.
- Métricas separadas para postulaciones en estado de revisión y casos abiertos.
- Mensaje accionable y no destructivo para inconsistencias de auditoría.

### Fuera de alcance

- Inventar o reconstruir CV ausentes.
- Reparar o reencadenar automáticamente eventos de auditoría.
- Aprobar, rechazar o contactar automáticamente a candidatos.
- Migrar SQLite o modificar integraciones externas.

## Requisitos funcionales

- **FR-001:** La API debe exponer si cada postulación tiene un CV asociado y un caso de revisión abierto.
- **FR-002:** Un usuario autorizado debe poder cargar y asociar PDF/DOCX a una postulación existente, con validación, consentimiento y auditoría.
- **FR-003:** Postulaciones, Pipeline y Candidate 360 deben filtrar por vacante, estado, texto y disponibilidad de CV cuando aplique.
- **FR-004:** Evaluaciones debe permitir crear de forma idempotente un caso de revisión por criterio no acreditado, conservando el control humano.
- **FR-005:** Pipeline debe mostrar por separado postulaciones en estado `human_review` y casos abiertos de revisión.
- **FR-006:** Auditoría debe explicar que una ruptura indica datos históricos alterados/importados y que no se corrige automáticamente.
- **FR-007:** Al crear o editar un candidato, la fuente de reclutamiento debe reflejarse de forma consistente en sus postulaciones y reportes, incluyendo Adecco.
- **FR-008:** Después de crear una postulación, la interfaz debe volver a consultar la API y mostrarla en el listado sin exigir una recarga manual.

## Requisitos no funcionales

- **NFR-001:** Las operaciones nuevas no deben duplicar CV idénticos ni casos de revisión abiertos.
- **NFR-002:** Los filtros deben operar sin llamadas al modelo ni consumo de tokens.
- **NFR-003:** La funcionalidad debe preservar compatibilidad con datos históricos incompletos.
- **NFR-004:** La sincronización de fuente debe ser transaccional, normalizada y auditada.

## Seguridad y privacidad

- **SEC-001:** La carga requiere `candidate:write`; la revisión requiere `review:decide`.
- **SEC-002:** El contenido del CV se procesa con el extractor existente y nunca se inserta como HTML.
- **SEC-003:** Toda asociación y solicitud de revisión debe quedar auditada sin registrar el texto completo del CV.

## Reglas y fuentes de verdad

- `applications.resume_id` determina la asociación documental real.
- `applications.status` determina la etapa; `human_reviews` determina la cola real.
- La máquina de estados sigue siendo la única fuente de transiciones válidas.
- `candidate.source` representa la fuente maestra registrada para la persona y se sincroniza
  en sus postulaciones cuando RR. HH. la modifica explícitamente.
- `application.source` es la fuente usada por los reportes operativos.

## Supuestos confirmados

- El usuario aprobó todas las decisiones y fases de esta solicitud el 2026-09-11.
- Las inconsistencias históricas se muestran y corrigen mediante acciones explícitas, no silenciosamente.

## Riesgos y fallos esperados

- Un archivo ilegible se rechaza sin cambiar la postulación.
- Una etapa avanzada sin CV queda marcada como dato incompleto hasta asociación manual.
- Una postulación puede tener estado de revisión sin caso abierto; ambas cifras se muestran separadas.

## Preguntas abiertas

Ninguna bloqueante.

## Historial de decisiones

| Fecha | Decisión | Responsable | Motivo |
|---|---|---|---|
| 2026-09-11 | No reparar ni inventar datos históricos | Rodrigo | Preservar trazabilidad y control humano |
| 2026-09-11 | Separar etapa y cola de revisión | Rodrigo | Son conceptos operativos distintos |
| 2026-09-11 | Implementación completada; pasa a verificación manual | Codex | 289 pruebas automatizadas aprobadas |
| 2026-09-11 | Refinamiento aprobado para sincronizar fuente y refrescar listados | Rodrigo | La demo mostró información desactualizada e inconsistente entre módulos |
| 2026-09-11 | Refinamiento R1 implementado | Codex | Fuente persistida y 290 pruebas aprobadas |
