# Verificación — SPEC-024

- Se retiró el autologging que podía capturar contenido.
- Streamlit consulta `/api/v1/observability/llm`; no abre la base SQLite.
- La caída o desactivación de MLflow no bloquea el flujo de negocio.
- Evidencia global: `310 passed`, incluida `test_mlflow_observability.py`.

## Refinamiento R1 — 2026-09-13

- Cada workflow persiste correlación, estado, tokens y una secuencia metadata-only de nodos con
  versión, intentos, duración, estado y error tipado.
- MLflow recibe un run padre por proceso y runs hijos por nodo cuando está habilitado; si falla o
  está deshabilitado, el proceso continúa y la consulta local permanece disponible.
- La API paginada y el panel permiten navegar proceso → grafo → nodo y muestran tokens de entrada,
  salida y total sin prompts, respuestas, CV, secretos ni PII.
- Se añadió acceso directo a la URL configurada de MLflow y se verificó RBAC fuera del laboratorio.
- Suite focalizada: `36 passed`; suite global: `401 passed, 2 warnings en 835.43 s`.
- Migración reversible y puertas greenfield aprobadas; escáner: `547 archivos revisados`.
