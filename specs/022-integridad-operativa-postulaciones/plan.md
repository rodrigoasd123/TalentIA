# Plan — SPEC-022

## Resumen técnico

Extender el contrato existente de postulaciones, reutilizar `UploadResumeUseCase`, añadir
una operación idempotente a `ReviewService` y aplicar filtros de presentación en Streamlit.

## Arquitectura y límites afectados

- Dominio/aplicación: creación manual idempotente de revisión.
- API: asociación de CV y solicitud de revisión; metadatos de integridad.
- Frontend: bandeja de CV, filtros y métricas reconciliadas.
- API/analítica: sincronización transaccional de `candidate.source` hacia postulaciones.
- Frontend: fuente Adecco explícita y recarga controlada con mensaje persistente.
- Persistencia: sin migraciones; se reutilizan tablas actuales.

## Flujo de datos

Archivo → extractor existente → ResumeDocument → `application.resume_id` → auditoría.
Evaluación → solicitud humana → caso abierto único → transición válida si corresponde.

## Decisiones y alternativas

- No se fuerza una transición inválida de etapas avanzadas: el caso puede existir sin alterar la etapa.
- No se deriva la cola desde el estado; se consulta `human_reviews` como fuente real.

## Compatibilidad, transición y reversión

Los campos API son aditivos. Reversión: retirar endpoints/campos y vistas; los documentos y
casos creados permanecen como acciones explícitas auditadas.

## Seguridad, privacidad y fallos

Se conservan permisos y extractor vigentes. No se registran bytes ni texto del documento.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-001 | automatizada | payload de aplicaciones |
| AC-002 | automatizada | endpoint de asociación |
| AC-003 | automatizada | idempotencia de revisión |
| AC-004 | manual/compilación | vistas Streamlit |
| AC-005 | automatizada/manual | payload y mensaje de auditoría |
| AC-006 | automatizada | actualización de candidato y analítica de fuentes |
| AC-007 | automatizada/manual | estado Streamlit y listado posterior al alta |

## Riesgos y mitigaciones

- Datos seed incoherentes: se etiquetan, nunca se corrigen masivamente.
- Doble clic: búsqueda previa de revisión y deduplicación por hash.
- Cambio de fuente histórica: se ejecuta solo ante una edición humana explícita y se audita.

## Aprobación

- [x] Plan aprobado por la persona responsable el 2026-09-11.
