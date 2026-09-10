# Plan — SPEC-008

## Resumen técnico

Documentar retrospectivamente la ingesta transaccional de candidato, CV y postulación. El caso de uso valida consentimiento y documento, reutiliza identidades exactas conservadoramente y persiste la relación completa en una unidad de trabajo.

## Arquitectura y límites afectados

- Entidades y repositorios de candidato, CV y postulación.
- `app/application/use_cases/intake.py` y `app/infrastructure/documents/`.
- UI `ats_frontend/pages/3_Ingreso.py`; pruebas de intake, OCR y flujo.

## Flujo de datos

Consentimiento + identidad + documento + vacante aprobada → validación → extracción normal/OCR → candidato → versión de CV → postulación → commit único y auditoría.

## Decisiones y alternativas

- El estado laboral pertenece a `Application`, no a la persona.
- Duplicados dudosos no se fusionan automáticamente.
- OCR local conserva páginas; la unidad de trabajo evita estados parciales.

## Compatibilidad, transición y reversión

No cambia esquema ni contratos de SPEC-004. Ante fallo previo al commit se revierte toda la unidad de trabajo.

## Seguridad, privacidad y fallos

Se exigen consentimiento, tipo y tamaño permitidos. El nombre recibido no se usa como ruta. Un documento ilegible no crea registros parciales.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-008-001 | integración | `tests/ats/test_intake_api.py` |
| AC-008-002 | regla | pruebas de consentimiento y flujo |
| AC-008-003 | documento | `tests/ats/test_ocr_adapter.py` |

## Riesgos y mitigaciones

- Duplicado falso: coincidencia conservadora, sin fusión automática.
- Documento hostil: allowlist, límites y extracción aislada.
- Persistencia parcial: transacción e idempotencia.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
