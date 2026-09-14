# Plan — SPEC-026

Normalizar acentos/espacios, usar identificadores fuertes exactos y similitud conservadora de nombre. Añadir preflight API antes del upload, reutilizar repositorio y auditoría; intake repite la validación transaccional para evitar TOCTOU. Rollback desactiva preflight conservando unicidades existentes. Pruebas: exactos, nombre variante, homónimo, permisos, historial e idempotencia.

## Refinamiento 2026-09-14

Separar señales fuertes (documento/correo) de señales probables (teléfono/nombre), retirar el límite
artificial, devolver evidencia mínima enmascarada y exigir una confirmación booleana explícita en
API/web. No se agrega LLM ni se implementa similitud configurable hasta resolver `BIZ-004`.
