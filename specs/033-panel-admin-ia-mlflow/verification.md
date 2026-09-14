# Verificación — SPEC-033

Estado: VERIFICADA

## Evidencia funcional

- Pruebas administrativas, cifrado, diagnóstico, cliente LLM, evidencia y MLflow: `7 passed`.
- Regresión focalizada de workflow, evaluación y observabilidad: `20 passed`.
- Suite completa: `110 passed, 3 warnings in 193.91s`.
- Revisión visual en navegador: panel administrativo, badge global, diagnóstico, selectores,
  credenciales write-only, ajustes y acceso a MLflow renderizan correctamente en escritorio.

## Migración SQLite reversible

- Upgrade a `0005_configuracion_ia`: correcto.
- Downgrade a `0004_seguridad`: correcto; tabla retirada.
- Nuevo upgrade a `head`: correcto.

## Puertas de calidad

- `python -m ruff format --check src/talentia migrations_greenfield tests/greenfield`:
  `97 files already formatted`.
- `python -m mypy src/talentia`: `Success: no issues found in 70 source files`.
- `python scripts/check_repository.py`: `Repositorio seguro: 374 archivos revisados`.
- `git diff --check`: correcto.
- Ruff sobre los archivos del alcance, excluyendo `paginas.py`: `All checks passed!`.

El comando Ruff global reporta exclusivamente `S110` en
`src/talentia/web/routes/paginas.py:148`. Ese archivo contiene una modificación local previa del
usuario, ajena a SPEC-033; no fue alterado ni se incluye en el commit para preservar trabajo
existente.

## Privacidad y degradación

- Las claves se guardan cifradas y nunca aparecen en DTO público, HTML, logs ni trazas.
- Las llamadas externas ocurren únicamente después de sanitización y bloqueo de prompt injection.
- MLflow recibe identificadores, modelo, estados, latencias y métricas de tokens; no recibe CV,
  prompts, respuestas ni PII.
- La caída de proveedor o MLflow conserva el modo manual y deriva a revisión humana sin rechazo
  automático.

## Advertencias no bloqueantes

- Starlette/AnyIO y LangGraph emitieron advertencias de deprecación de dependencias.
- Pytest no pudo escribir `.pytest_cache` por permisos de OneDrive; `--basetemp` permitió ejecutar
  la suite completa sin afectar el resultado.
