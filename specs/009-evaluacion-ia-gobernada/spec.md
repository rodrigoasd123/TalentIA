---
id: SPEC-009
titulo: Evaluación asistida por IA gobernada
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-009 — Evaluación asistida por IA gobernada

## Propósito

Producir evaluación documental explicable sin delegar al modelo los filtros, el puntaje total, los estados ni las decisiones laborales.

## Alcance vigente

- Grafo acotado con mayoría de nodos determinísticos.
- CV tratado como entrada no confiable y detección de prompt injection.
- Anonimización previa a cualquier proveedor LLM.
- Salida estructurada por dimensiones, verificación de citas y evidencia.
- Total calculado por backend con criterios versionados.
- Fallback controlado y derivación a revisión ante fallo o incertidumbre.

## Fuera de alcance

Contratación/rechazo autónomo, inferencia de atributos sensibles, herramientas de escritura y uso del LLM como fuente de verdad.

## Requisitos heredados

- **FR-009-001 (SPEC-004 FR-006):** anonimizar y verificar evidencia antes/después del proveedor.
- **FR-009-002 (SPEC-004 FR-007):** calcular score total en código.
- **FR-009-003 (SPEC-004 FR-008):** exponer filtros, dimensiones, brechas, procedencia y motivos de revisión.
- **FR-009-004:** una inyección o fallo del proveedor no ejecuta efectos y deriva a revisión.

## Implementación y evidencia

`app/ai/`, reglas de scoring/políticas y suites `test_config_and_graph.py`, `test_policy_and_guardrails.py`, `test_prompt_injection.py` y `test_pii_leakage.py`.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
