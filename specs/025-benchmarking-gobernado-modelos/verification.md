# Verificación — SPEC-025

- Suite sintética con versión y hash, resultados por caso sin texto de respuesta y gate contra baseline.
- La API exige confirmación y entre uno y cinco modelos; no cambia el modelo activo.
- Las pruebas usan dobles y no realizan llamadas externas.
- Evidencia global: `310 passed`.

## Refinamiento R1 — 2026-09-13

- Histórico de benchmarks persistido con versión/hash de suite, usuario, baseline, ranking,
  resultados sin texto y vínculo MLflow.
- Ranking ampliado con errores, tokens de entrada/salida/total, p50/p95, calidad, éxito y costo
  estimado cuando el administrador declara tarifas.
- La ejecución exige confirmación explícita y nunca activa automáticamente el ganador.
- MLflow conserva métricas agregadas metadata-only, incluido costo estimado cuando está disponible.
- Suite focalizada: `36 passed`; suite global: `401 passed, 2 warnings`.
- Ruff, formato, migración reversible y puertas greenfield aprobadas.
