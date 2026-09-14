# Plan — SPEC-033

1. Añadir configuración cifrada persistente y migración reversible.
2. Crear catálogo, diagnóstico seguro y cliente LLM gobernado.
3. Añadir panel, fragmento HTMX, badge global y JavaScript vanilla.
4. Conectar el worker a la configuración compartida y verificar evidencia externa.
5. Instrumentar MLflow de forma opcional y metadata-only.
6. Probar RBAC, CSRF, cifrado, concurrencia, errores, privacidad, trazas y regresión.

La dependencia cryptography se declara directamente. MLflow permanece en el extra benchmark y
su caída nunca bloquea una evaluación.
