# Tareas — SPEC-011

- [x] **T-011-001 — Consolidar Candidate 360 autorizado**
  - Cubre: FR-011-001, AC-011-001
  - Archivos: servicios, repositorios y rutas Candidate 360
  - Verificación: pruebas de aplicación, seguridad y auditoría
  - Dependencias: ninguna
- [x] **T-011-002 — Implementar ranking contextual**
  - Cubre: FR-011-002, FR-011-003, AC-011-003
  - Archivos: `app/application/services/ranking_service.py`
  - Verificación: `test_quien_no_supera_los_filtros_queda_al_final_del_ranking`
  - Dependencias: T-011-001
- [x] **T-011-003 — Restringir y explicar comparaciones**
  - Cubre: FR-011-002, AC-011-002
  - Archivos: servicio y ruta de comparación
  - Verificación: `test_no_se_comparan_candidaturas_de_vacantes_distintas`
  - Dependencias: T-011-002
- [x] **T-011-004 — Presentar vista consolidada**
  - Cubre: FR-011-001–FR-011-003, AC-011-001–AC-011-003
  - Archivos: `ats_frontend/pages/7_Candidate360.py`, cliente API
  - Verificación: pruebas API y smoke de Streamlit
  - Dependencias: T-011-001–T-011-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes.
- [x] No se mezclan vacantes ni se genera ranking global.
