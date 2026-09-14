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

## AC-006-004 — Arranque sin credenciales predecibles

Con una base vacía, solo se crea un administrador cuando correo y contraseña se entregan juntos
por entorno; ningún arranque ni seed crea usuarios `@ejemplo.local` o la clave histórica conocida.

## AC-006-005 — Bloqueo auditable

Tras alcanzar el máximo configurable de intentos inválidos, incluso la contraseña correcta falla
hasta terminar el bloqueo. El contador, vencimiento y eventos sobreviven al rechazo HTTP.

## AC-006-006 — Revocación efectiva

Un token válido deja de autorizar inmediatamente después de logout, cambio de contraseña o cambio
de alcance. La comprobación ocurre contra el usuario activo persistido.

## AC-006-007 — Política y caducidad

Una contraseña débil o conocida no puede aprovisionarse ni reemplazar a otra, y una contraseña
vencida no permite iniciar sesión.

## AC-006-008 — Migración reversible

La migración de seguridad sube desde `0003_workflow`, conserva usuarios existentes y puede bajar
sin dejar columnas o índices nuevos.
