# Tareas — SPEC-004

- [x] **T-001 — Importar el ATS mediante lista permitida**
  - Cubre: NFR-001, NFR-007; SEC-001, SEC-010, SEC-011; AC-013
  - Archivos: `app/`, `ats_frontend/`, `fixtures/`, `scripts/`, `docs/adr/`, `pyproject.toml`, `.gitignore`
  - Verificación: inventario Git y búsqueda de secretos/artefactos prohibidos
  - Dependencias: ninguna

- [x] **T-002 — Resolver entorno y regresión base**
  - Cubre: FR-016, FR-017; NFR-003, NFR-005, NFR-008; AC-011, AC-012
  - Archivos: `requirements.txt`, `README.md`, pruebas existentes y `tests/ats/`
  - Verificación: instalación/imports y `python -m pytest -q`
  - Dependencias: T-001

- [x] **T-003 — Exponer ingesta transaccional autenticada**
  - Cubre: FR-001–FR-005; SEC-002–SEC-004; AC-001
  - Archivos: `app/api/schemas.py`, `app/api/v1/routes/operations.py`, `app/application/use_cases/intake.py`, `ats_frontend/api_client.py`, nueva página de ingreso
  - Verificación: pruebas API positivas, consentimiento, duplicado, rol e idempotencia
  - Dependencias: T-002

- [x] **T-004 — Integrar extracción normal y OCR local**
  - Cubre: FR-004; NFR-004, NFR-008; SEC-004, SEC-005; AC-002
  - Archivos: `app/infrastructure/documents/text_extractor.py`, adaptador OCR nuevo, `backend/pdf_reader.py`
  - Verificación: PDF de texto, DOCX y PDF escaneado ficticio con referencias de página
  - Dependencias: T-002

- [x] **T-005 — Consolidar UI ATS y autenticación**
  - Cubre: FR-009–FR-012, FR-015; NFR-002; SEC-002, SEC-003, SEC-008; AC-006–AC-008
  - Archivos: `ats_frontend/streamlit_app.py`, `ats_frontend/api_client.py`, `ats_frontend/pages/*`
  - Verificación: prueba de cliente y recorrido manual de estados vacíos/error/éxito
  - Dependencias: T-003

- [x] **T-006 — Completar ayudas gobernadas y operación sin efectos**
  - Cubre: FR-006–FR-008, FR-013, FR-014, FR-016; SEC-005–SEC-009; AC-003–AC-005, AC-009–AC-011
  - Archivos: `app/ai/`, `app/api/`, `app/application/services/`, pruebas de IA/seguridad
  - Verificación: suite adversarial, proveedor caído, salida Boolean y cero envío
  - Dependencias: T-003, T-004

- [x] **T-007 — Documentar operación, rollback y publicación**
  - Cubre: FR-016, FR-017; NFR-005–NFR-008; SEC-010, SEC-011; AC-011–AC-013
  - Archivos: `README.md`, `.env.example`, `specs/004-consolidacion-ats-piloto/verification.md`
  - Verificación: comandos reproducibles, suite completa, escaneo de secretos y push comprobado
  - Dependencias: T-001–T-006

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos por tareas y evidencia prevista.
- [x] No quedan bloqueantes.
- [x] Existe estrategia de fallos, transición y reversión.
