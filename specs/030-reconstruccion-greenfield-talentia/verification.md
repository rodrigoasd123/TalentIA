# Verificacion - SPEC-030

Fecha de verificacion: 2026-09-13.

Estado SDD: fase 8 implementada y en verificacion; no se declara `VERIFIED` global hasta recibir
conformidad de RR. HH. y autorizacion de promocion.

## Evidencia de fase 8 - decisiones, UAT y promocion

- `decisiones-negocio-fase-8.md` registra `BIZ-001..010` como explicitamente fuera del alcance del
  piloto. No asigna valores ni aprobaciones a TCS y conserva el comportamiento seguro ya probado.
- `uat-fase-8.md` define diez recorridos con datos sinteticos para perfiles, postulaciones, CV,
  evaluacion, revision, lotes, ex-TCS, exclusiones y recuperacion.
- La ejecucion UAT tecnica aprobo 23 pruebas, con 2 advertencias, en 13,13 segundos y codigo 0. No
  se encontraron incidencias tecnicas o funcionales en los escenarios ejecutados.
- La conformidad humana de RR. HH. no se falsifica: queda pendiente de una persona designada por
  TCS y es una condicion de la aceptacion global.
- `checklist-despliegue-fase-8.md` cubre instalacion, secretos externos, respaldo, migracion, smoke,
  rollback y condiciones de bloqueo.
- `pull-request-fase-8.md` contiene titulo, resumen, evidencia, riesgos y limites para revisar la
  comparacion `codex/rubrica-greenfield-talentia` hacia `main`.
- `pytest -q tests/greenfield --basetemp=.pytest-tmp/fase8-greenfield -p no:cacheprovider`:
  81 pruebas aprobadas, 2 advertencias, en 67,48 segundos.
- `pytest -q --basetemp=.pytest-tmp/fase8-completa -p no:cacheprovider`: 391 pruebas aprobadas,
  2 advertencias, en 89,80 segundos.
- `ruff check`: aprobado; `ruff format --check`: 88 archivos conformes.
- `mypy src/talentia`: 65 archivos sin observaciones.
- `python scripts/check_repository.py`: 538 archivos revisados, repositorio seguro.
- No se realizo merge ni modificacion de `main`.

## Evidencia de fase 7 - endurecimiento y aceptacion tecnica

- `matriz-riesgos-fase-7.md` enlaza autenticacion, RBAC, CSRF, IDOR, aislamiento por cliente,
  uploads, prompt injection, privacidad, control humano, idempotencia, concurrencia y recuperacion
  con pruebas automatizadas. No quedan brechas tecnicas P0/P1 conocidas sin control.
- `test_fase_7_operaciones.py` recorre las revisiones `0001_greenfield`, `0002_esquema` y
  `0003_workflow`: upgrade individual, downgrade individual, downgrade a base y nuevo upgrade a
  `head`. La misma secuencia se repitio manualmente sobre SQLite desechable con codigo de salida 0.
- El respaldo usa la API nativa de SQLite, comprueba `PRAGMA integrity_check`, no sobrescribe el
  destino y rechaza una fuente corrupta. Se creo un respaldo y se restauro en otra base con codigo
  de salida 0.
- Una instalacion limpia de Windows en `.pytest-tmp/fase7-venv`, creada solo desde
  `pip install -e ".[dev]"`, termino con codigo 0. `pip check` informo `No broken requirements
  found`; el smoke importo `talentia.main:app` y mostro `TalentIA`.
- En ese entorno limpio, `pytest -q test_fase_7_operaciones.py test_api.py` aprobo 9 pruebas, con
  1 advertencia, en 3,44 segundos.
- `pytest -q tests/greenfield --basetemp=.pytest-tmp/fase7-greenfield -p no:cacheprovider`:
  81 pruebas aprobadas, 2 advertencias, en 39,55 segundos.
- `pytest -q --basetemp=.pytest-tmp/fase7-completa -p no:cacheprovider`: 391 pruebas aprobadas,
  2 advertencias, en 57,90 segundos.
