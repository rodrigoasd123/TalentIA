# Aceptacion - SPEC-034

- **AC-034-001** `[FR-034-001..003]`: dos CV validos generan dos fichas con los campos encontrados,
  documentos y extracciones; repetir una identidad no duplica ni sobrescribe la ficha.
- **AC-034-002** `[FR-034-004..005, SEC-034-002]`: una identidad incluida en ex-TCS y vetados muestra
  ambas alertas y las conserva en trazabilidad sin cambiar el estado del candidato.
- **AC-034-003** `[NFR-034-001, SEC-034-001]`: un CV con prompt injection queda en revision sin crear
  una ficha y el flujo no requiere red.
- **AC-034-004** `[SEC-034-003]`: CSRF, permisos y alcance de cliente siguen aplicando al formulario.
