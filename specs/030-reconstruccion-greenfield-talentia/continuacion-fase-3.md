# Continuacion de trabajo - SPEC-030 fase 3

Fecha: 2026-09-13

Estado SDD: `VERIFICANDO`. La implementacion y las puertas tecnicas de la fase 3 estan terminadas. La
fase permanece en este estado hasta la aprobacion expresa del propietario para iniciar la fase 4.

## Punto exacto alcanzado

- Se implemento la pagina `/evaluaciones/{id}` con datos de candidatura y perfil, requisitos,
  veredictos, explicaciones y evidencia navegable mediante pagina, posiciones y fragmento minimo.
- Se implemento el formulario web para aceptar, corregir o rechazar sugerencias con justificacion
  obligatoria.
- Una decision `corregida` exige al menos una correccion; se cubrio el caso
  `nivel_ingles = B2 verificado` y su visualizacion en el historial.
- La resolucion de revision es atomica mediante estado/version. Dos revisores concurrentes generan
  una sola decision y un solo evento de auditoria; el segundo recibe conflicto.
- Se aplicaron CSRF, RBAC y alcance por cliente tanto en lectura como en escritura.
- Se implementaron `/trabajos/{id}` y `/fragmentos/trabajos/{id}` con polling HTMX y estados
  pendiente, procesando, revision/completado y error seguro.
- Los listados existentes enlazan evaluaciones, revisiones y trabajos con sus nuevas pantallas.
- No se agrego ninguna migracion ni se resolvio una decision `BIZ-001..010`.

## Verificacion ya ejecutada

- `python -m pytest -q tests/greenfield/test_evaluation_flow.py`: 7 aprobadas, 2 advertencias.
- `python -m pytest -q tests/greenfield`: 61 aprobadas, 2 advertencias.
- `python -m ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `python -m ruff format --check src/talentia migrations_greenfield tests/greenfield`: 78 archivos
  conformes.
- `python -m mypy src/talentia`: 60 archivos sin observaciones.
- `python scripts/check_repository.py`: 516 archivos revisados, repositorio seguro.
- `python -m pytest -q`: 371 aprobadas, 2 advertencias, en 391,78 segundos.

## Lo que debe seguir

1. Subir el cierre documental de verificacion a `codex/rubrica-greenfield-talentia`.
2. Informar los resultados exactos y confirmar que `main` no fue modificado.
3. Esperar aprobacion expresa antes de comenzar la fase 4.

## Siguiente fase tras aprobacion

La fase 4 implementa formularios operativos de perfiles/versiones, postulaciones y carga de CV con
inicio/seguimiento de evaluacion, conservacion de datos ante errores, RBAC, IDOR e idempotencia. No
debe iniciarse hasta cerrar la verificacion anterior y recibir aprobacion expresa.
