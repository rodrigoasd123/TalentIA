# Plan — SPEC-010

## Resumen técnico

Documentar retrospectivamente el pipeline y la cola de revisión. La máquina de estados valida toda transición; el servicio conserva propuesta, decisión humana y justificación en auditoría.

## Arquitectura y límites afectados

- `app/domain/rules/state_machine.py` y estados en `app/domain/enums.py`.
- Servicios de revisión y decision trail, rutas de pipeline/review.
- Páginas `5_Pipeline.py`, `6_Revision.py` y pruebas de dominio/flujo.

## Flujo de datos

Evaluación → motivo de revisión → cola → reclamo autorizado → decisión y justificación → transición válida → persistencia y evento encadenado.

## Decisiones y alternativas

- Estados validados en backend, no por controles visuales.
- Acciones irreversibles reservadas a personas.
- Se conserva tanto la propuesta como la corrección humana.

## Compatibilidad, transición y reversión

No cambia estados ni contratos existentes. Una transición inválida no se persiste; una resolución fallida revierte su unidad de trabajo.

## Seguridad, privacidad y fallos

Permisos por acción, motivo obligatorio y auditoría. Ítems vencidos o ya reclamados no pueden resolverse silenciosamente.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-010-001 | dominio/RBAC | `tests/ats/test_domain_rules.py` |
| AC-010-002 | integración | `tests/ats/test_application_flow.py` |
| AC-010-003 | políticas | suites de políticas y dominio |

## Riesgos y mitigaciones

- Saltos de estado: máquina centralizada.
- Doble resolución: reclamo/versionado e idempotencia.
- Autonomía indebida: flags conservadores y permisos humanos.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
