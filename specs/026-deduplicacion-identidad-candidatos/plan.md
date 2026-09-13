# Plan — SPEC-026

Normalizar acentos/espacios, usar identificadores fuertes exactos y similitud conservadora de nombre. Añadir preflight API antes del upload, reutilizar repositorio y auditoría; intake repite la validación transaccional para evitar TOCTOU. Rollback desactiva preflight conservando unicidades existentes. Pruebas: exactos, nombre variante, homónimo, permisos, historial e idempotencia.
