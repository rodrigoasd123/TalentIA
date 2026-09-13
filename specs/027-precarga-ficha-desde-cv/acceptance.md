# Aceptación — SPEC-027

- **AC-027-001** `[FR-027-001..004]`: dado un CV sintético, se muestran únicamente datos presentes con confianza/procedencia y ningún campo cambia antes de confirmar.
- **AC-027-002** `[FR-027-002, SEC-027-002]`: al aceptar dos sugerencias y corregir una, solo esos campos se guardan y la auditoría registra fuente/versión.
- **AC-027-003** `[NFR-027-001, SEC-027-001]`: ante extracción fallida o rol insuficiente, se mantiene carga manual y no se revelan datos.

**Evidencia (2026-09-12):** extracción persistida, campos editables/seleccionables en Candidate 360, control de versión y evento de auditoría; suite completa 310 passed.
