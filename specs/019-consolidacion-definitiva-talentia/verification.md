# SPEC-019 — Verificación

## Resultado

Verificación local completada y revalidada el 11 de septiembre de 2026 antes
de la publicación autorizada.

## Evidencia

- `python -m pytest -q --basetemp=.pytest-tmp-spec019-final`: **280 passed**
  y 1 advertencia de deprecación externa de Starlette/AnyIO.
- `python -m pytest tests/ats/test_talentia_consolidation.py -q`: **8 passed**.
- Smoke FastAPI con `TestClient`: `/health/live` respondió 200 y OpenAPI publicó
  el título `TalentIA`.
- Smoke Streamlit con `streamlit.testing.v1.AppTest`: 0 excepciones y pantalla
  principal TalentIA cargada.
- `python scripts/check_brand_identity.py`: identidad visible TalentIA validada.
- `python scripts/check_repository.py`: repositorio seguro, sin bases, secretos
  ni respaldos rastreados.
- `git diff --check`: sin espacios en blanco inválidos.

Durante la revalidación final se corrigieron dos expectativas de edad que
dependían del calendario. Las pruebas ahora calculan el valor esperado con la
fecha actual y no volverán a fallar al cambiar de día o de año.

## Cobertura relevante

Las pruebas de consolidación cubren prioridad de `TALENTIA_*`, aliases heredados
sin filtrar valores, instalación nueva, adopción verificada de `vera.db`, base
oficial existente, conflicto de ambas bases, fallo de copia y migración Alembic
real hasta `head`.

## Limitaciones conocidas

El repositorio mantiene deuda histórica de lint fuera del alcance de esta spec;
los archivos nuevos de la consolidación pasan el lint dirigido. La suite completa
mantiene una advertencia de deprecación originada en `starlette.testclient` por el
alias `anyio.abc.BlockingPortal`; no afecta el resultado funcional.
