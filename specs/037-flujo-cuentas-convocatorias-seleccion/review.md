# Evidencia de implementación — SPEC-037

**Estado:** LISTA PARA REVISIÓN (`VERIFICANDO`)  
**Fecha:** 2026-09-16  
**Veredicto de implementación:** todos los criterios cuentan con evidencia automatizada; falta la revisión SDD independiente para declarar `VERIFICADA`.

## Matriz de aceptación

| Criterio | Evidencia reproducible | Resultado |
|---|---|---|
| AC-037-001 | `test_espacio_web_expone_jerarquia_y_funciona_sin_llm` y plantillas `cuentas.html`, `convocatorias.html`, `detalle_convocatoria.html` | Cumple |
| AC-037-002 | `test_un_perfil_admite_convocatorias_independientes` y API paginada `/campaigns` | Cumple |
| AC-037-003 | `test_identidad_exacta_muestra_antecedente_de_la_misma_cuenta` | Cumple |
| AC-037-004 | `test_identidad_y_url_no_filtran_otra_cuenta` | Cumple |
| AC-037-005 | `test_hiring_manager_asigna_alcance_y_responsabilidad_con_auditoria` | Cumple |
| AC-037-006 | `test_maquina_estados_exige_motivo_y_separa_aptitud_de_finalista` y `test_cupo_finalistas_se_revalida_en_la_transicion` | Cumple |
| AC-037-007 | `test_flujo_humano_cierra_y_convierte_aptas_en_backup`, incluida prohibición de nuevas altas | Cumple |
| AC-037-008 | `test_transicion_rechaza_version_obsoleta` | Cumple |
| AC-037-009 | `test_migracion_convocatorias_preserva_postulacion_y_evidencia` | Cumple |
| AC-037-010 | `test_espacio_web_expone_jerarquia_y_funciona_sin_llm`; el flujo operativo no invoca proveedores | Cumple |

## Evidencia técnica

- Dominio: máquina de estados determinística, separación `apta`/`finalista`, motivos obligatorios y cupos.
- Persistencia: convocatorias, responsables, relación obligatoria candidatura–convocatoria, índices y control optimista.
- Migración: backfill a convocatorias de compatibilidad, upgrade/downgrade con documentos, evaluaciones y revisiones preservados.
- Seguridad: alcance por cuenta, respuesta 404 para candidato fuera de alcance, deduplicación sin filtración lateral, permisos granulares e invalidación de sesión.
- Operación: cuenta → perfil → convocatoria → responsables → candidaturas; cierre humano y backups atómicos.
- Trazabilidad: altas, asignaciones, transiciones y cierre registran actor, cuenta, recurso y detalle.
- Panel central: el estado se lee desde la candidatura y muestra cuenta, perfil y convocatoria.
- Despliegue: conserva FastAPI, Jinja2, SQLAlchemy y SQLite; no añade Node.js ni infraestructura externa.

## Comandos ejecutados

```powershell
.\.venv\Scripts\python.exe -m ruff check src\talentia tests\greenfield migrations_greenfield
.\.venv\Scripts\python.exe -m ruff format --check src\talentia tests\greenfield migrations_greenfield
.\.venv\Scripts\python.exe -m mypy src\talentia
.\.venv\Scripts\python.exe -m pytest tests\greenfield -q --basetemp .pytest-tmp-spec037-final
```

Resultados:

- Ruff lint: aprobado.
- Ruff format: 109 archivos conformes.
- Mypy: 77 archivos, sin errores.
- Pytest greenfield: 138 aprobadas, 0 fallidas, 4 advertencias de dependencias.

## Observaciones para revisión

- Las advertencias provienen de aliases/deprecaciones en Starlette, LangGraph y el adaptador datetime de SQLite; no representan fallos funcionales de SPEC-037.
- No se añadieron decisiones automáticas por IA: la aptitud, selección, backup y cierre continúan bajo control humano.
- Las modificaciones locales preexistentes de IA/documentos se conservaron y no fueron revertidas.