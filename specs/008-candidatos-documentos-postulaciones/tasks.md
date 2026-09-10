# Tareas — SPEC-008

- [x] **T-008-001 — Separar persona, CV y postulación**
  - Cubre: FR-008-004, AC-008-001
  - Archivos: `app/domain/entities.py`, modelos y repositorios
  - Verificación: pruebas de persistencia y flujo
  - Dependencias: ninguna
- [x] **T-008-002 — Validar consentimiento e identidad**
  - Cubre: FR-008-001, AC-008-002
  - Archivos: `app/application/use_cases/intake.py`, contratos API
  - Verificación: pruebas de consentimiento y duplicados
  - Dependencias: T-008-001
- [x] **T-008-003 — Extraer PDF/DOCX con OCR local**
  - Cubre: FR-008-002, AC-008-003
  - Archivos: `app/infrastructure/documents/`, `backend/pdf_reader.py`
  - Verificación: `tests/ats/test_ocr_adapter.py`
  - Dependencias: ninguna
- [x] **T-008-004 — Persistir el alta atómica e idempotente**
  - Cubre: FR-008-003, AC-008-001
  - Archivos: intake, unidad de trabajo, repositorios, API y página de ingreso
  - Verificación: `test_alta_completa_crea_vacante_candidato_cv_y_candidatura`
  - Dependencias: T-008-001–T-008-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes.
- [x] Los fallos previos al commit revierten el alta completa.
