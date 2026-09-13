# Matriz de riesgos tecnicos - fase 7

Fecha: 2026-09-13

Esta matriz enlaza los riesgos P0/P1 del piloto con controles ejecutables. Las decisiones
`BIZ-001..010` se registran por separado y no se consideran defectos tecnicos resueltos.

| Riesgo | Prioridad | Control y evidencia automatizada | Estado |
|---|---|---|---|
| Acceso sin autenticar, rol insuficiente o autoampliacion | P0 | `test_api.py`, `test_seguridad.py` | Cubierto |
| IDOR o acceso entre clientes | P0 | `test_operational_forms.py`, `test_evaluation_flow.py`, `test_fase_5_lotes_excolaboradores_exclusiones.py`, `test_fase_6_observabilidad.py` | Cubierto |
| Escritura web sin CSRF | P0 | `test_operational_forms.py`, `test_evaluation_flow.py`, `test_fase_5_lotes_excolaboradores_exclusiones.py` | Cubierto |
| CV invalido, vacio, traversal o prompt injection | P0 | `test_storage.py`, `test_document_extraction.py`, `test_workflow_restart.py` | Cubierto |
| PII, secretos o CV en telemetria | P0 | `test_fase_6_observabilidad.py`, `scripts/check_repository.py` | Cubierto |
| Rechazo automatico sin evidencia | P0 | `test_agentes.py`, `test_workflow_restart.py`, `test_evaluation_flow.py` | Cubierto |
| Efectos duplicados por reintento | P1 | `test_api.py`, `test_operational_forms.py`, `test_workflow_restart.py`, `test_fase_5_lotes_excolaboradores_exclusiones.py` | Cubierto |
| Carrera entre workers o revisores | P1 | `test_workflow_restart.py`, `test_evaluation_flow.py` | Cubierto |
| Caida, timeout o lease vencido | P1 | `test_workflow_restart.py` | Cubierto |
| Corrupcion durante lote o auditoria parcial | P1 | `test_fase_5_lotes_excolaboradores_exclusiones.py` | Cubierto |
| Migracion irreversible o restauracion corrupta | P0 | `test_fase_7_operaciones.py` | Cubierto |
| Instalacion no reproducible en Windows | P1 | entorno virtual limpio, `pip check`, smoke y `docs/INSTALACION_GREENFIELD_WINDOWS.md` | Cubierto |
| Dependencia obligatoria de Node.js o proveedor LLM | P1 | smoke sin proveedor y runtime Python documentado | Cubierto |

## Resultado

No quedan brechas tecnicas P0/P1 conocidas sin control. La aceptacion de usuarios, las politicas
corporativas y las decisiones `BIZ-001..010` permanecen como dependencias externas de fase 8.
