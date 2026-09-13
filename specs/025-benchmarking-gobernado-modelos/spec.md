# SPEC-025 — Benchmarking gobernado de modelos

- **Estado:** VERIFIED
- **Fecha:** 2026-09-12
- **Owner:** Product and engineering

## Problema

El benchmark reciente ejecuta tres ejemplos fijos y ordena resultados, pero no tiene dataset TalentIA versionado, baseline, quality gate, límites operativos ni activación controlada del ganador.

## Alcance

- Suite sintética versionada de extracción/evaluación segura.
- Ejecución explícita por modelos seleccionados, con límite de llamadas.
- Resultados por caso y agregados: exactitud, validez, errores, tokens y latencia.
- Comparación con baseline y veredicto `passed` sin activar automáticamente modelos.
- Registro agregado metadata-only en MLflow.

## Fuera de alcance

- Probar con CV reales, evaluación humana automática o cambiar producción sin aprobación.

## Requisitos

- **FR-025-001:** todos los modelos reciben exactamente la misma suite/version y parámetros reproducibles.
- **FR-025-002:** el resultado incluye detalle por caso, agregado, ranking, suite hash y versión del grafo.
- **FR-025-003:** un quality gate compara calidad, errores y presupuesto con un baseline elegido.
- **FR-025-004:** ejecutar o adoptar un resultado requiere acción administrativa explícita; el benchmark nunca cambia el modelo por sí mismo.
- **NFR-025-001:** la ejecución limita modelos, casos, timeout y costo estimado antes de comenzar.
- **NFR-025-002:** tests automatizados usan dobles sin red.
- **SEC-025-001:** solo datos sintéticos aprobados llegan a proveedores y no se persiste su contenido en trazas.
- **SEC-025-002:** solo `settings:write` ejecuta benchmarks.

## Riesgos

- Hasta 90 llamadas por defecto: se exige selección explícita y máximo seguro.
- Métrica exacta demasiado estrecha: el piloto declara sus límites y no decide contrataciones.
- Sin preguntas bloqueantes.
