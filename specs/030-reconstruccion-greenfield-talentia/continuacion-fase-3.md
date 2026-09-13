# Continuacion de trabajo - SPEC-030 fase 3

Fecha: 2026-09-13

Estado SDD: `VERIFICANDO`. La implementacion funcional de la fase 3 esta terminada, pero la fase no
debe declararse cerrada hasta completar nuevamente la regresion total y registrar su resultado.

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
- La suite completa fue iniciada, pero se interrumpio por solicitud expresa del propietario antes
  de obtener un resultado final. Ese intento no constituye evidencia aprobatoria.

## Lo que debe seguir

1. Sin modificar codigo, ejecutar nuevamente:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest-fase-3-final -p no:cacheprovider
   ```

2. Si la suite completa falla, determinar si es una regresion de fase 3 o el timeout intermitente de
   Streamlit ya documentado. Corregir solo regresiones atribuibles al cambio.
3. Registrar en `verification.md` el numero exacto de pruebas, advertencias y duracion de la corrida
   completa.
4. Actualizar la fila `Calidad y regresion` de `rubric-gap-review.md` para retirar la brecha de la
   puerta final solamente si la suite completa pasa.
5. Repetir `git diff --check`, revisar el commit remoto y confirmar que los Markdown locales
   `TalentIA_informacion_extraida_consolidada_v4.md` y `extraccion_talentia_imagenes (1).md`
   permanezcan sin seguimiento y fuera del commit.
6. Informar la fase 3 como terminada y solicitar aprobacion antes de comenzar la fase 4.

## Siguiente fase tras aprobacion

La fase 4 implementa formularios operativos de perfiles/versiones, postulaciones y carga de CV con
inicio/seguimiento de evaluacion, conservacion de datos ante errores, RBAC, IDOR e idempotencia. No
debe iniciarse hasta cerrar la verificacion anterior y recibir aprobacion expresa.
