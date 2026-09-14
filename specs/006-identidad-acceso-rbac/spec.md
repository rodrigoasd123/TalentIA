---
id: SPEC-006
titulo: Identidad, sesión y control de acceso
estado: VERIFICANDO
tipo: ESPECIFICACION_ACTIVA
origen: SPEC-004, SPEC-030
actualizado: 2026-09-14
---

# SPEC-006 — Identidad, sesión y control de acceso

## Propósito

Garantizar que cada operación de TalentIA identifique al actor y aplique permisos por rol, sin conceder acceso implícito a datos personales o configuración.

## Alcance vigente

- Inicio de sesión firmado, cierre con revocación y cambio de contraseña.
- Roles del dominio greenfield definidos en `modules/access/domain/modelos.py`.
- Autorización por permiso en endpoints; denegación por defecto.
- Contraseñas derivadas con scrypt, bloqueo persistente y revocación mediante versión de sesión.
- Provisión inicial exclusivamente mediante variables de entorno.

## Fuera de alcance

SSO/OIDC, aprovisionamiento corporativo, MFA, multitenancy productivo y recuperación de contraseña.

## Requisitos heredados

- **FR-006-001 (SPEC-004 SEC-002):** todo endpoint ATS debe autenticar y autorizar por permiso.
- **FR-006-002 (SPEC-004 SEC-003):** el acceso a PII debe limitarse por rol y propósito.
- **FR-006-003 (SPEC-004 SEC-009):** secretos y tokens no se devuelven completos ni aparecen en logs.
- **FR-006-004:** el auditor no dispone de operaciones de escritura.

## Implementación y evidencia

La evidencia heredada procede de SPEC-004. El runtime vigente se implementa en
`src/talentia/platform/security/`, rutas `/api/v1/auth/*`, repositorio SQLAlchemy y
`tests/greenfield/test_seguridad.py`.

## Brechas conocidas

SSO/MFA y recuperación autoservicio siguen pendientes para producción. El piloto sí aplica
aislamiento por cliente, RBAC, bloqueo y revocación persistente.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
- 2026-09-14: refinamiento greenfield aprobado al ordenar la ejecución completa de
  `PENDIENTES_IMPLEMENTACION_GREENFIELD.md`.

## Refinamiento greenfield aprobado

El runtime oficial `src/talentia` debe provisionar exclusivamente la cuenta administradora
declarada mediante entorno, sin usuarios ni claves de laboratorio. Las contraseñas deben aplicar
longitud y complejidad, caducar de forma configurable y rechazar credenciales comprometidas
conocidas. Los intentos fallidos se persisten y bloquean temporalmente la cuenta. Cada token
incluye una versión de sesión contrastada contra SQLite; logout, cambio de contraseña y cambios de
roles o clientes invalidan sesiones anteriores.

### Requisitos nuevos

- **FR-006-005:** el arranque no crea cuentas previsibles y exige el par completo de variables de
  provisión; piloto sin usuario inicial falla cerrado.
- **FR-006-006:** cinco fallos consecutivos por defecto bloquean temporalmente la cuenta y todos
  los intentos quedan auditados sin registrar correo en claro.
- **FR-006-007:** logout y cambio de contraseña revocan los tokens emitidos; las sesiones vencidas,
  de usuarios inactivos o con versión antigua fallan cerradas.
- **FR-006-008:** la contraseña tiene mínimo 14 caracteres, mayúscula, minúscula, número y símbolo,
  rechaza la clave de laboratorio conocida y caduca en un plazo configurable.
- **FR-006-009:** cambios de rol o alcance invalidan sesiones previas para impedir permisos obsoletos.

### Fuera de alcance del refinamiento

SSO, MFA y recuperación autoservicio continúan fuera del piloto y son requisitos de producción.
