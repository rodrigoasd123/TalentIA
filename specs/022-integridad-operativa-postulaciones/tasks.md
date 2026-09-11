# Tareas — SPEC-022

- [x] **T-001 — Contratos de integridad y asociación documental**
  - Cubre: FR-001, FR-002, AC-001, AC-002
  - Archivos: `app/api/v1/routes/operations.py`, `app/application/use_cases/intake.py`
  - Verificación: pruebas API focales
  - Dependencias: ninguna
- [x] **T-002 — Solicitud humana idempotente**
  - Cubre: FR-004, FR-005, AC-003
  - Archivos: `app/application/services/review_service.py`, API y cliente
  - Verificación: pruebas de servicio/API
  - Dependencias: T-001
- [x] **T-003 — Bandeja, filtros y métricas reconciliadas**
  - Cubre: FR-003, FR-005, AC-004
  - Archivos: vistas de Postulaciones, Pipeline, Evaluaciones y Candidate 360
  - Verificación: compilación y smoke Streamlit
  - Dependencias: T-001, T-002
- [x] **T-004 — Diagnóstico de auditoría y regresión**
  - Cubre: FR-006, AC-005
  - Archivos: API/vista Auditoría y pruebas
  - Verificación: pytest focal y global
  - Dependencias: T-001..T-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos por tareas.
- [x] No quedan bloqueantes.
- [x] Existe estrategia para fallos y reversión.

## Evidencia de implementación

- `python -m compileall -q app ats_frontend`: aprobado.
- `python -m pytest tests/ats/test_intake_api.py -q`: 6 aprobadas.
- `python -m pytest -q`: 289 aprobadas, una advertencia deprecada de Starlette/httpx.
- API `/health/ready`: `ready`, SQLite y LLM disponible.
- Streamlit `http://127.0.0.1:8501`: HTTP 200.
- Pendiente: aceptación visual y funcional manual por RR. HH.
