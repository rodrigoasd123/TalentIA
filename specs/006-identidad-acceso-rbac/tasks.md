# Tareas — SPEC-006

- [x] **T-006-001 — Implementar credenciales y sesión rotatoria**
  - Cubre: FR-006-001, AC-006-001
  - Archivos: `app/infrastructure/security/`, modelos y rutas `/api/v1/auth/*`
  - Verificación: `tests/ats/test_security_endpoints.py`
  - Dependencias: ninguna

- [x] **T-006-002 — Aplicar permisos con denegación por defecto**
  - Cubre: FR-006-001, FR-006-004, AC-006-002
  - Archivos: `app/api/dependencies.py`, `app/domain/enums.py`, rutas protegidas
  - Verificación: pruebas RBAC y de auditor sin escritura
  - Dependencias: T-006-001

- [x] **T-006-003 — Proteger PII y credenciales**
  - Cubre: FR-006-002, FR-006-003, AC-006-003
  - Archivos: dependencias de API, settings y logging
  - Verificación: pruebas de PII, hashing, secretos enmascarados y scanner
  - Dependencias: T-006-001

- [x] **T-006-004 — Verificar sesión de laboratorio acotada**
  - Cubre: FR-006-001, AC-006-002
  - Archivos: `app/core/config.py`, `ats_frontend/api_client.py`
  - Verificación: prueba que impide sesión implícita fuera de `development`
  - Dependencias: T-006-002

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes dentro del laboratorio.
- [x] Los fallos de sesión y autorización cierran el acceso.
