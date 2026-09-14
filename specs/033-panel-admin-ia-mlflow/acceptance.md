# Aceptación — SPEC-033

- **AC-033-001:** administrador ve el panel; otros roles reciben 403.
- **AC-033-002:** guardar actualiza SQLite, cifra la clave y rechaza CSRF, modelo inválido o versión
  obsoleta.
- **AC-033-003:** diagnóstico simulado actualiza la tarjeta y clasifica 401, 429, timeout y red sin
  filtrar la clave.
- **AC-033-004:** modo local no realiza red y sigue disponible como fallback.
- **AC-033-005:** el cliente LLM recibe solo texto sanitizado y toda evidencia se verifica contra
  el CV original; lo ambiguo deriva a revisión.
- **AC-033-006:** MLflow conserva runs padre/hijo con proveedor, modelo, nodos, tiempos y tokens,
  sin contenido ni secretos.
- **AC-033-007:** migración upgrade/downgrade y regresión completa pasan.
