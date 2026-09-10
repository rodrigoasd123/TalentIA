# Tareas — SPEC-009

- [x] **T-009-001 — Acotar grafo y contratos**
  - Cubre: FR-009-001, FR-009-003, AC-009-001
  - Archivos: `app/ai/graphs/`, `app/ai/state.py`, `app/ai/schemas.py`
  - Verificación: `tests/ats/test_config_and_graph.py`
  - Dependencias: ninguna
- [x] **T-009-002 — Tratar entrada y salida como no confiables**
  - Cubre: FR-009-001, FR-009-004, AC-009-002, AC-009-003
  - Archivos: `app/ai/guardrails/`, nodos determinísticos
  - Verificación: pruebas de PII, inyección y políticas
  - Dependencias: T-009-001
- [x] **T-009-003 — Calcular filtros y score en código**
  - Cubre: FR-009-002, FR-009-003, AC-009-001
  - Archivos: `app/domain/rules/scoring.py`, `hard_filters.py`
  - Verificación: pruebas de dominio y evaluación
  - Dependencias: T-009-001
- [x] **T-009-004 — Resolver fallos con revisión humana**
  - Cubre: FR-009-004, AC-009-003
  - Archivos: adaptadores LLM, políticas, rutas y página de evaluación
  - Verificación: proveedor caído, salida inválida y presupuesto excedido
  - Dependencias: T-009-002, T-009-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes del piloto.
- [x] Los fallos derivan a revisión sin efectos externos.
