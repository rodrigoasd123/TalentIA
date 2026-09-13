# API greenfield

La documentacion OpenAPI esta en `/docs`. La API usa `/api/v1`, token Bearer firmado y alcance
por cliente. Los endpoints principales corresponden a la tabla de `IMPLEMENTATION_SPEC.md`:
autenticacion, comprobacion de identidad, candidatos, perfiles, postulaciones, documentos,
trabajos, lotes, excolaboradores, exclusiones y metricas.

Las mutaciones devuelven errores uniformes con `codigo`, `mensaje` y `correlacion_id`.

