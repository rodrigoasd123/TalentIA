# Verificación — SPEC-024

- Se retiró el autologging que podía capturar contenido.
- Streamlit consulta `/api/v1/observability/llm`; no abre la base SQLite.
- La caída o desactivación de MLflow no bloquea el flujo de negocio.
- Evidencia global: `310 passed`, incluida `test_mlflow_observability.py`.
