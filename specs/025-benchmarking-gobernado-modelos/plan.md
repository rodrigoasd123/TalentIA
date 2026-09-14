# Plan — SPEC-025

## Enfoque

Mantener el grafo acotado, mover casos a un dataset JSON versionado, validar presupuesto previo y devolver resultados auditables. El ranking no muta settings.

## Componentes

| Componente | Cambio |
|---|---|
| `fixtures/benchmarks/*.json` | Suite sintética versionada |
| `model_benchmark_graph.py` | Detalle, hash, baseline y gate |
| esquemas/API/cliente/UI | Ejecución explícita y resultados |
| MLflow | Resumen sin contenido |

## Rollout y rollback

Endpoint experimental restringido. Rollback deshabilita la vista/endpoint sin afectar evaluación ATS.

## Verificación

Pruebas con modelos falsos para empate, fallo, JSON inválido, presupuesto, baseline, RBAC y ausencia de red.

## Plan R1 aprobado — Histórico y tablero comparativo

1. Persistir cada benchmark y su ranking metadata-only en SQLite, incluido el usuario iniciador y
   el identificador de run MLflow cuando exista.
2. Calcular tokens de entrada/salida/total, éxito, calidad, costo nullable y percentiles de
   latencia a partir de resultados por caso.
3. Exponer API paginada de histórico y detalle, protegida con `settings:read`.
4. Integrar indicadores y comparaciones en Configuración/Observabilidad sin activar modelos.
5. Conservar el benchmark actual como ejecución explícita con confirmación y máximo de cinco
   modelos.
6. Probar reproducibilidad, datos antiguos incompletos, RBAC, privacidad y MLflow opcional.

**Rollback R1:** retirar vistas/endpoints y revertir la tabla de históricos; el benchmark síncrono
existente continúa disponible sin cambiar el modelo activo.
