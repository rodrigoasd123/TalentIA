# Aceptación — SPEC-016

## AC-016-001 — Instalación reproducible

Desde un entorno limpio se instalan dependencias, se aplica `alembic upgrade head`, se siembran fixtures y se inician API y Streamlit con los comandos documentados.

**Evidencia:** CI de TalentIA y smoke local de SPEC-004/005.

## AC-016-002 — Migración desde base vacía

Alembic crea el esquema completo en SQLite vacío y registra la revisión vigente.

**Evidencia:** gate de migración de CI y verificación SPEC-005.

## AC-016-003 — Rollback disponible

El entry point heredado conserva carga PDF, OCR, ranking y consulta sin escribir en la base ATS.

**Evidencia:** regresión heredada y comando documentado en README.
