# Verificación — SPEC-005

## Entorno

- Fecha: 2026-09-10
- Revisión/commit base: `436c4e6` con cambios de trabajo de SPEC-005
- Rama: `main`
- Plataforma: Windows, Python 3.12.2, SQLite

## Evidencia por criterio

| AC | Requisitos | Evidencia | Resultado |
|---|---|---|---|
| AC-001 | FR-001, FR-002, FR-011, NFR-007, SEC-002–004, SEC-010 | `test_importa_candidato_restringido_y_es_idempotente`, pruebas de macro/objeto activo, encabezados duplicados y scanner inyectable | APROBADO |
| AC-002 | FR-003, FR-004, NFR-002, NFR-004 | selección de hoja, sugerencias, mapeo/plantillas por API y AppTest Streamlit sin excepciones | APROBADO |
| AC-003 | FR-005, FR-013, NFR-003, NFR-008, SEC-005 | staging persistente, paginación, logs solo con IDs/conteos/duración y prueba nombre-only sin Candidate | APROBADO |
| AC-004 | FR-006–008, SEC-007 | clasificación fuerte por email/teléfono/documento, ambigüedad name-only y preview enmascarado para auditor | APROBADO |
| AC-005 | FR-009–011, NFR-005, SEC-001, SEC-007–008 | permiso HR, idempotencia, versión 409, unicidad en DB y rollback provocado después de crear Candidate | APROBADO |
| AC-006 | FR-004, FR-008, SEC-006, SEC-008 | candidato nuevo queda `restricted_review`/`unknown`; `can_be_processed` es falso | APROBADO |
| AC-007 | FR-012, SEC-005, SEC-006, SEC-009 | CSV de errores sin PII de origen y neutralización de fórmulas | APROBADO |
| AC-008 | FR-013, FR-014, SEC-001, SEC-005 | cancelación denegada a recruiter, autorizada a HR y evento encadenado `import.cancelled` | APROBADO |

## Comandos ejecutados

| Comando | Resultado | Observaciones |
|---|---|---|
| `python -m pytest tests/ats/test_historical_import.py -q` | 11 aprobadas | Incluye fallos, permisos, privacidad, XLSX, selección de hoja, rollback e idempotencia. |
| `python -m pytest -q` | 266 aprobadas | Regresión completa anterior al último test aislado del hook antimalware; ese test está incluido en el foco de 11. |
| pytest de `test_application_flow.py` y `test_config_and_graph.py` | 46 aprobadas | Regresión focal posterior al bloqueo de comunicaciones para candidatos restringidos. |
| `python -m alembic upgrade head` con SQLite temporal | aprobado | Creó la baseline y SPEC-005 desde una base vacía. |
| Ruff sobre módulos/artefactos SPEC-005 | aprobado | Incluye dominio, reader, repositorio, caso de uso, página, tests, migración y puerto. |
| `mypy --strict --ignore-missing-imports app/domain/imports.py` | aprobado | Contratos nuevos de dominio sin errores. |
| AppTest de `4_Importacion_Historica.py` | 0 excepciones | Smoke sin API externa ni red. |
| parse YAML de compose y workflow | aprobado | Validación sintáctica con PyYAML. |
| `python scripts/check_repository.py` | aprobado | 236 archivos rastreados/no ignorados, sin secretos ni artefactos locales. |
| `git diff --check` | aprobado | Sin errores de whitespace. |

## Hallazgos

| Severidad | Ubicación | Problema | Acción |
|---|---|---|---|
| MENOR | Repositorio heredado | El chequeo global conserva 213 hallazgos Ruff y 13 MyPy anteriores a SPEC-005; los archivos nuevos bajo el gate focal pasan. | Mantener como deuda transversal y sanear por incrementos sin mezclar cambios mecánicos masivos. |
| MENOR | Verificación Docker | Docker no está instalado en el host, por lo que no se construyó la imagen localmente. | El compose/Dockerfile y YAML quedaron versionados; CI o un host con Docker debe ejecutar `docker compose build`. |
| INFORMATIVO | pytest/OneDrive | Pytest no pudo escribir `.pytest_cache`; las suites y sus bases temporales sí finalizaron. | Mantener `--basetemp` y ejecutar fuera de una carpeta sincronizada si se desea caché. |
| INFORMATIVO | Antimalware | Existe el puerto de escaneo y rechazo probado, pero el piloto no integra un motor AV concreto. | Conectar el adaptador aprobado antes de aceptar archivos no ficticios. |

## Limitaciones conocidas

- Piloto local, SQLite y datos ficticios; no es un despliegue multiusuario de producción.
- La confirmación está limitada a 10 000 filas para reducir contención de escritura.
- Los archivos permanecen en almacenamiento privado; la política de retención y purga física se especificará por separado.
- La compatibilidad PostgreSQL es un objetivo de diseño, no una capacidad verificada.
- Los futuros AI Agents se rigen por ADR-007; no se implementaron en esta fase.

## Veredicto

- [x] VERIFICADO
- [ ] REQUIERE CORRECCIONES
- [ ] NO VERIFICABLE TODAVÍA

Todos los criterios obligatorios de SPEC-005 poseen evidencia satisfactoria y no
quedan hallazgos críticos o mayores abiertos dentro de su alcance.
