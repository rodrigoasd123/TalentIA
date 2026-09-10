---
id: SPEC-006
titulo: Identidad, sesión y control de acceso
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-006 — Identidad, sesión y control de acceso

## Propósito

Garantizar que cada operación de TalentIA identifique al actor y aplique permisos por rol, sin conceder acceso implícito a datos personales o configuración.

## Alcance vigente

- Inicio de sesión, access token, refresh token, cierre de sesión y consulta de sesión.
- Roles `ADMIN`, `RECRUITER`, `HIRING_MANAGER`, `INTERVIEWER` y `AUDITOR`.
- Autorización por permiso en endpoints; denegación por defecto.
- Contraseñas Argon2id, rotación de refresh token y revocación de familia.
- Sesión limitada de laboratorio exclusivamente en `development`.

## Fuera de alcance

SSO/OIDC, aprovisionamiento corporativo, MFA, multitenancy productivo y recuperación de contraseña.

## Requisitos heredados

- **FR-006-001 (SPEC-004 SEC-002):** todo endpoint ATS debe autenticar y autorizar por permiso.
- **FR-006-002 (SPEC-004 SEC-003):** el acceso a PII debe limitarse por rol y propósito.
- **FR-006-003 (SPEC-004 SEC-009):** secretos y tokens no se devuelven completos ni aparecen en logs.
- **FR-006-004:** el auditor no dispone de operaciones de escritura.

## Implementación y evidencia

`app/api/dependencies.py`, rutas `/api/v1/auth/*`, `app/infrastructure/security/` y `tests/ats/test_security_endpoints.py`. Verificación original: SPEC-004 AC-006, AC-007 y AC-013.

## Brechas conocidas

No apto para despliegue compartido hasta incorporar SSO/MFA, gobierno de cuentas y aislamiento organizacional.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
