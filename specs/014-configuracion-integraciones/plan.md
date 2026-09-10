# Plan — SPEC-014

## Resumen técnico

Documentar retrospectivamente la configuración gobernada y los adaptadores opcionales. Los settings públicos se separan de secretos cifrados; las pruebas de conexión son explícitas y el mock conserva operación sin proveedor.

## Arquitectura y límites afectados

- `app/core/config.py`, `app/infrastructure/settings_store.py` y `app/core/crypto.py`.
- Factory/adaptadores LLM, Gmail, rutas `/config/*` y métricas.
- `ats_frontend/pages/1_Configuracion.py` y pruebas de configuración/seguridad.

## Flujo de datos

Actor autorizado → clave permitida → validación → cifrado si es secreto → persistencia → respuesta enmascarada. La prueba de proveedor devuelve solo estado accionable.

## Decisiones y alternativas

- Secretos cifrados y enmascarados, nunca hardcodeados.
- Adaptador mock por defecto para recorrido sin red.
- Catálogo permitido en vez de settings arbitrarios.

## Compatibilidad, transición y reversión

No cambia claves ni valores de SPEC-004. Desactivar una integración vuelve al mock o a `DRY_RUN`; la operación no depende de Gemini/Gmail.

## Seguridad, privacidad y fallos

Solo permisos administrativos modifican. Errores no revelan secretos. Claves desconocidas fallan de forma segura y el proveedor caído no habilita autonomía.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-014-001 | seguridad | cifrado/enmascaramiento en `test_config_and_graph.py` |
| AC-014-002 | RBAC | `tests/ats/test_security_endpoints.py` |
| AC-014-003 | resiliencia | fallo de proveedor y smoke con mock |

## Riesgos y mitigaciones

- Secreto expuesto: cifrado, máscara, scanner y logs mínimos.
- Dependencia externa: puertos desacoplados y mock.
- Configuración inválida: allowlist y validación tipada.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
