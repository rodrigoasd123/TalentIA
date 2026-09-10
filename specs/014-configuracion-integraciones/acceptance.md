# Aceptación — SPEC-014

## AC-014-001 — Secreto protegido

Un secreto se persiste cifrado, dos cifrados del mismo valor difieren y la API nunca devuelve el valor completo.

**Evidencia:** pruebas de cifrado y settings en `test_config_and_graph.py`.

## AC-014-002 — Permiso administrativo

Fuera del laboratorio, únicamente el permiso correspondiente modifica configuración; el resto recibe denegación.

**Evidencia:** pruebas RBAC en `test_security_endpoints.py`.

## AC-014-003 — Operación degradada

Sin proveedor externo el ATS conserva vacantes, postulaciones, pipeline, revisión y auditoría; una evaluación fallida deriva a revisión.

**Evidencia:** prueba de fallo del proveedor y smoke con mock.
