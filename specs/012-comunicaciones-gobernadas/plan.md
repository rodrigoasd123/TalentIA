# Plan — SPEC-012

## Resumen técnico

Documentar retrospectivamente la preparación gobernada de comunicaciones. El servicio usa plantillas aprobadas, valida destinatario e idempotencia y delega en un adaptador Gmail que permanece en `DRY_RUN`.

## Arquitectura y límites afectados

- `app/application/services/email_service.py` y motor de políticas.
- `app/infrastructure/email/gmail_adapter.py`, rutas `/emails*` y repositorios.
- Pruebas en `test_application_flow.py` y `test_policy_and_guardrails.py`.

## Flujo de datos

Plantilla aprobada + postulación + actor → variables permitidas → borrador → validación de destinatario/duplicado/sensibilidad → revisión humana cuando aplica → registro auditado sin envío real.

## Decisiones y alternativas

- Plantillas versionadas en vez de prompts libres.
- Correo registrado como único destinatario válido.
- `DRY_RUN` predeterminado; Gmail real queda fuera de alcance.

## Compatibilidad, transición y reversión

No cambia contratos ni mensajes existentes. Desactivar el adaptador externo conserva los borradores. No hay efecto remoto que revertir en el piloto.

## Seguridad, privacidad y fallos

No se aceptan destinatarios tomados del CV o del modelo. Mensajes sensibles requieren aprobación. Claves y tokens no se auditan ni se muestran.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-012-001 | integración | pruebas de servicio con `DRY_RUN` |
| AC-012-002 | seguridad | prueba de destinatario registrado |
| AC-012-003 | política | pruebas de idempotencia y aprobación |

## Riesgos y mitigaciones

- Envío involuntario: adaptador desacoplado y `DRY_RUN`.
- Destinatario inyectado: valor exclusivo del registro autorizado.
- Duplicado: clave idempotente.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
