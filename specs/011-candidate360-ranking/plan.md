# Plan — SPEC-011

## Resumen técnico

Documentar retrospectivamente Candidate 360, ranking y comparación contextual. Los servicios consultan la fuente persistida, aplican filtros obligatorios y restringen toda comparación a una misma vacante.

## Arquitectura y límites afectados

- `app/application/services/ranking_service.py` y `decision_trail.py`.
- Repositorios y rutas Candidate 360/ranking/compare.
- `ats_frontend/pages/7_Candidate360.py` y pruebas de dominio, seguridad y auditoría.

## Flujo de datos

Actor autorizado + vacante/candidato → carga contextual → minimización → historial o ranking. La comparación valida la misma vacante y explica diferencias por dimensión.

## Decisiones y alternativas

- No existe ranking global de personas.
- Filtros obligatorios prevalecen sobre score.
- Candidate 360 minimiza por rol y deja auditoría de acceso.

## Compatibilidad, transición y reversión

No cambia consultas ni persistencia de SPEC-004. La reversión documental vuelve a la trazabilidad original; no hay transformación de datos.

## Seguridad, privacidad y fallos

El acceso a PII requiere permiso y propósito. IDs inexistentes o candidaturas de vacantes distintas se rechazan sin mezclar datos.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-011-001 | seguridad/integración | pruebas Candidate 360 y auditoría |
| AC-011-002 | dominio | prueba de comparación entre vacantes |
| AC-011-003 | ranking | prueba de filtros obligatorios |

## Riesgos y mitigaciones

- Comparación sin contexto: validación estricta de vacante.
- Perfilado excesivo: no hay score global ni atributos sensibles.
- Exposición de PII: permisos, minimización y auditoría.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
