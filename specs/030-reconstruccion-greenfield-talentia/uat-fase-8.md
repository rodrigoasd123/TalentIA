# UAT de fase 8

Fecha de ejecucion tecnica: 2026-09-13

## Alcance y datos

Se usaron exclusivamente identidades, CV y lotes sinteticos generados por las pruebas. No se
versionaron CV reales, PII, secretos ni bases SQLite. La ejecucion automatizada representa los
recorridos de RR. HH.; la validacion y firma de una persona usuaria de TCS sigue siendo externa.

| Escenario | Recorrido | Resultado tecnico | Evidencia |
|---|---|---|---|
| UAT-01 | Crear perfil, version, requisitos y publicacion | Aprobado | `test_operational_forms.py` |
| UAT-02 | Crear postulacion y evitar duplicados | Aprobado | `test_operational_forms.py` |
| UAT-03 | Cargar CV, crear trabajo y seguir su estado | Aprobado | `test_operational_forms.py` |
| UAT-04 | Evaluar con evidencia y conservar incertidumbre | Aprobado | `test_evaluation_flow.py` |
| UAT-05 | Aceptar, corregir o rechazar una sugerencia con auditoria | Aprobado | `test_evaluation_flow.py` |
| UAT-06 | Bloquear CSRF, rol insuficiente, IDOR y carrera de revisores | Aprobado | `test_operational_forms.py`, `test_evaluation_flow.py` |
| UAT-07 | Cargar, mapear, corregir, confirmar y cancelar un lote | Aprobado | `test_fase_5_lotes_excolaboradores_exclusiones.py` |
| UAT-08 | Revisar coincidencia ex-TCS sin exponer documento | Aprobado | `test_fase_5_lotes_excolaboradores_exclusiones.py` |
| UAT-09 | Crear y descargar exclusion integra y aislada | Aprobado | `test_fase_5_lotes_excolaboradores_exclusiones.py` |
| UAT-10 | Migrar, respaldar y restaurar el piloto | Aprobado | `test_fase_7_operaciones.py` |

## Ejecucion

Comando:

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q tests/greenfield/test_operational_forms.py tests/greenfield/test_evaluation_flow.py tests/greenfield/test_fase_5_lotes_excolaboradores_exclusiones.py tests/greenfield/test_fase_7_operaciones.py --basetemp=.pytest-tmp/fase8-uat -p no:cacheprovider
```

Resultado: **23 pruebas aprobadas, 2 advertencias, 13,13 segundos, codigo de salida 0**.

Incidencias funcionales o tecnicas: ninguna. Las dos advertencias son deprecaciones conocidas de
Starlette/AnyIO y LangGraph.

## Aceptacion humana

- Responsable de ejecucion tecnica: Codex, sobre la rama de la especificacion.
- Responsable de aceptacion funcional: pendiente de asignacion por TCS.
- Firma o conformidad de RR. HH.: pendiente; no se simula ni se declara en nombre de TCS.
- Repeticion necesaria: solo si la validacion humana encuentra una incidencia o se aprueba una BIZ.
