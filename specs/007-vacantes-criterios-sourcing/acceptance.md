# Aceptación — SPEC-007

## AC-007-001 — Aprobación de criterios

Una vacante solo puede quedar abierta cuando sus criterios fueron aprobados explícitamente; cambiar los criterios incrementa la versión y devuelve la vacante a borrador.

**Evidencia:** `test_editar_criterios_reabre_solo_con_aprobacion_humana`.

## AC-007-002 — Pesos válidos

Los pesos de evaluación deben sumar cien y el dominio rechaza configuraciones inválidas.

**Evidencia:** `test_los_pesos_deben_sumar_cien`.

## AC-007-003 — Sourcing bajo control humano

La respuesta de sourcing contiene una consulta para copiar manualmente y declara que no abre LinkedIn.

**Evidencia:** `test_sourcing_solo_devuelve_una_consulta_para_ejecucion_manual`.
