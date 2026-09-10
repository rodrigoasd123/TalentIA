# Tareas — SPEC-010

- [x] **T-010-001 — Centralizar transiciones del pipeline**
  - Cubre: FR-010-001, FR-010-003, AC-010-001, AC-010-003
  - Archivos: `app/domain/rules/state_machine.py`, enums y políticas
  - Verificación: `tests/ats/test_domain_rules.py`
  - Dependencias: ninguna
- [x] **T-010-002 — Implementar cola y resolución explicable**
  - Cubre: FR-010-002, AC-010-002
  - Archivos: servicios de revisión, repositorios y decision trail
  - Verificación: `tests/ats/test_application_flow.py`
  - Dependencias: T-010-001
- [x] **T-010-003 — Aplicar permisos y auditoría**
  - Cubre: FR-010-001–FR-010-003, AC-010-001–AC-010-003
  - Archivos: rutas de review/pipeline, dependencias y auditoría
  - Verificación: pruebas RBAC, estados terminales y eventos
  - Dependencias: T-010-002
- [x] **T-010-004 — Exponer pipeline y revisión en UI**
  - Cubre: FR-010-001, FR-010-002, AC-010-001, AC-010-002
  - Archivos: `ats_frontend/pages/5_Pipeline.py`, `6_Revision.py`
  - Verificación: smoke de Streamlit y flujo API
  - Dependencias: T-010-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes.
- [x] Operaciones fallidas no dejan una transición parcial.
