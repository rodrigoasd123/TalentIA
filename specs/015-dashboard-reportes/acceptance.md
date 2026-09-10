# Aceptación — SPEC-015

## AC-015-001 — Métricas coherentes

Resumen, funnel, alertas, fuentes y duración se obtienen de la API y reflejan la fuente de verdad persistida.

**Evidencia:** servicios analíticos, contratos `/dashboard/*` y suite de regresión ATS.

## AC-015-002 — Acceso autorizado

Un usuario sin `APPLICATION_READ` no puede consultar los endpoints analíticos.

**Evidencia:** dependencias RBAC y pruebas de endpoints protegidos.

## AC-015-003 — Estado vacío seguro

La interfaz puede representar ausencia de datos sin fabricar valores ni producir una decisión laboral.

**Evidencia:** comportamiento implementado y smoke de Streamlit; verificación visual exhaustiva pendiente en SPEC-017.
