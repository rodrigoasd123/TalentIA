# Verificación heredada — SPEC-006

- Fuente: SPEC-004 AC-006, AC-007 y AC-013.

- Evidencia: `tests/ats/test_security_endpoints.py`, `test_domain_rules.py` y CI de TalentIA.

- Resultado: **VERIFICADO**, sin ejecutar cambios de comportamiento durante la distribución.

- Límite: SSO, MFA y aislamiento productivo permanecen fuera de alcance.

## Refinamiento greenfield — 2026-09-14

Estado: `VERIFICANDO`.

- Se confirmó que el runtime y seed contenían seis cuentas `@ejemplo.local` y una contraseña fija;
  ambas rutas fueron retiradas.
- La autenticación ahora persiste intentos, bloqueo y auditoría antes de responder 401.
- Cada petición autenticada contrasta `sesion_version` y estado activo con SQLite.
- Logout y cambio de contraseña revocan sesiones; los cambios de rol/cliente también incrementan
  la versión.
- Pruebas focalizadas iniciales: `8 passed`; regresión completa inicial detectó siete pruebas que
  fabricaban tokens para usuarios inexistentes. La infraestructura de prueba fue corregida para
  ejercer RBAC/IDOR con usuarios persistidos, sin introducir bypass de seguridad.
- Migración SQLite: `upgrade head`, `downgrade 0003_workflow` y nuevo `upgrade head` aprobaron;
  las cuatro columnas y el índice se eliminaron/restauraron como se esperaba.
- Suite greenfield final: `87 passed, 2 warnings in 97.61s`.
- Ruff: aprobado; formato: `89 files already formatted`; mypy: 65 archivos sin errores.
- Scanner: repositorio seguro, 348 archivos revisados; identidad visible aprobada.
- El run remoto `34821866388` aprobó con seguridad incluida; estado final `VERIFICADO`.
