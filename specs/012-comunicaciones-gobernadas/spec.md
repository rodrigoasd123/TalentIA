---
id: SPEC-012
titulo: Comunicaciones gobernadas
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-012 — Comunicaciones gobernadas

## Propósito

Preparar comunicaciones trazables desde plantillas aprobadas sin producir envíos externos no autorizados.

## Alcance vigente

- Plantillas versionadas, variables permitidas y aprobación.
- Preparación idempotente dirigida exclusivamente al correo registrado.
- Revisión humana para mensajes sensibles.
- Adaptador Gmail desacoplado, estado visible y `DRY_RUN` predeterminado.
- Auditoría de preparación/aprobación sin secretos.

## Fuera de alcance

Envío real, OAuth productivo, campañas, calendario, InMail y contacto automático.

## Requisitos heredados

- **FR-012-001 (SPEC-004 FR-014):** preparar borradores desde plantillas aprobadas.
- **FR-012-002:** `DRY_RUN` impide todo efecto externo.
- **FR-012-003:** destinatario, duplicados y mensajes sensibles se validan por política.

## Implementación y evidencia

`email_service.py`, `gmail_adapter.py`, motor de políticas, rutas `/emails*` y pruebas de comunicaciones en `test_application_flow.py` y `test_policy_and_guardrails.py`.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
