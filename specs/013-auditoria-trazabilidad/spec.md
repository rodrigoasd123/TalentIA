---
id: SPEC-013
titulo: Auditoría y trazabilidad de decisiones
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-013 — Auditoría y trazabilidad de decisiones

## Propósito

Reconstruir acciones de usuarios, sistema e IA mediante eventos inmutables y encadenados, sin convertir los logs en una copia de datos personales.

## Alcance vigente

- Eventos con actor, acción, recurso, estados anterior/nuevo y procedencia de IA.
- Cadena hash verificable y repositorio append-only.
- Incidentes de seguridad diferenciados.
- Traza cronológica por postulación.
- Consulta de auditoría de solo lectura y exportación autorizada.

## Fuera de alcance

SIEM externo, firma digital certificada, retención productiva, WORM y correlación multiempresa.

## Requisitos heredados

- **FR-013-001 (SPEC-004 FR-015):** registrar acciones relevantes y verificar la cadena.
- **FR-013-002:** conservar procedencia de modelo, prompt, política y aprobación humana.
- **FR-013-003:** impedir edición o eliminación desde el repositorio de aplicación.

## Implementación y evidencia

`audit_service.py`, `decision_trail.py`, repositorio/evento de auditoría, página `9_Auditoria.py` y `tests/ats/test_persistence_and_audit.py`.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
