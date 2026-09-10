# Tareas — SPEC-007

- [x] **T-007-001 — Modelar vacante y criterios válidos**
  - Cubre: FR-007-001, FR-007-002, AC-007-002
  - Archivos: `app/domain/entities.py`, `app/domain/value_objects.py`
  - Verificación: `tests/ats/test_domain_rules.py`
  - Dependencias: ninguna
- [x] **T-007-002 — Implementar aprobación y versionado**
  - Cubre: FR-007-002, FR-007-004, AC-007-001
  - Archivos: dominio, repositorios y rutas de jobs
  - Verificación: `test_editar_criterios_reabre_solo_con_aprobacion_humana`
  - Dependencias: T-007-001
- [x] **T-007-003 — Exponer gestión y sourcing manual**
  - Cubre: FR-007-001, FR-007-003, AC-007-001, AC-007-003
  - Archivos: `app/api/v1/routes/operations.py`, `ats_frontend/pages/2_Vacantes.py`
  - Verificación: pruebas API y smoke de interfaz
  - Dependencias: T-007-002

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes.
- [x] No existe automatización externa que requiera reversión.
