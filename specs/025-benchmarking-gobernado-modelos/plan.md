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
