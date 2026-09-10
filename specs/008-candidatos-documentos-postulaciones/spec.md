---
id: SPEC-008
titulo: Candidatos, documentos y postulaciones
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-008 — Candidatos, documentos y postulaciones

## Propósito

Mantener una persona candidata única y representar cada participación laboral mediante una postulación independiente vinculada a una vacante y una versión de CV.

## Alcance vigente

- Registro consentido de candidato y detección conservadora de duplicados.
- CV PDF/DOCX con validación de contenido, tamaño y extracción.
- OCR local cuando el PDF carece de texto suficiente.
- Versiones de CV y evidencia por página.
- Creación transaccional e idempotente de la postulación.

## Fuera de alcance

Portal público, verificación de identidad, autenticidad documental, fusión automática de duplicados y almacenamiento productivo de CV reales.

## Requisitos heredados

- **FR-008-001 (SPEC-004 FR-003):** registrar solo con consentimiento explícito y reportar duplicados sin fusionar.
- **FR-008-002 (SPEC-004 FR-004):** validar PDF/DOCX y usar OCR local cuando proceda.
- **FR-008-003 (SPEC-004 FR-005):** vincular candidato, vacante y CV transaccional e idempotentemente.
- **FR-008-004:** el estado de selección pertenece a `Application`, no a `Candidate`.

## Implementación y evidencia

Entidades y repositorios de candidato/CV/postulación, `intake.py`, `text_extractor.py`, `postulaia_ocr.py`, página `3_Ingreso.py` y pruebas `test_intake_api.py`, `test_ocr_adapter.py`, `test_application_flow.py`.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
