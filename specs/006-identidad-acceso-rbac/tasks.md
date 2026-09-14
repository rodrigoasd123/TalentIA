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

## Refinamiento greenfield — 2026-09-14

- [x] **T-006-005 — Retirar credenciales previsibles**
  - Cubre: FR-006-005, AC-006-004
  - Archivos: `src/talentia/bootstrap.py`, `scripts/seed_greenfield.py`, `.env.example`
- [x] **T-006-006 — Aplicar política y bloqueo persistente**
  - Cubre: FR-006-006, FR-006-008, AC-006-005, AC-006-007
  - Archivos: seguridad, servicio, repositorio y configuración
- [x] **T-006-007 — Revocar y validar sesiones**
  - Cubre: FR-006-007, FR-006-009, AC-006-006
  - Archivos: API, web, dominio y persistencia
- [x] **T-006-008 — Migrar SQLite reversiblemente**
  - Cubre: AC-006-008
  - Archivo: `migrations_greenfield/versions/0004_seguridad_acceso.py`
- [ ] **T-006-009 — Cerrar verificación local y remota**
  - Cubre: todos los criterios nuevos
  - Evidencia: suite, lint, tipos, scanner, upgrade/downgrade y CI remoto
