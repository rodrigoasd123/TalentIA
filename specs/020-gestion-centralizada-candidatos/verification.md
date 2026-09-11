# Verificación — SPEC-020

## Resultado

SPEC-020 verificada localmente el 11 de septiembre de 2026.

## Evidencia reproducible

- `pytest tests/ats/test_candidate_table.py -q`: **5 passed**.
- `pytest tests/ats/test_candidate_table.py tests/ats/test_candidate_general_database.py -q`:
  **10 passed** después de incorporar el smoke de Streamlit.
- `pytest -q --basetemp=.pytest-tmp-spec020-release`: **285 passed** en la
  ejecución final, con una advertencia externa de Starlette/AnyIO.
- `ruff check ats_frontend tests/ats/test_candidate_table.py`: correcto.
- `python -m compileall -q app ats_frontend`: correcto.
- `python scripts/check_brand_identity.py`: identidad TalentIA verificada.
- `python scripts/check_repository.py`: repositorio seguro.
- Smoke con `streamlit.testing.v1.AppTest`: navegación a Candidatos, tabla general
  y apertura de Nuevo candidato sin excepciones ni red.
- Verificación visual en `http://127.0.0.1:8502/candidates`: nueve filas ficticias,
  filtros responsivos, selección de fila, formulario completo y guardado real por API.

## Criterios cubiertos

- AC-020-001: tabla general, conteo, búsqueda y filtros visibles.
- AC-020-002: selección y guardado por API con `expected_version` existente.
- AC-020-003: alta integrada en la misma pantalla.
- AC-020-004: estados por vacante visibles y no editables en la ficha.
- AC-020-005: exportación de filas filtradas, sin identificadores internos y con
  neutralización de fórmulas; columnas PII ausentes sin permiso.
- AC-020-006: helpers puros, smoke Streamlit y regresión completa.

## Datos y rollback

No se modificó el esquema de SQLite. La validación manual escribió únicamente en
la base local ignorada de la branch y utilizó candidatos ficticios del seed. El
rollback consiste en restaurar la vista anterior y retirar
`talentia/candidate_table.py`; los datos existentes siguen siendo compatibles.

## Limitación conocida

La tabla permite editar una ficha seleccionada, no varias filas en una sola
transacción. La edición masiva permanece fuera del alcance aprobado.
