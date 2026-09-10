# Plan — SPEC-009

## Resumen técnico

Documentar retrospectivamente el grafo de evaluación gobernada. El LLM solo propone extracción y dimensiones estructuradas; nodos determinísticos aplican guardrails, filtros, score, políticas y derivación humana.

## Arquitectura y límites afectados

- Grafo, nodos, estado y esquemas bajo `app/ai/`.
- Guardrails y políticas bajo `app/ai/guardrails/` y `app/ai/policies/`.
- Score/filtros en `app/domain/rules/`; adaptadores LLM y pruebas adversariales.

## Flujo de datos

CV no confiable → detección de inyección → extracción → anonimización → proveedor opcional → validación → evidencia → filtros/score en código → políticas → resultado o revisión.

## Decisiones y alternativas

- El modelo no calcula el total ni cambia estados.
- Salida Pydantic, anonimización previa y verificación posterior.
- Fallo, incertidumbre o documento hostil deriva a revisión.

## Compatibilidad, transición y reversión

El mock mantiene operación sin red. No cambia prompts, grafo ni esquema. Se puede desactivar el proveedor externo sin perder reglas determinísticas.

## Seguridad, privacidad y fallos

El CV es contenido no confiable. Se detecta inyección, se minimiza PII y se verifica evidencia. Timeout, salida inválida o presupuesto excedido fallan cerrado.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-009-001 | dominio/grafo | `test_config_and_graph.py`, `test_domain_rules.py` |
| AC-009-002 | privacidad | `tests/ats/test_pii_leakage.py` |
| AC-009-003 | adversarial | `tests/ats/test_prompt_injection.py` |

## Riesgos y mitigaciones

- Alucinación: esquema y verificador de citas.
- Fuga de PII: sanitización y pruebas del payload efectivo.
- Proveedor caído: mock y revisión humana.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
