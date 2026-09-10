# Tareas — SPEC-013

- [x] **T-013-001 — Modelar eventos encadenados**
  - Cubre: FR-013-001, AC-013-001
  - Archivos: entidad y modelo de auditoría, `audit_service.py`
  - Verificación: pruebas de génesis y enlace
  - Dependencias: ninguna
- [x] **T-013-002 — Restringir persistencia a append-only**
  - Cubre: FR-013-003, AC-013-002
  - Archivos: repositorio de auditoría
  - Verificación: pruebas adversariales de modificación/eliminación
  - Dependencias: T-013-001
- [x] **T-013-003 — Conservar procedencia y decisión humana**
  - Cubre: FR-013-002, AC-013-003
  - Archivos: `decision_trail.py`, servicios de evaluación y revisión
  - Verificación: pruebas de traza y procedencia
  - Dependencias: T-013-001
- [x] **T-013-004 — Exponer consulta autorizada**
  - Cubre: FR-013-001–FR-013-003, AC-013-001–AC-013-003
  - Archivos: rutas y `ats_frontend/pages/9_Auditoria.py`
  - Verificación: pruebas RBAC, API y smoke
  - Dependencias: T-013-002, T-013-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes del laboratorio.
- [x] La manipulación resulta detectable y no existe borrado de negocio.
