---
id: SPEC-011
titulo: Candidate 360, ranking y comparación
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-011 — Candidate 360, ranking y comparación

## Propósito

Ofrecer una vista autorizada de la trayectoria de una persona y comparaciones explicables únicamente dentro del contexto de una vacante.

## Alcance vigente

- Candidate 360 con postulación, CV, evaluaciones, revisiones, comunicaciones y traza.
- Ranking por vacante, con filtros obligatorios y orden estable.
- Comparación explicable de dos postulaciones de la misma vacante.
- Minimización y auditoría del acceso a PII.

## Fuera de alcance

Ranking global de personas, perfilado sensible, recomendación definitiva y comparación entre vacantes distintas.

## Requisitos heredados

- **FR-011-001 (SPEC-004 FR-010):** consolidar historial permitido en Candidate 360.
- **FR-011-002 (SPEC-004 FR-012):** limitar ranking/comparación a una misma vacante y explicar diferencias.
- **FR-011-003:** los filtros no superados prevalecen sobre el score para el orden contextual.

## Implementación y evidencia

Servicios de ranking/decision trail, rutas Candidate 360/ranking/compare, página `7_Candidate360.py` y pruebas de aplicación, dominio y auditoría.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
