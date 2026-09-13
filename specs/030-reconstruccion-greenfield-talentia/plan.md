# Plan por fases - SPEC-030

## Resumen tecnico

Completar la reconstruccion greenfield mediante ocho fases incrementales sobre
`codex/rubrica-greenfield-talentia`. Cada fase debe producir una demostracion independiente,
pruebas automatizadas, evidencia en `verification.md` y un commit reversible. `main` no se modifica
hasta que las fases aplicables, la revision de seguridad y la aceptacion del piloto esten aprobadas.

Estado del plan: **APROBADO**.

## Arquitectura y limites afectados

- Dominio: `src/talentia/modules/*/domain`; permanece libre de FastAPI, SQLAlchemy y LangGraph.
- Aplicacion: `src/talentia/shared/application`; coordina casos de uso mediante puertos.
- Infraestructura: `src/talentia/shared/infrastructure`, `src/talentia/platform` y adaptadores nuevos
  indicados expresamente por fase.
- IA: `src/talentia/ai/agents`, `src/talentia/ai/guardrails` y
  `src/talentia/ai/workflows`; AG-02/03 no deciden estados de postulacion.
- Transporte: `src/talentia/web/api.py`, `src/talentia/web/routes` y plantillas Jinja2/HTMX; no
  acceden directamente al ORM.
- Persistencia: cualquier cambio de esquema se realiza solo con una revision nueva de Alembic.
- Runtime historico: se conserva como rollback y referencia; no recibe funcionalidades nuevas.

## Fases de implementacion

### Fase 0 - Baseline y aislamiento - COMPLETADA

Objetivo: establecer una base confiable fuera de `main`.

- Rama aislada publicada y basada en el trabajo de Miguel.
- Persistencia inicial de evaluacion/revision, almacenamiento privado y paneles de lectura.
- Regresion actual: 354 pruebas; Ruff, formato, mypy y escaner aprobados.

Puerta de salida: mantener estos controles aprobados al terminar cada fase.

### Fase 1 - Lectura documental real y AG-02

Objetivo: convertir PDF/DOCX en una extraccion persistida, segura y trazable.

- Crear un adaptador nuevo `src/talentia/modules/documents/infrastructure/extractores.py` para PDF y
  DOCX; OCR queda como adaptador opcional con fallback manual.
- Conectar `lector_cv.py` con documento original, sanitizacion de PII y referencias verificables.
- Persistir `document_extractions` y `field_suggestions` de forma idempotente.
- Rechazar firma invalida, documento vacio, traversal, instrucciones incrustadas y fallo de
  sanitizacion sin invocar proveedor remoto.

Demostracion: subir un CV sintetico y consultar campos sugeridos con referencia al original.

Puerta de salida: pruebas unitarias, integracion documental, seguridad e idempotencia aprobadas.

### Fase 2 - AG-03 y workflow LangGraph durable

Objetivo: ejecutar una evaluacion completa con evidencia, checkpoints y recuperacion.

- Crear `src/talentia/ai/workflows/nodos_evaluacion.py` y
  `src/talentia/ai/workflows/procesador_evaluacion.py` como archivos nuevos.
- Sustituir los nodos marcadores por validacion, carga, sanitizacion, extraccion, relacion de
  requisitos, verificacion original, veredicto determinista, persistencia e interrupt HITL.
- Guardar checkpoint tras cada nodo y propagar un mismo identificador de correlacion.
- Añadir timeout, renovacion de reserva, retry central e idempotencia por efecto.
- Ausencia o ambiguedad de evidencia produce `requiere_revision`; nunca un rechazo inventado.

Demostracion: interrumpir el worker a mitad del grafo, reiniciarlo y comprobar una sola evaluacion.

Puerta de salida: pruebas de workflow, reinicio, concurrencia, fallo inyectado y evidencia aprobadas.

### Fase 3 - Evaluacion y revision humana en la interfaz

Objetivo: hacer operable el resultado de las fases 1 y 2 para RR. HH.

- Crear plantillas nuevas para detalle de evaluacion y cola/detalle de revision.
- Mostrar requisitos, puntaje documental, evidencia, motivo de ambiguedad y origen IA/humano.
- Permitir aceptar, corregir o rechazar una revision con comentario obligatorio.
- Usar polling HTMX para trabajos y conservar CSRF, RBAC y alcance por cliente.
- Mantener la evaluacion inmutable; las correcciones se registran en `field_corrections` y auditoria.

