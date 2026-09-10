# Plan — SPEC-007

## Resumen técnico

Documentar retrospectivamente el agregado `Job` y sus criterios versionados. El dominio valida pesos y estados; la API exige aprobación humana antes de abrir o evaluar y solo genera una consulta Boolean para sourcing manual.

## Arquitectura y límites afectados

- Dominio de vacantes en `app/domain/`; rutas en `app/api/v1/routes/operations.py`.
- Persistencia mediante repositorios SQLAlchemy y UI en `ats_frontend/pages/2_Vacantes.py`.
- Evidencia en `tests/ats/test_intake_api.py` y `tests/ats/test_domain_rules.py`.

## Flujo de datos

Borrador → criterios y pesos válidos → aprobación humana → vacante abierta. Editar criterios incrementa la versión y devuelve a borrador. Sourcing transforma requisitos aprobados en una consulta Boolean sin llamar a LinkedIn.

## Decisiones y alternativas

- Criterios versionados en backend, no reglas calculadas en UI.
- Aprobación explícita y pesos validados en dominio.
- Consulta copiable en lugar de scraping, RSC o automatización web.

## Compatibilidad, transición y reversión

No cambia contratos ni datos de SPEC-004. Las versiones previas permanecen trazables. No existe integración externa que deba revertirse.

## Seguridad, privacidad y fallos

Solo actores autorizados modifican o aprueban. Pesos y transiciones inválidos se rechazan antes de persistir. Sourcing no contiene credenciales ni ejecuta efectos.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-007-001 | integración | versionado y aprobación en `tests/ats/test_intake_api.py` |
| AC-007-002 | unitaria | pesos en `tests/ats/test_domain_rules.py` |
| AC-007-003 | API | prueba de consulta Boolean manual |

## Riesgos y mitigaciones

- Criterios obsoletos: toda edición invalida aprobación.
- Automatización accidental: el contrato devuelve texto y declara operación manual.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
