# Plan — SPEC-006

## Resumen técnico

Documentar retrospectivamente la identidad y el RBAC ya consolidados por SPEC-004. FastAPI autentica la sesión, resuelve al actor y exige permisos antes de invocar casos de uso; la persistencia conserva hashes y familias de refresh tokens.

## Arquitectura y límites afectados

- `app/api/dependencies.py` y rutas de autenticación: sesión y autorización.
- `app/infrastructure/security/`: hashing Argon2id y tokens.
- `app/domain/enums.py`: roles y permisos.
- `app/infrastructure/database/`: usuarios y sesiones persistidas.
- `ats_frontend/api_client.py`: propagación del access token.
- `tests/ats/test_security_endpoints.py`: evidencia principal.

## Flujo de datos

Credenciales → verificación Argon2id → access/refresh token → dependencia autenticada → permiso requerido → operación o denegación. El refresh rota la familia; reutilización o logout revocan la sesión.

## Decisiones y alternativas

- Autorización en backend, no solo ocultamiento en Streamlit.
- Permisos explícitos y denegación por defecto en vez de confiar en nombres de rol.
- Argon2id y refresh rotatorio en lugar de contraseñas o sesiones reversibles.
- La sesión implícita se limita a `development`; SSO/MFA queda como brecha productiva.

## Compatibilidad, transición y reversión

La extracción desde SPEC-004 no cambia API, esquema ni tokens. Reversión documental: volver a la trazabilidad de SPEC-004. Un despliegue productivo requiere sustituir la sesión de laboratorio sin relajar permisos.

## Seguridad, privacidad y fallos

Los secretos no se devuelven completos ni se registran. Un token ausente, vencido, de tipo incorrecto o sin permiso falla cerrado. El auditor permanece en solo lectura.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-006-001 | seguridad/integración | `tests/ats/test_security_endpoints.py` |
| AC-006-002 | autorización | `tests/ats/test_security_endpoints.py`, `tests/ats/test_domain_rules.py` |
| AC-006-003 | seguridad | pruebas de hashing, tokens y settings en `tests/ats/` |

## Riesgos y mitigaciones

- Confundir UI oculta con autorización: todos los controles efectivos permanecen en FastAPI.
- Reutilización de refresh token: rotación y revocación de familia.
- Uso compartido del laboratorio: declarado fuera de alcance hasta SSO/MFA.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.

## Plan de refinamiento greenfield — 2026-09-14

1. Retirar del bootstrap y seed todas las cuentas y claves previsibles.
2. Ampliar `users` con contador/bloqueo, fecha de contraseña y versión de sesión mediante una
   migración Alembic reversible.
3. Persistir el resultado de autenticación antes de devolver el error para conservar auditoría y
   rate limiting.
4. Validar cada token contra SQLite y aumentar la versión al cerrar sesión, cambiar contraseña,
   rol o alcance.
5. Probar política, bloqueo, expiración, revocación, RBAC e IDOR con usuarios persistidos reales.

La revocación por versión invalida todas las sesiones del usuario. Es deliberadamente simple y
adecuada para SQLite/piloto; evita una tabla adicional de tokens y no expone identificadores de
sesión. La reversión operativa consiste en bajar `0004_seguridad` y revertir el commit del bloque.

- [x] Alcance y plan aprobados por el usuario el 2026-09-14 mediante la orden de ejecutar el MD de
  pendientes.