Demostracion: evaluar un CV, abrir el caso pendiente, corregir un dato y verificar la traza.

Puerta de salida: API, seguridad, navegacion por teclado y E2E del flujo HITL aprobados.

### Fase 4 - Formularios operativos principales

Objetivo: reemplazar las proyecciones de solo lectura por recorridos completos.

- Perfiles: alta, nueva version, requisitos y publicacion controlada.
- Postulaciones: alta con candidato/perfil/fuente y prevencion de duplicados.
- Documentos: carga, estado de procesamiento y asociacion visible.
- Trabajos: estado, intentos, error sanitizado y reintento permitido.
- Conservar filtros de servidor, 18 campos, control optimista y mensajes de conflicto.

Demostracion: crear perfil y postulacion, adjuntar CV y lanzar trabajo sin usar API manualmente.

Puerta de salida: E2E, RBAC, IDOR, concurrencia y estados loading/error/vacio aprobados.

### Fase 5 - Lotes, ex-TCS y exclusiones - IMPLEMENTADA EN VERIFICACION

Objetivo: completar los recorridos de datos masivos sin resolver reglas BIZ bloqueadas.

- Añadir carga, mapeo, vista previa, clasificacion, reporte de errores y confirmacion de lote.
- Permitir revisar excolaboradores usando solo hash de documento.
- Generar exclusiones deterministas con filtros y hash, protegiendo personas vigentes.
- Mantener `BIZ-001` y `BIZ-008` en fallo cerrado donde corresponda.

Demostracion: cargar un CSV sintetico, corregir errores, confirmar una vez y descargar reporte.

Puerta de salida: integracion, idempotencia, rollback transaccional, seguridad y E2E aprobados.

### Fase 6 - Observabilidad, metricas y MLflow - IMPLEMENTADA EN VERIFICACION

Objetivo: medir el piloto con eventos reales sin convertir estimaciones en resultados.

- Persistir tiempos por request, trabajo, agente y nodo; intentos, errores, tokens y cache cuando
  existan. Costo desconocido permanece nulo.
- Correlacionar request, trabajo, evaluacion, revision y auditoria sin guardar CV ni PII en logs.
- Crear agregaciones p50/p95 y panel de baseline.
- Conectar el benchmark greenfield con MLflow y un corpus sintetico versionado.
- Comparar modelos por calidad, latencia, errores y costo conocido; no seleccionar automaticamente.

Demostracion: ejecutar benchmark reproducible y abrir corrida, parametros, metricas y artefactos.

Puerta de salida: pruebas de exactitud de metricas, privacidad, rendimiento y reproducibilidad.

### Fase 7 - Endurecimiento y aceptacion tecnica - IMPLEMENTADA EN VERIFICACION

Objetivo: demostrar que el conjunto es seguro, recuperable y desplegable como piloto local.

- Completar E2E de todos los recorridos P0/P1, pruebas IDOR, CSRF, uploads, PII e inyeccion.
- Ejecutar migracion `upgrade/downgrade/upgrade`, backup/restore y reinicio del worker.
- Probar instalacion limpia en Windows sin Node.js y funcionamiento sin proveedor LLM.
- Resolver o fijar las dos advertencias de dependencias antes de actualizar versiones.
- Actualizar runbook, matriz de rubrica, tareas y evidencia.

Demostracion: instalar desde cero, restaurar backup y completar el smoke operativo.

Puerta de salida: cero fallos P0/P1 tecnicos y revision de seguridad aprobada.

### Fase 8 - Decisiones TCS, UAT y promocion

Objetivo: cerrar las definiciones de negocio y validar el piloto con personas usuarias.

- Resolver y documentar `BIZ-001..010`; cada decision que cambie comportamiento exige refinamiento
  de spec, pruebas y versionado cuando aplique.
- Ejecutar UAT con RR. HH. para candidatos, evaluacion/HITL, lotes, exclusiones y recuperacion.
- Registrar observaciones, corregir defectos y repetir solo los escenarios afectados.
- Preparar comparacion final con `main`; promover mediante PR solo tras aprobacion explicita.

Puerta de salida: decisiones BIZ aprobadas, UAT firmado, runbook aceptado y autorizacion de merge.

## Flujo de datos objetivo

