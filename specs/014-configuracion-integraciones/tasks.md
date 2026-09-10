# Tareas — SPEC-014

- [x] **T-014-001 — Definir catálogo y validación de settings**
  - Cubre: FR-014-003, AC-014-002
  - Archivos: `app/core/config.py`, contratos y rutas de configuración
  - Verificación: pruebas de claves permitidas y RBAC
  - Dependencias: ninguna
- [x] **T-014-002 — Cifrar y enmascarar secretos**
  - Cubre: FR-014-002, AC-014-001
  - Archivos: `app/core/crypto.py`, `settings_store.py`
  - Verificación: cifrado no determinista y respuesta enmascarada
  - Dependencias: T-014-001
- [x] **T-014-003 — Desacoplar proveedores y mock**
  - Cubre: FR-014-001, AC-014-003
  - Archivos: factory y adaptadores LLM/Gmail
  - Verificación: evaluación sin red y proveedor caído
  - Dependencias: T-014-001
- [x] **T-014-004 — Mostrar estado sin secretos**
  - Cubre: FR-014-002, FR-014-003, AC-014-001, AC-014-002
  - Archivos: rutas `/config/*`, `ats_frontend/pages/1_Configuracion.py`
  - Verificación: pruebas API y smoke de configuración
  - Dependencias: T-014-002, T-014-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes del piloto.
- [x] Las integraciones pueden desactivarse sin detener el ATS.
