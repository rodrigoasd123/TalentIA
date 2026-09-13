# Aceptación — SPEC-029

- **AC-029-001** `[FR-029-001..004]`: con datos sintéticos, el panel muestra fórmula, numerador/denominador y filtros coherentes por vacante/fuente/periodo.
- **AC-029-002** `[NFR-029-001, SEC-029-001]`: las métricas coinciden con SQLite/auditoría, no llaman al LLM y no contienen PII.
- **AC-029-003** `[NFR-029-002]`: sin datos, el panel indica muestra insuficiente y no afirma horas ahorradas ni ROI.

**Evidencia (2026-09-12):** agregación por vacante/fuente/periodo, fórmula y parámetros visibles, sin LLM ni afirmación de ROI; pruebas incluidas en 310 passed.
