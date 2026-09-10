---
id: SPEC-015
titulo: Dashboard y reportes operativos
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-015 — Dashboard y reportes operativos

## Propósito

Presentar métricas operativas del proceso de selección sin convertir agregados o scores en decisiones automáticas sobre personas.

## Alcance vigente

- Resumen operativo y embudo por estado.
- Alertas SLA, fuentes y duración por etapa.
- Filtros provistos por API y visualización Altair.
- Estados sin datos y acceso condicionado a permisos.
- Exportaciones únicamente donde existe contrato real.

## Fuera de alcance

BI corporativo, predicción de desempeño, inferencia sensible, benchmarking externo y reportes regulatorios definitivos.

## Requisitos derivados

- **FR-015-001:** todas las métricas proceden de la API y de datos persistidos; Streamlit no recalcula reglas de negocio.
- **FR-015-002:** las métricas de selección se presentan como apoyo operativo y no como aprobación/rechazo.
- **FR-015-003:** endpoints y exportaciones respetan permisos y minimización.

## Implementación y evidencia

`analytics_service.py`, rutas `/dashboard/*`, página `8_Dashboard.py`, pruebas de servicios/seguridad y smoke de SPEC-004.

## Brecha conocida

La matriz visual completa, responsive y accesible queda reservada a SPEC-017.

## Historial

- 2026-09-10: extraída de la línea base implementada por SPEC-004, sin cambio de comportamiento.
