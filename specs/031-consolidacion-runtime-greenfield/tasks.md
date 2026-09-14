# Tareas — SPEC-031

- [x] **T-001 — Asegurar fuente y rollback**
  - Cubre: NFR-003, SEC-001, AC-004
  - Archivos: Git
  - Verificacion: commit inicial y tag existentes
  - Dependencias: ninguna

- [x] **T-002 — Inventariar runtimes**
  - Cubre: FR-002, FR-004, AC-002
  - Archivos: `inventory.md`
  - Verificacion: imports y archivos versionados enumerados
  - Dependencias: T-001

- [x] **T-003 — Retirar consumidores heredados**
  - Cubre: FR-001, FR-002, SEC-002, AC-001, AC-002
  - Archivos: arboles y scripts clasificados REMOVE
  - Verificacion: busqueda global sin imports/entrypoints activos
  - Dependencias: T-002

- [x] **T-004 — Normalizar runtime y documentacion**
  - Cubre: FR-001, FR-003, NFR-001, NFR-002, AC-001, AC-003
  - Archivos: `pyproject.toml`, `requirements.txt`, `Dockerfile`, CI, README y scripts
  - Verificacion: controles declarados en el plan
  - Dependencias: T-003

- [x] **T-005 — Ejecutar regresion y documentar evidencia**
  - Cubre: FR-004, NFR-002, AC-004
  - Archivos: `verification.md`
  - Verificacion: suite y migracion desde cero
  - Dependencias: T-004

- [x] **T-006 — Estabilizar extras opcionales en CI**
  - Cubre: FR-003, NFR-001, NFR-002, AC-003, AC-004
  - Archivos: `constraints-ci.txt`, `.github/workflows/ci.yml`, `verification.md`
  - Verificacion: instalacion Python 3.12 limpia, `pip check` y workflow remoto verde
  - Dependencias: T-005

## Puertas de salida

- [x] Todos los requisitos obligatorios estan cubiertos.
- [x] No quedan bloqueantes de alcance.
- [x] Existe estrategia para fallos y reversion.
