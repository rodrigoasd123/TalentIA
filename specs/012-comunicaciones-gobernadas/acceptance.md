# Aceptación — SPEC-012

## AC-012-001 — Borrador sin envío

Con plantilla aprobada y `DRY_RUN`, el sistema registra solo un borrador y realiza cero envíos externos.

**Evidencia:** pruebas de servicio y política de comunicaciones.

## AC-012-002 — Destinatario controlado

El destinatario siempre coincide con el correo registrado; una dirección introducida por el CV o por el agente se deniega.

**Evidencia:** `test_el_destinatario_es_siempre_el_correo_registrado` y prueba de destinatario externo.

## AC-012-003 — Idempotencia y aprobación

La misma comunicación no se prepara o envía dos veces y las categorías sensibles exigen aprobación humana.

**Evidencia:** pruebas correspondientes en `test_application_flow.py`.
