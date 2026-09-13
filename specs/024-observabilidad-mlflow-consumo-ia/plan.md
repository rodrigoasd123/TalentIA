# Plan — SPEC-024

## Enfoque

Mantener el decorador `ObservedLLMAdapter`, retirar autologging de contenido, persistir telemetría mediante repositorio/servicio y exponerla exclusivamente por API.

## Componentes

| Componente | Cambio |
|---|---|
| `mlflow_tracker.py` | Métricas metadata-only y costo nullable |
| `app/api/main.py` | Estado/uso autorizado; sin autologging invasivo |
| `ai_usage.py` | Cliente HTTP, nunca SQLite directo |
| migración/modelo | Persistencia compatible y downgrade |

## Rollout y rollback

Aplicar migración antes de API. MLflow puede desactivarse con variable. Rollback conserva ATS y permite downgrade explícito de la tabla.

## Verificación

Dobles MLflow inspeccionan parámetros registrados; pruebas aseguran ausencia de contenido/secretos, persistencia, RBAC y degradación.