- `ruff check`: aprobado; `ruff format --check`: 88 archivos conformes.
- `mypy src/talentia`: 65 archivos sin observaciones.
- `python scripts/check_repository.py`: 534 archivos revisados, repositorio seguro.
- Las dos advertencias pertenecen a deprecaciones pendientes de Starlette/AnyIO y LangGraph; no
  representan fallos de seguridad ni funcionales y se documentan para una actualizacion controlada.
- `docs/INSTALACION_GREENFIELD_WINDOWS.md` diferencia runtime/desarrollo y documenta configuracion,
  migracion, API, worker, verificacion, respaldo, restauracion y rollback sin Node.js ni proveedor.

## Evidencia de fase 6 - observabilidad, metricas y MLflow

- La solicitud de evaluacion registra `trabajo.creado` con el mismo identificador de correlacion que
  conserva el trabajo, los checkpoints, la evaluacion y su auditoria.
- Cada nodo nuevo persiste una metrica idempotente con trabajo, correlacion, nombre, estado y tiempo
  acumulado. Cada intento del worker registra duracion, resultado o clase segura de error.
- La lista blanca de telemetria descarta atributos desconocidos y sustituye correos, documentos
  numericos extensos y tokens Bearer. No se guardan textos de CV ni mensajes de excepcion.
- `/api/v1/metrics/pilot` calcula conteos, tasas de exito/error/revision, reintentos y p50/p95 desde
  trabajos, evaluaciones y eventos persistidos. Admite rango temporal y cliente con RBAC/IDOR; el
  conjunto vacio devuelve tasas cero y percentiles nulos.
- La metrica de CV util queda nula como `bloqueado_BIZ_006`. La retencion automatica permanece
  deshabilitada y documentada hasta resolver `BIZ-007`.
- `scripts/ejecutar_benchmark_greenfield.py` ejecuta AG-02, AG-03 y el flujo combinado sobre 20 CV
  sinteticos, sin proveedor remoto. La corrida verificada registro AG-02 `1,0`, AG-03 `0,95`, hash de
  dataset, configuracion `greenfield-v1` y artefacto agregado en MLflow SQLite.
- Una prueba con prompt injection confirma que el proveedor doble recibe cero llamadas. No se
  incorporo LangSmith ni autologging de contenido.
- `pytest -q tests/greenfield/test_fase_6_observabilidad.py tests/greenfield/test_workflow_restart.py`:
  11 pruebas aprobadas, 2 advertencias.
- `pytest -q tests/greenfield`: 78 pruebas aprobadas, 2 advertencias, en 65,25 segundos.
- `pytest -q`: 388 pruebas aprobadas, 2 advertencias, en 98,34 segundos.
- `ruff check`: aprobado; `ruff format --check`: 85 archivos conformes.
- `mypy src/talentia`: 63 archivos sin observaciones.
- `python scripts/check_repository.py`: 529 archivos revisados, repositorio seguro.
- No fue necesaria una migracion: `pilot_metric_events`, correlacion de trabajos y checkpoints ya
  existian en el esquema greenfield aprobado.

## Evidencia de fase 5 - lotes, ex-TCS y exclusiones

- Los lotes aceptan CSV/XLSX en staging, presentan una vista previa y permiten mapear columnas o
  corregir filas antes de una confirmacion explicita. Las filas vacias, incompletas o con correo
  invalido muestran errores accionables y bloquean la persistencia.
- La clasificacion distingue filas nuevas, coincidencias exactas y coincidencias de nombre que
  requieren revision humana. Los duplicados del archivo se omiten y no se fusionan identidades bajo
  reglas `BIZ-008` no aprobadas.
- La carga, el mapeo, la correccion, la confirmacion y la cancelacion quedan auditados en la misma
  unidad de trabajo. Carga, confirmacion y cancelacion repetidas no duplican datos ni eventos.
- Una confirmacion con fallo revierte candidatos, estado y auditoria. Se comprobo con un fallo
  inyectado despues de escribir en la sesion y antes del commit.
