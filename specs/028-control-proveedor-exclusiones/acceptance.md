# Aceptación — SPEC-028

- **AC-028-001** `[FR-028-001..002, SEC-028-001]`: la lista filtrada contiene solo identificador mínimo, motivo, vigencia y última gestión; el CSV neutraliza fórmulas.
- **AC-028-002** `[FR-028-003..004]`: un lote Adecco clasifica duplicados/recontactables/nuevos sin fusionar ni rechazar personas.
- **AC-028-003** `[NFR-028-001, SEC-028-002]`: repetir el cruce produce el mismo resultado, no llama al LLM y registra auditoría.

**Evidencia (2026-09-12):** servicio determinístico, filtros, vigencia, endpoint, CSV neutralizado y panel; pruebas de reporte incluidas en 310 passed.
