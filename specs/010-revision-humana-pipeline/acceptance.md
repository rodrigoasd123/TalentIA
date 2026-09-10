# Aceptación — SPEC-010

## AC-010-001 — Transición autorizada

El backend acepta una transición permitida y rechaza una inválida, terminal o solicitada por un actor sin permiso.

**Evidencia:** pruebas de máquina de estados y RBAC en `test_domain_rules.py`.

## AC-010-002 — Resolución explicable

Resolver una revisión exige decisión y justificación y conserva el resultado original junto con la intervención humana.

**Evidencia:** pruebas de revisión en `test_application_flow.py`.

## AC-010-003 — Sin automatización irreversible

Con los flags del piloto desactivados, shortlist, rechazo, contacto y contratación requieren una persona.

**Evidencia:** suites de políticas y dominio.