- Ex-TCS persiste el hash SHA-256 del documento normalizado y no el identificador crudo. Su consulta
  aplica permiso y cliente; una coincidencia devuelve `revision_requerida`, nunca elegibilidad ni una
  decision automatica.
- AG-05 sigue siendo determinista y conservador. Los reportes aplican el filtro de estado, conservan
  filtros y hash, minimizan la descarga a documento y motivo generico, verifican integridad y auditan
  creacion, actualizacion, consulta y descarga.
- API y web aplican autenticacion, RBAC, alcance contra IDOR y CSRF. La web permite cargar, revisar,
  corregir, confirmar o cancelar lotes, comprobar ex-TCS y crear/descargar reportes sin usar la API
  manualmente.
- `pytest -q tests/greenfield/test_fase_5_lotes_excolaboradores_exclusiones.py`: 9 pruebas aprobadas,
  1 advertencia.
- `pytest -q tests/greenfield`: 74 pruebas aprobadas, 2 advertencias, en 59,03 segundos.
- `pytest -q`: 384 pruebas aprobadas, 2 advertencias, en 93,60 segundos.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: 80 archivos conformes.
- `mypy src/talentia`: 60 archivos sin observaciones.
- `python scripts/check_repository.py`: 524 archivos revisados, repositorio seguro. Los dos archivos
  locales obsoletos de `src/talentia/platform/storage/` se eliminaron con autorizacion expresa del
  propietario; nunca formaron parte de la rama.
- No se crearon migraciones ni se asignaron criterios de vigencia, elegibilidad o identidad. Las
  decisiones `BIZ-001..010` permanecen bloqueadas.

## Evidencia de fase 4 - formularios operativos

- `/perfiles/nuevo` crea perfiles dentro del alcance del usuario, normaliza el codigo, informa
  duplicados y conserva cliente, codigo y titulo ante errores recuperables.
- `/perfiles/{id}/versiones/nueva` captura requisitos mediante lineas estructuradas, obligatoriedad,
  peso, CTC y publicacion. Rechaza formatos, pesos, CTC y codigos duplicados invalidos.
- La creacion de versiones valida permiso y cliente del perfil para impedir IDOR y registra auditoria
  correlacionada.
- `/postulaciones/nueva` ofrece solo candidatos y versiones publicadas del alcance. El caso de uso
  verifica cliente, candidato y perfil; una repeticion devuelve la misma postulacion sin nuevo evento.
- `/evaluaciones/nueva` permite seleccionar postulacion, cargar PDF/DOCX, crear el trabajo durable y
  abrir `/trabajos/{id}` sin llamadas API manuales.
- Repetir carga con el mismo archivo y clave conserva exactamente un documento, un archivo privado y
  un trabajo. El worker procesa ese trabajo y la web enlaza la evaluacion resultante.
- Un archivo invalido conserva postulacion y clave de idempotencia; el navegador solo exige volver a
  seleccionar el archivo por su restriccion de seguridad.
- Las rutas de escritura exigen CSRF, RBAC y alcance por cliente. Se probaron usuario sin permiso,
  perfil/postulacion de otro alcance y CSRF incorrecto.
- `pytest -q tests/greenfield/test_operational_forms.py`: 4 pruebas aprobadas, 2 advertencias.
- `pytest -q tests/greenfield`: 65 pruebas aprobadas, 2 advertencias.
- `pytest -q`: 375 pruebas aprobadas, 2 advertencias, en 310,45 segundos.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: 79 archivos conformes.
- `mypy src/talentia`: 60 archivos sin observaciones.
- `python scripts/check_repository.py`: 521 archivos revisados, repositorio seguro.

## Evidencia de fase 3 - interfaz de evaluacion y revision humana

- `/evaluaciones/{id}` muestra candidatura, perfil, documento, puntaje, naturaleza de sugerencia,
  requisitos, veredictos, explicaciones y evidencia con fragmento, pagina y posiciones originales.
