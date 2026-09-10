# Tareas — SPEC-005

- [x] **T-001 — Foundation de migraciones reproducible**
  - Cubre: NFR-001, NFR-006
  - Archivos: `alembic.ini`, `migrations/`, dependencias, sesión y documentación
  - Verificación: `alembic upgrade head` sobre una base temporal
  - Dependencias: ninguna

- [x] **T-002 — Modelo de datos de importación y privacidad**
  - Cubre: FR-001, FR-005, FR-013, SEC-010, AC-001, AC-003, AC-006
  - Archivos: dominio, modelos SQLAlchemy, repositorios y migración SPEC-005
  - Verificación: pruebas de persistencia SQLite y upgrade Alembic
  - Dependencias: T-001

- [x] **T-003 — Adaptador CSV/XLSX y mapeo**
  - Cubre: FR-002–FR-005, NFR-002, NFR-007
  - Archivos: `app/infrastructure/imports/`, configuración y dependencias
  - Verificación: pruebas unitarias con CSV/XLSX ficticios y entradas hostiles
  - Dependencias: T-002

- [x] **T-004 — Clasificación, preview y confirmación transaccional**
  - Cubre: FR-006–FR-014, NFR-003, NFR-005, SEC-005–SEC-008
  - Archivos: caso de uso, puertos, repositorios y auditoría
  - Verificación: pruebas de staging, duplicados, idempotencia y rollback
  - Dependencias: T-003

- [x] **T-005 — API autorizada y contratos**
  - Cubre: FR-001–FR-014, SEC-001, AC-001–AC-008
  - Archivos: esquemas, rutas y pruebas API
  - Verificación: pruebas positivas y negativas por permiso
  - Dependencias: T-004

- [x] **T-006 — Interfaz Streamlit de importación**
  - Cubre: FR-003, FR-007, FR-009, NFR-004
  - Archivos: cliente HTTP y página `Historical Import`
  - Verificación: importación estática y smoke del frontend
  - Dependencias: T-005

- [x] **T-007 — Calidad, documentación y evidencia**
  - Cubre: NFR-006–NFR-008, SEC-009
  - Archivos: README, ADR, CI, SPEC y pruebas
  - Verificación: pytest, Ruff, MyPy práctico, escáner de repositorio
  - Dependencias: T-001–T-006

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos por tareas.
- [x] No quedan bloqueantes.
- [x] Existe estrategia para fallos y reversión.
