# Plan — SPEC-023

## Enfoque y componentes

Conservar `LLMPort`, unificar catálogo/fábrica/settings y hacer que cada adaptador reciba modelo y credencial explícitos.

| Componente | Cambio |
|---|---|
| `model_catalog.py` | Catálogo por proveedor/capacidad |
| `factory.py` y adaptadores | Respetar modelo/clave seleccionados |
| `settings_store.py` y API | Credencial OpenAI cifrada y autorizada |
| manifests | Dependencias directas consistentes |

## Flujo y seguridad

Modelo → proveedor validado → credencial propia → adaptador observado → salida estructurada o revisión. Los secretos se enmascaran y el mock conserva la operación local.

## Rollout, rollback y verificación

Cambio aditivo. Rollback: seleccionar `mock` o desactivar proveedor; no eliminar claves heredadas. Probar catálogo, modelo solicitado, separación de claves, RBAC, proveedor caído e instalación.