- La ausencia de evidencia se presenta como motivo de revision y nunca como rechazo automatico.
- El formulario web permite aceptar, corregir o rechazar la sugerencia; exige justificacion y, para
  `corregida`, al menos un campo con valor verificado. Se verifico `nivel_ingles = B2 verificado`.
- Las correcciones se muestran en el historial de revision y la forma deja de estar disponible una
  vez resuelta.
- La toma de revision usa una actualizacion condicional por estado/version. Dos resoluciones
  concurrentes producen una decision, un conflicto controlado y un solo evento de auditoria.
- GET y POST aplican permiso y alcance por cliente en la capa de aplicacion; el formulario esta
  protegido con CSRF. Se probaron lectura sin permiso de resolucion, POST prohibido e IDOR.
- `/trabajos/{id}` y `/fragmentos/trabajos/{id}` ofrecen polling HTMX y estados pendiente,
  procesando, completado/revision y error con codigo seguro.
- `pytest -q tests/greenfield/test_evaluation_flow.py`: 7 pruebas aprobadas, 2 advertencias.
- `pytest -q tests/greenfield`: 61 pruebas aprobadas, 2 advertencias.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: 78 archivos conformes.
- `mypy src/talentia`: 60 archivos sin observaciones.
- `python scripts/check_repository.py`: 516 archivos revisados, repositorio seguro.
- `pytest -q`: 371 pruebas aprobadas, 2 advertencias, en 391,78 segundos. La regresion historica y
  greenfield es compatible con la fase 3.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: 78 archivos conformes.
- `mypy src/talentia`: 60 archivos sin observaciones.
- `python scripts/check_repository.py`: 515 archivos revisados, repositorio seguro.
- La regresion completa de fase 3 fue iniciada y detenida por solicitud expresa del propietario
  antes de producir un resultado final; debe repetirse segun `continuacion-fase-3.md`.

## Evidencia de fase 2 - AG-03 y workflow LangGraph durable

- El worker ejecuta los diez nodos reales de LangGraph y conecta la extraccion documental de AG-02
  con la evaluacion de AG-03.
- El estado persistible usa una lista blanca de identificadores, resultados estructurados y codigos
  seguros; no guarda texto original del CV.
- Cada nodo completado deja un checkpoint unico por trabajo y nodo. Al reiniciar, el grafo parte del
  primer nodo incompleto.
- El trabajo conserva identificador de correlacion, lease con token y vencimiento, timeout, contador
  de intentos y reintento con backoff.
- Un fallo inyectado y una reanudacion producen exactamente una extraccion, cuatro sugerencias, una
  evaluacion, dos valoraciones de requisito, una revision y un evento de auditoria de evaluacion.
- Dos workers concurrentes no reservan el mismo trabajo. Un lease vencido se recupera y libera.
- La evidencia guardada por AG-03 es el termino minimo encontrado en el original. La ausencia o
  ambiguedad conserva la candidatura y crea revision humana; nunca genera rechazo automatico.
- Un documento con prompt injection se bloquea en sanitizacion: no ejecuta extraccion ni evaluacion
  remota, no crea sugerencias y persiste un resultado seguro para revision humana.
- `pytest -q tests/greenfield/test_workflow_restart.py tests/greenfield/test_evaluation_flow.py
  tests/greenfield/test_document_extraction.py`: 14 pruebas aprobadas.
- `pytest -q tests/greenfield`: 56 pruebas aprobadas; 2 advertencias de dependencias.
- Alembic sobre SQLite desechable: `upgrade head`, `downgrade 0002_esquema`, `upgrade head`; revision
  final `0003_workflow (head)`.
- La primera suite completa no recolecto por faltar `langchain_openai`, dependencia ya declarada en
  `pyproject.toml`; se instalo en el entorno virtual. El primer reintento completo termino con 364
  pruebas aprobadas y un timeout intermitente de Streamlit. La prueba afectada paso aislada en
  4,12 segundos. La repeticion completa final aprobo 366 pruebas en 346,86 segundos, con dos
  advertencias de deprecacion de dependencias.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: 78 archivos conformes.
- `mypy src/talentia`: 60 archivos sin observaciones.
- `python scripts/check_repository.py`: 512 archivos revisados, repositorio seguro.

