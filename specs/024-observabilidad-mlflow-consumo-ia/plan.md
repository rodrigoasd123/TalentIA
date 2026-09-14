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

## Plan R1 aprobado — Trazas de procesos

1. Enriquecer el estado del grafo con registros metadata-only por nodo: orden, versión, estado,
   intentos, duración y delta de tokens.
2. Persistir dichos registros junto al workflow existente mediante una columna JSON reversible,
   evitando una segunda fuente de verdad.
3. Registrar en MLflow un run padre por workflow y runs hijos por nodo, sin prompts, respuestas,
   CV, PII ni mensajes de excepción.
4. Exponer listados paginados y detalle por workflow usando la persistencia local; incorporar
   topología derivada del grafo real y enlace seguro a MLflow.
5. Extender el panel para filtros, totales, desglose de tokens y navegación de nodos.
6. Probar privacidad, RBAC, degradación de MLflow, persistencia y paginación.

**Rollback R1:** la columna de detalle es aditiva; el endpoint agregado original y los workflows
previos sin detalle continúan renderizando sus tiempos agregados.
