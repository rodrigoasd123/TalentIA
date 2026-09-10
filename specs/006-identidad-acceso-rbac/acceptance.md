# Aceptación — SPEC-006

## AC-006-001 — Sesión segura

Dadas credenciales válidas, el sistema emite tokens diferenciados; un refresh token no sirve como access token, su reutilización revoca la familia y logout invalida la sesión.

**Evidencia:** `tests/ats/test_security_endpoints.py`.

## AC-006-002 — RBAC denegado por defecto

Un endpoint protegido devuelve acceso denegado a una sesión sin permiso y el auditor no puede escribir; la sesión implícita de laboratorio no existe fuera de desarrollo.

**Evidencia:** pruebas de permisos en `test_security_endpoints.py` y `test_domain_rules.py`.

## AC-006-003 — Credenciales no expuestas

Las contraseñas se almacenan con Argon2id y ninguna respuesta de configuración devuelve secretos completos.

**Evidencia:** pruebas de hashing, token y secretos en `tests/ats/`.
