# Plan — SPEC-020

1. Crear helpers puros para componer filas, filtrar y exportar CSV seguro.
2. Reorganizar `ats_frontend/views/candidates.py` alrededor de la tabla general.
3. Integrar selección de fila, alta y edición mediante los contratos API existentes.
4. Aplicar RBAC antes de construir columnas sensibles y mantener estados por postulación.
5. Añadir pruebas unitarias de filtros, columnas, CSV y payload editable.
6. Ejecutar lint, pruebas focales, smoke Streamlit y regresión completa.
7. Registrar resultados, limitaciones y rollback en `verification.md`.

No se modifica el esquema SQLite ni se introduce un endpoint nuevo: los contratos
de SPEC-018 ya proporcionan alta, listado, consulta y actualización con versión.
