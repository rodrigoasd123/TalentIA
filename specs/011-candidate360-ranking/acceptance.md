# Aceptación — SPEC-011

## AC-011-001 — Vista consolidada autorizada

Un actor autorizado consulta CV, estado, evaluaciones y trazabilidad permitida; el acceso personal queda sujeto a rol y auditoría.

**Evidencia:** contratos Candidate 360 y pruebas de seguridad/auditoría.

## AC-011-002 — Comparación contextual

La comparación explica diferencias por dimensión y rechaza candidaturas pertenecientes a vacantes distintas.

**Evidencia:** `test_no_se_comparan_candidaturas_de_vacantes_distintas` y pruebas de comparación explicable.

## AC-011-003 — Ranking gobernado

Una postulación que incumple filtros obligatorios queda después de las elegibles aunque su score numérico sea mayor.

**Evidencia:** `test_quien_no_supera_los_filtros_queda_al_final_del_ranking`.
