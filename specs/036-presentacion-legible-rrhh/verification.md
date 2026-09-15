# Verificacion - SPEC-036

Fecha: 2026-09-14.

- Las evaluaciones muestran `Revisar evaluacion`, candidato, vacante y estado humano; el ID permanece
  solamente en el `href` interno.
- Las postulaciones muestran persona candidata, vacante y `codigo · nombre` del cliente, sin columna
  de UUID.
- Los formularios de candidato, lote, comprobacion de excolaborador y reporte de exclusiones muestran
  `TCS · TCS`; mantienen el ID como valor del `option` para autorizacion y persistencia.
- Los filtros de Ex-TCS y exclusiones se ejecutan desde un archivo JavaScript local autorizado por CSP.
- Pruebas focalizadas iniciales: 30 aprobadas y 1 regresion visual detectada; se corrigio el titulo de
  exclusiones conservando el contrato `Registros actuales`.
- `pytest -q tests/greenfield/test_operational_panels.py tests/greenfield/test_operational_forms.py
  tests/greenfield/test_evaluation_flow.py tests/greenfield/test_frontend_visual.py
  --basetemp=tmp/pytest-presentacion-rrhh-2`: 31 aprobadas, 3 advertencias sin impacto funcional.
- `ruff check src/talentia ...`: aprobado.
- `ruff format --check src/talentia ...`: 79 archivos formateados.
- `mypy src/talentia`: 76 archivos sin errores.
- `pytest -q --basetemp=tmp/pytest-presentacion-rrhh-full`: 126 aprobadas, 3 advertencias sin impacto
  funcional.
- `python scripts/check_repository.py`: repositorio seguro, 510 archivos revisados.
- `git diff --check`: aprobado.

Resultado: FR-036-001 a FR-036-004, NFR-036-001 y SEC-036-001 satisfechos.
