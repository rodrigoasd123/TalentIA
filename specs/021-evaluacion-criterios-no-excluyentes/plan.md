# Plan — SPEC-021

## Resumen técnico

Extender criterios con modo excluyente o ponderado, resultado ternario y penalización porcentual. Solo un incumplimiento acreditado y excluyente corta el grafo; los demás continúan y el backend calcula el impacto.

## Arquitectura y límites afectados

Dominio, grafo determinístico, contratos API, vistas Vacantes/Evaluaciones y pruebas ATS. Sin dependencias nuevas.

## Flujo de datos

`criterio aprobado → resultado ternario → bloqueo acreditado o evaluación → penalización → revisión humana → presentación explicable`.

## Decisiones

- Extender contratos existentes con defaults compatibles.
- Penalización porcentual de 0 a 100 aplicada una vez.
- Ausencia de evidencia = no acreditado.
- El LLM no controla modo, penalización ni total.

## Compatibilidad, transición y reversión

Sin migración SQL: los requisitos están serializados. API aditiva, historial inmutable y reversión mediante versión anterior.

## Seguridad y fallos

RBAC, aprobación, auditoría y prohibición de criterios sensibles permanecen. Una evaluación no ejecutada se muestra como tal.

## Pruebas

Dominio y grafo ternario; cálculo independiente; API/versionado; UI sin cero engañoso; historial inmutable; suite completa y smoke.

## Aprobación

- [x] Plan aprobado por la persona responsable el 2026-09-11.
