# SPEC-019 — Verificación

## Resultado

Verificación local completada antes de la publicación autorizada.

## Evidencia

- `python -m pytest -q --basetemp=.pytest-tmp-spec019-release`: **280 passed**.
- `python -m pytest tests/ats/test_talentia_consolidation.py -q`: **8 passed**.
- Smoke FastAPI con `TestClient`: `/health/live` respondió 200 y OpenAPI publicó
  el título `TalentIA`.
- Smoke Streamlit con `streamlit.testing.v1.AppTest`: 0 excepciones y pantalla
  principal TalentIA cargada.
- `python scripts/check_brand_identity.py`: identidad visible TalentIA validada.
- `python scripts/check_repository.py`: repositorio seguro, sin bases, secretos
  ni respaldos rastreados.
- `git diff --check`: sin espacios en blanco inválidos.

## Cobertura relevante

Las pruebas de consolidación cubren prioridad de `TALENTIA_*`, aliases heredados
sin filtrar valores, instalación nueva, adopción verificada de `vera.db`, base
oficial existente, conflicto de ambas bases, fallo de copia y migración Alembic
real hasta `head`.

## Limitaciones conocidas

El repositorio mantiene deuda histórica de lint fuera del alcance de esta spec;
los archivos nuevos de la consolidación pasan el lint dirigido. La suite completa
emite advertencias transitorias cuando pruebas históricas usan aliases `VERA_*`.
