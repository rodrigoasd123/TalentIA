# Tareas — SPEC-015

- [x] **T-015-001 — Calcular agregados desde persistencia**
  - Cubre: FR-015-001, FR-015-002, AC-015-001
  - Archivos: `app/application/services/analytics_service.py`, repositorios
  - Verificación: pruebas de servicios analíticos
  - Dependencias: ninguna
- [x] **T-015-002 — Exponer contratos autorizados**
  - Cubre: FR-015-001, FR-015-003, AC-015-001, AC-015-002
  - Archivos: rutas `/dashboard/*`, esquemas y dependencias
  - Verificación: pruebas API y acceso denegado
  - Dependencias: T-015-001
- [x] **T-015-003 — Representar métricas y estados vacíos**
  - Cubre: FR-015-002, AC-015-003
  - Archivos: `ats_frontend/pages/8_Dashboard.py`
  - Verificación: smoke de Streamlit con y sin datos
  - Dependencias: T-015-002
- [x] **T-015-004 — Delimitar rediseño pendiente**
  - Cubre: FR-015-002, FR-015-003, AC-015-003
  - Archivos: `specs/017-redisenio-frontend-talentia/`
  - Verificación: alcance visual trazado sin alterar backend
  - Dependencias: T-015-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes funcionales; el rediseño es otra spec.
- [x] La presentación puede revertirse sin cambiar la fuente de datos.