```text
Upload CV -> validacion local -> almacenamiento privado -> AG-02/sanitizacion
          -> extraccion y sugerencias -> AG-03/requisitos -> verificacion original
          -> evaluacion inmutable -> interrupt/revision humana -> correcciones auditadas
          -> metricas tecnicas y de piloto
```

## Decisiones y alternativas

- Se mantiene un solo monolito modular. Separar microservicios ahora añade operacion sin resolver una
  necesidad de la rubrica.
- LangGraph se limita a AG-02/03. Llevar AG-01/04/05 al grafo reduciria explicabilidad sin beneficio.
- El proveedor LLM sigue siendo opcional. Exigirlo romperia `NFR-030-002` y el fallback manual.
- No se reutiliza el frontend Streamlit historico. La interfaz aprobada sigue siendo Jinja2/HTMX.
- No se selecciona automaticamente un modelo desde MLflow; el benchmark produce evidencia para una
  decision humana.

## Compatibilidad, transicion y reversion

- Cada fase produce un commit independiente sobre la rama aislada; su rollback es revertir ese commit.
- Las migraciones nuevas deben incluir `downgrade` y probarse sobre una base desechable.
- Los endpoints existentes no se eliminan durante estas fases; cambios incompatibles requieren
  addendum aprobado.
- El runtime y la base anteriores permanecen sin cambios hasta la promocion final.
- Si una fase falla su puerta de salida, no se inicia la siguiente ni se mezcla a `main`.

## Seguridad, privacidad y fallos

- CV y lotes son entradas no confiables; se validan firma, tamaño, nombre y contenido.
- Ningun texto de CV puede convertirse en instruccion, tool call o regla de negocio.
- PII se minimiza antes de cualquier proveedor remoto y no aparece en logs, metricas o MLflow.
- IDOR se bloquea en aplicacion mediante alcance por cliente; la interfaz no sustituye esa validacion.
- Trabajos externos no mantienen transacciones SQL abiertas.
- Fallos, ambiguedad y decisiones BIZ pendientes derivan a revision humana o fallo cerrado.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-030-001 | automatizada/manual | instalacion limpia y smoke sin proveedor en fase 7 |
| AC-030-002 | automatizada | suites API/security/IDOR por fase y regresion en fase 7 |
| AC-030-003 | automatizada/E2E | persistencia, versionado, auditoria y pantallas de fases 1, 3, 4 y 5 |
| AC-030-004 | automatizada/manual | agentes, evidencia original y fallback de fases 1 y 2; demostracion en fase 3 |
| AC-030-005 | automatizada | reinicio, retry, timeout e idempotencia de fase 2 |
| AC-030-006 | automatizada | `tests/greenfield/test_arquitectura.py` y mypy en todas las fases |
| AC-030-007 | automatizada/manual | migracion, backup, restore y verificacion Windows en fase 7 |
| AC-030-008 | inspeccion/automatizada | matriz BIZ actualizada en cada fase y resolucion controlada en fase 8 |

Comandos existentes obligatorios al cerrar cada fase:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/greenfield
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src/talentia migrations_greenfield tests/greenfield
.venv\Scripts\python.exe -m ruff format --check src/talentia migrations_greenfield tests/greenfield
.venv\Scripts\python.exe -m mypy src/talentia
.venv\Scripts\python.exe scripts/check_repository.py
```

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Duplicar efectos al reiniciar LangGraph | claves idempotentes por efecto y prueba de corte por nodo |
| Filtrar PII al proveedor o MLflow | sanitizacion fail-closed y pruebas con proveedor espia |
| Convertir ausencia en rechazo | `requiere_revision` obligatorio y assertion de dominio/API |
| Mezclar reglas en plantillas | rutas solo traducen; pruebas de arquitectura |
| Bloqueo SQLite durante IA | reservar/commit antes del trabajo externo y metricas de lock |
| Formularios expuestos a IDOR/CSRF | alcance en aplicacion, token CSRF y pruebas negativas |
| Declarar ahorro o calidad sin baseline | separar estimacion/medicion y exigir corpus versionado |
| Divergencia con trabajo paralelo | commits por fase, rebase revisado y regresion antes de integrar |

## Aprobacion

- [x] Plan por fases aprobado por la persona responsable el 2026-09-13.
- [x] Fase 1 autorizada para implementacion el 2026-09-13.
- [x] Fase 4 aprobada y fase 5 autorizada por la persona responsable el 2026-09-13.