## Evidencia de fase 1 - lectura documental y AG-02

- `pytest -q tests/greenfield/test_document_extraction.py`: 5 pruebas aprobadas.
- DOCX: texto extraido localmente, PII sanitizada y cuatro sugerencias con pagina y fragmento fuente.
- PDF sin texto: deriva de forma segura a `revision_manual` con `ocr_requerido`; el puerto OCR
  permanece opcional.
- PDF corrupto e instrucciones incrustadas: extraccion bloqueada con codigo seguro, sin texto ni
  sugerencias persistidas.
- Archivo vacio y firma incompatible: rechazados antes del almacenamiento.
- Idempotencia: una segunda solicitud reutiliza la extraccion y conserva una sola fila de extraccion
  y cuatro sugerencias.
- Proveedor remoto: AG-02 es determinista y local en esta fase; no existe un puerto de proveedor en
  el recorrido documental, por lo que los rechazos no pueden consumir tokens.
- `mypy src/talentia`: 58 archivos sin observaciones.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `python scripts/check_repository.py`: 507 archivos revisados, repositorio seguro.

## Evidencia aprobada

- `pytest -q tests/greenfield`: 44 pruebas aprobadas.
- `pytest -q`: 359 pruebas aprobadas; suite historica y greenfield compatibles.
- `ruff check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `ruff format --check src/talentia migrations_greenfield tests/greenfield`: aprobado.
- `mypy src/talentia`: 58 archivos sin observaciones.
- Alembic en SQLite desechable: `upgrade head`, `downgrade base`, `upgrade head`; revision final
  persistida `0002_esquema`.
- `python scripts/check_repository.py`: 497 archivos revisados, repositorio seguro.
- FastAPI TestClient: login, cabeceras de seguridad, salud y flujos API aprobados.
- Concurrencia: fusion de campos disjuntos y conflicto de campos solapados aprobados.
- Importaciones: persistencia e idempotencia de candidatos y excolaboradores aprobadas.
- Web: alta con preflight, ficha de 18 campos, derivados y trazabilidad aprobadas.
- Web operativa: los modulos dejaron de ser placeholders y muestran proyecciones reales con alcance
  por cliente y permiso; formularios de escritura distintos del alta de candidatos siguen pendientes.
- Evaluacion/HITL: contexto referencial validado antes de encolar; worker persiste evaluacion y revision
  idempotentes; consulta y resolucion con correcciones quedan auditadas en la misma unidad de trabajo.
- Recuperacion: reservas de trabajo abandonadas por mas de 15 minutos vuelven a estar disponibles.
- Almacen de documentos: escritura atomica, sin sobreescritura y con defensa contra escape de ruta.
- Acceso: asignacion API/web de roles y clientes, auditoria y autoampliacion denegada.
- Corpus golden: 20 CV sinteticos y anonimizados.

## Limitaciones verificadas

- La suite completa se recolecta y pasa. Permanecen dos advertencias de deprecacion de dependencias
  (`Starlette/AnyIO` y serializador de checkpoint de LangGraph), sin fallos funcionales actuales.
- AG-02 y AG-03 ya se ejecutan desde el worker. En esta fase ambos adaptadores son locales y
  deterministas; la seleccion o evaluacion de un proveedor LLM permanece fuera del recorrido.
- El mapeo/correccion de lotes, flujo ex-TCS y descargas de exclusion permanecen para la fase 5; no
  se adelantaron ni se resolvieron decisiones BIZ.
- No se incluyo un motor OCR concreto: el adaptador es opcional y la ausencia de texto deriva a
  revision humana, segun el alcance aprobado de la fase 1.
- `BIZ-001..010` continuan en estado `BLOCKED`; las capacidades afectadas fallan cerrado o exigen
  revision humana. No se asignaron umbrales, vigencias, retenciones ni alcances ficticios.
- La Definition of Done global no puede declararse completa mientras esas decisiones y las tareas
  parciales registradas en `tasks.md` sigan abiertas.
