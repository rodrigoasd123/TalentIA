# Aceptación — SPEC-008

## AC-008-001 — Alta transaccional

Con vacante aprobada, consentimiento vigente y documento válido, una sola operación crea o reutiliza candidato, registra CV y crea la postulación sin estados parciales.

**Evidencia:** `test_alta_completa_crea_vacante_candidato_cv_y_candidatura`.

## AC-008-002 — Consentimiento obligatorio

Una persona sin consentimiento vigente no puede registrarse ni evaluarse.

**Evidencia:** pruebas de consentimiento en `test_intake_api.py` y `test_application_flow.py`.

## AC-008-003 — OCR con páginas

Un PDF sin texto útil activa el adaptador OCR local y conserva marcas de página.

**Evidencia:** `tests/ats/test_ocr_adapter.py`.
