# Verificación — SPEC-037

## Entorno

- Fecha: 2026-09-17
- Revisión/commit base: `d3b6fd0ceb450e5e2aa3f582e5443a9b1731cebb` con cambios locales de SPEC-037
- Rama/worktree: `codex/revision-demo-20260915` / `D:\Documents\PostulaIA\.codex-demo-review`
- Plataforma: Windows 11 `10.0.26200`, Python 3.13.7, SQLite, FastAPI/Jinja2/SQLAlchemy
- Alcance: implementación completa de SPEC-037 y correcciones derivadas de la primera revisión.

## Evidencia por criterio

| AC | Requisitos | Evidencia | Resultado |
|---|---|---|---|
| AC-037-001 | FR-037-001/002/003, NFR-037-004 | `test_espacio_web_expone_jerarquia_y_funciona_sin_llm`, `test_sistema_visual_es_local_centralizado_y_responsive`; cuenta, perfil, versión, cupos, conteos y acciones visibles en `detalle_convocatoria.html` | CUMPLE |
| AC-037-002 | FR-037-002/003 | `test_un_perfil_admite_convocatorias_independientes`, `test_convocatoria_ordinaria_exige_ambas_fechas`; contrato `AltaConvocatoria` | CUMPLE |
| AC-037-003 | FR-037-006/007, SEC-037-001 | `test_identidad_exacta_muestra_antecedente_de_la_misma_cuenta`; `applications.reclutador_id` y consulta agrupada con actor, fecha y proceso | CUMPLE |
| AC-037-004 | FR-037-006, SEC-037-001/002 | `test_identidad_y_url_no_filtran_otra_cuenta`; respuesta opaca y evento `seguridad.idor_bloqueado` confirmado | CUMPLE |
| AC-037-005 | FR-037-008, SEC-037-003/004 | `test_hiring_manager_asigna_alcance_y_responsabilidad_con_auditoria`; invalidación de sesión, auditoría y vista web limitada | CUMPLE |
| AC-037-006 | FR-037-009/010, SEC-037-005 | `test_maquina_estados_exige_motivo_y_separa_aptitud_de_finalista`, `test_finalista_exige_justificacion_y_la_audita`, `test_cupo_finalistas_se_revalida_en_la_transicion` | CUMPLE |
| AC-037-007 | FR-037-011/012 | `test_flujo_humano_cierra_y_convierte_aptas_en_backup`; cierre, backup y bloqueo de altas en una transacción | CUMPLE |
| AC-037-008 | FR-037-005/009/013, NFR-037-003 | `test_compare_and_swap_rechaza_dos_sesiones_con_la_misma_version`, `test_conflicto_web_conserva_destino_y_comentario`; `UPDATE ... WHERE version` con validación de `rowcount` | CUMPLE |
| AC-037-009 | FR-037-014, NFR-037-005 | `test_migracion_convocatorias_preserva_postulacion_y_evidencia`; upgrade/downgrade, relaciones, CV, evaluación y revisión preservados | CUMPLE |
| AC-037-010 | NFR-037-001/006 | `test_flujo_completo_no_invoca_proveedores_llm`; claves eliminadas y `ClienteLLM.evaluar` sustituido por un doble que falla ante cualquier invocación | CUMPLE |

## Comandos ejecutados

| Comando | Resultado | Observaciones |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests\greenfield\test_convocatorias.py tests\greenfield\test_fase_7_operaciones.py -q` | 19 aprobadas | Incluye CAS con dos sesiones, migración reversible, UI 409 y cero llamadas LLM. |
| `.venv\Scripts\python.exe -m pytest tests\greenfield -q` | 143 aprobadas | Regresión greenfield completa; cuatro advertencias informativas. |
| `.venv\Scripts\python.exe -m pytest tests\greenfield\test_convocatorias.py tests\greenfield\test_seguridad.py tests\greenfield\test_fase_7_operaciones.py tests\greenfield\test_frontend_visual.py -q` | 35 aprobadas | Revisión formal focalizada de aceptación, seguridad y presentación. |
| `.venv\Scripts\python.exe -m ruff check src\talentia tests\greenfield migrations_greenfield` | Aprobado | Sin incidencias. |
| `.venv\Scripts\python.exe -m ruff format --check src\talentia tests\greenfield migrations_greenfield` | Aprobado | Formato conforme. |
| `.venv\Scripts\python.exe -m mypy src\talentia` | Aprobado | 77 archivos, sin errores. |
| `git diff --check` | Aprobado | Solo avisos de normalización LF/CRLF de Git en Windows. |

## Hallazgos

| Severidad | Ubicación | Problema | Acción |
|---|---|---|---|
| INFORMATIVO | Dependencias de pruebas | Starlette, LangGraph y el adaptador datetime de SQLite emiten advertencias de deprecación. | Registrar su actualización como mantenimiento futuro; no afecta SPEC-037. |

## Limitaciones conocidas

- La evidencia visual es reproducible mediante pruebas HTML/CSS y TestClient; no se realizó una sesión manual adicional con navegador móvil físico.
- No se ejecutó una prueba de carga con volumen productivo; la spec no define un umbral cuantitativo y las consultas críticas quedaron indexadas y sin N+1.
- Las advertencias de dependencias continúan como deuda informativa y no alteran los resultados funcionales.

## Veredicto

- [x] VERIFICADO
- [ ] REQUIERE CORRECCIONES
- [ ] NO VERIFICABLE TODAVÍA

Todos los criterios AC-037-001 a AC-037-010 cuentan con evidencia satisfactoria. No existen
hallazgos críticos o mayores abiertos y la regresión completa permanece en verde.
