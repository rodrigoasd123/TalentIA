# SPEC-028 — Control de proveedor y listas de exclusión

- **Estado:** VERIFIED
- **Fuente:** Documento TCS, agentes de exclusión y modelo con Adecco.

## Problema y alcance

Adecco remite CV sin acceso al histórico, provocando duplicidades y recontactos. TalentIA debe generar una lista mínima de exclusión y validar lotes antes de que lleguen a RR. HH.

## Requisitos

- **FR-028-001:** generar una lista de exclusión con identificador pseudónimo, motivo operativo, vigencia y última gestión, sin exponer historial completo.
- **FR-028-002:** permitir filtrar por proveedor, vacante, estado y vigencia y exportar CSV seguro.
- **FR-028-003:** validar un lote del proveedor contra candidatos existentes y clasificar exacto, posible, recontactable o nuevo.
- **FR-028-004:** reglas de vigencia/recontacto son configurables y la decisión final es humana.
- **NFR-028-001:** cruce y exportación son deterministas, idempotentes y sin LLM.
- **SEC-028-001:** exportar solo datos mínimos autorizados; neutralizar fórmulas y auditar descarga/validación.
- **SEC-028-002:** la exclusión nunca usa atributos protegidos ni equivale a rechazo laboral automático.

## Fuera de alcance

Portal externo de Adecco, envío automático o penalizaciones contractuales. Sin preguntas bloqueantes.
