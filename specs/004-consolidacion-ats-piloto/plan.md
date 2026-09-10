# Plan — SPEC-004

## Resumen técnico

Consolidar el ATS recibido como aplicación principal bajo `app/` y `ats_frontend/`, conservando el flujo Streamlit actual como rollback. La API FastAPI será la única puerta de negocio; Streamlit seguirá siendo un cliente HTTP. Se importará por lista permitida y se añadirá la ingesta completa, OCR local reutilizado, sugerencias Boolean manuales y documentación reproducible.

## Arquitectura y límites afectados

- Nuevos: `app/`, `ats_frontend/`, `fixtures/`, `scripts/`, `docs/adr/`, `pyproject.toml`.
- Adaptados: `backend/pdf_reader.py` como dependencia del adaptador OCR, `requirements.txt`, `.gitignore`, `README.md`.
- Preservados: `frontend/streamlit_postulacion.py`, `backend/` y sus contratos actuales.
- Pruebas ATS aisladas bajo `tests/ats/`; regresión existente permanece en `tests/`.

## Flujo de datos

Vacante aprobada → formulario autenticado → candidato con consentimiento + PDF/DOCX → validación binaria → extracción normal u OCR local → candidato/CV/candidatura en una unidad de trabajo → evaluación gobernada → revisión humana → transición válida → auditoría.

La IA usa un grafo acotado y salida estructurada. Antes del proveedor se anonimiza; el backend calcula el total y ejecuta políticas. LinkedIn recibe solo una consulta Boolean para operación manual. Gmail permanece en borrador y `DRY_RUN`.

## Decisiones y alternativas

- Se adopta VERA en vez de ampliar la UI monolítica existente: ya aporta dominio, persistencia, RBAC, auditoría y guardrails.
- Se usa `ats_frontend/` en vez de reemplazar `frontend/`: permite rollback verificable.
- Se reutiliza OCR mediante adaptador en vez de duplicarlo.
- No se incorpora RSC, scraping, Gmail real, PostgreSQL ni LangSmith.

## Compatibilidad, transición y reversión

- SQLite de laboratorio se crea de nuevo desde fixtures; no se migra `vera.db` del RAR.
- El entrypoint heredado conserva sus módulos y comando.
- Reversión: ejecutar el Streamlit heredado o retirar `app/` y `ats_frontend/`; no hay migración destructiva.
- Configuración nueva solo mediante `.env.example`; los secretos reales permanecen fuera de Git.

## Seguridad, privacidad y fallos

- Importación allowlist; exclusión y escaneo de secretos/PII/artefactos.
- Autenticación y RBAC en endpoints mutables; auditoría de PII.
- CV tratado como no confiable, validado antes de persistir y anonimizado antes del LLM.
- Proveedor caído deriva a revisión; mock permite operar sin red.
- El piloto muestra advertencia explícita de datos ficticios.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-001 | integración/manual | `tests/ats/test_intake_api.py` y pantalla Ingreso |
| AC-002 | unitaria | `tests/ats/test_ocr_adapter.py` |
| AC-003 | regresión ATS | scoring, graph y evidencia existentes |
| AC-004 | seguridad | `tests/ats/test_prompt_injection.py` |
| AC-005 | seguridad | `tests/ats/test_pii_leakage.py` |
| AC-006 | integración | flujo de revisión, RBAC y transición |
| AC-007 | integración | Candidate 360 y auditoría |
| AC-008 | integración | ranking y comparación contextual |
| AC-009 | unitaria/API | salida Boolean y ausencia de automatización web |
| AC-010 | integración | adaptador espía y `DRY_RUN` |
| AC-011 | sistema | seed + API sin clave + suite sin red |
| AC-012 | regresión | pruebas actuales de PostulaIA |
| AC-013 | publicación | estado Git, escaneo, pruebas y SHA remoto |

## Riesgos y mitigaciones

- Dependencias incompatibles: instalar y probar en entorno limpio; fijar rangos compatibles.
- Suite recibida no comprobada: ejecutarla antes de adaptar y después de integrar.
- Autenticación incompleta en UI: añadir sesión/login al cliente antes del recorrido manual.
- OCR costoso: conservar límites de archivo y ejecutar solo cuando la extracción sea insuficiente.

## Aprobación

- [x] Plan aprobado por la persona responsable el 2026-09-10 mediante aprobación explícita de todas las fases.
