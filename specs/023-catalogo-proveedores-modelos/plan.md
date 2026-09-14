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

## Plan R1 aprobado — Catálogo administrable

1. Añadir tablas SQLite para proveedores y modelos, con versión de concurrencia, estados y
   credencial cifrada; sembrar el catálogo incorporado de manera idempotente.
2. Implementar un almacén de catálogo que combine registros del sistema y personalizados, valide
   URLs contra SSRF y resuelva un modelo al adaptador/credencial correctos.
3. Mantener `llm.model` como selección activa compatible y hacer que fábrica, prueba de conexión y
   benchmark resuelvan modelos mediante el catálogo persistido.
4. Exponer API RBAC para alta y actualización sin borrado físico, con secretos write-only.
5. Extender Configuración en Streamlit con formularios administrativos y manejo de versiones.
6. Probar migración upgrade/downgrade, cifrado, SSRF, RBAC, concurrencia, compatibilidad y fallback.

**Rollback R1:** revertir la migración y el código; `runtime_settings` conserva el modelo y las
credenciales previas, por lo que el catálogo estático continúa operativo.
