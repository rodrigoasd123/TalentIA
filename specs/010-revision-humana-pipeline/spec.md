---
id: SPEC-010
titulo: Revisión humana y pipeline de selección
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-010 — Revisión humana y pipeline de selección

## Propósito

Controlar el ciclo de vida de cada postulación mediante transiciones autorizadas y decisiones humanas justificadas.

## Alcance vigente

- Pipeline por vacante y máquina de estados de postulación.
- Transiciones válidas, permisos, motivos y auditoría.
- Cola de revisión, reclamo, resolución, modificación y vencimiento.
- Conservación de propuesta, valor anterior, decisión humana y justificación.
- Bloqueo de contratación/rechazo/contacto autónomos.

## Fuera de alcance

Automatizaciones irreversibles, SLA productivo, asignación corporativa avanzada y coordinación externa de entrevistas.

## Requisitos heredados

- **FR-010-001 (SPEC-004 FR-009):** permitir solo transiciones válidas, autorizadas y auditadas.
- **FR-010-002 (SPEC-004 FR-011):** resolver revisiones con decisión y justificación obligatoria.
- **FR-010-003:** un agente no puede ejecutar transiciones reservadas a personas.

## Implementación y evidencia

`state_machine.py`, servicios de revisión/decision trail, rutas de pipeline/review, páginas `5_Pipeline.py` y `6_Revision.py`, pruebas de dominio y flujo.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
