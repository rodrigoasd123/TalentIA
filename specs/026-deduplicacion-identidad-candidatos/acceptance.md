# Aceptación — SPEC-026

- **AC-026-001** `[FR-026-001..003]`: dado un correo/documento existente, el preflight alerta antes del CV y muestra procesos previos sin crear otra identidad.
- **AC-026-002** `[FR-026-001, SEC-026-002]`: dado un nombre parecido sin identificador fuerte, se marca posible duplicado y nunca se fusiona automáticamente.
- **AC-026-003** `[FR-026-002, SEC-026-001]`: dado un rol sin PII, el historial se devuelve enmascarado y auditado.

**Evidencia (2026-09-12):** pruebas por DNI y nombre normalizado, más preflight API con historial enmascarado; suite completa 310 passed.

- **AC-026-004:** una coincidencia telefónica se clasifica probable y exige confirmación humana
  explícita para crear una identidad separada.
- **AC-026-005:** una coincidencia situada después de 200 registros se encuentra igualmente.
- **AC-026-006:** la evidencia visible está enmascarada y muestra criterio, estado, fecha y
  reclutador; la confirmación queda auditada.
