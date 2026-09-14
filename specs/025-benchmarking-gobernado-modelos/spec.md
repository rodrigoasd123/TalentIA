# SPEC-025 — Benchmarking gobernado de modelos

- **Estado:** VERIFICANDO (refinamiento R2)
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

## Refinamiento R1 — Indicadores comparativos en el panel administrativo

> Refinamiento aprobado por el propietario el 2026-09-13.

### Necesidad

El benchmark actual devuelve un ranking al terminar una ejecución. Administración necesita revisar
históricos y comparar de forma visual qué modelos ofrecen el mejor equilibrio entre calidad,
errores, latencia, tokens y costo conocido.

### Alcance propuesto

- Vista de benchmark integrada al panel administrativo.
- Selección exclusiva de modelos habilitados del catálogo administrable.
- Indicadores agregados y detalle por caso sintético sin mostrar prompts ni respuestas.
- Histórico de ejecuciones con suite, hash, versión del grafo, baseline, fecha y responsable.
- Comparación visual de calidad, tasa de éxito, errores, p50/p95 de latencia, tokens de entrada,
  salida y total, y costo conocido/no disponible.
- Enlace desde cada ejecución a su run correspondiente en MLflow cuando esté disponible.
- Recomendación informativa basada en reglas transparentes; nunca activación automática.

### Requisitos nuevos

- **FR-025-005:** el panel debe mostrar el histórico paginado de benchmarks y permitir filtrar por
  fecha, modelo, proveedor, suite y resultado del quality gate.
- **FR-025-006:** cada comparación debe mostrar calidad, éxito, errores, latencia p50/p95, tokens de
  entrada/salida/total y costo conocido/no disponible con unidades claras.
- **FR-025-007:** los resultados deben conservar proveedor/modelo exactos, versión de suite, hash,
  versión de grafo, baseline y usuario que inició la ejecución.
- **FR-025-008:** el panel puede destacar el mejor resultado según reglas visibles, pero nunca debe
  cambiar una asignación o activar un modelo sin una acción administrativa independiente.
- **FR-025-009:** una ejecución histórica debe enlazar a MLflow solo mediante una URL segura
  construida por el backend.
- **NFR-025-003:** los cálculos de ranking e indicadores deben ser reproducibles para los mismos
  resultados persistidos.
- **NFR-025-004:** el panel debe funcionar con MLflow deshabilitado usando los resultados agregados
  persistidos localmente.
- **SEC-025-003:** el histórico y sus enlaces requieren `settings:read`; ejecutar benchmark sigue
  requiriendo `settings:write` y confirmación explícita de consumo.
- **SEC-025-004:** no se persistirán ni mostrarán prompts, respuestas o contenido de los casos,
  únicamente identificadores y métricas agregadas permitidas.

### Compatibilidad

- La suite sintética, sus límites y el endpoint actual se conservan.
- Los resultados previos que carezcan de una métrica nueva se mostrarán como “no disponible”.
- La falta de una tarifa no debe excluir un modelo ni convertir su costo en cero.

## Refinamiento R2 — Etiquetas independientes (2026-09-14)

El benchmark debe fallar si falta `requisito` o las etiquetas independientes de extracción y
veredicto. Debe informar acuerdo contra etiquetas, falso avance y falso descarte. El requisito ya
no puede derivarse de la habilidad encontrada en el mismo CV. Aprobado por la orden de ejecutar el
documento de pendientes.
