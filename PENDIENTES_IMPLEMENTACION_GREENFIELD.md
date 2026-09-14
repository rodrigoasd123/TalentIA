# Pendientes de implementacion de TalentIA

Fecha: 2026-09-14
Referencia: prompt de continuidad greenfield adjunto por el usuario.

## Estado actual

- Repositorio: `rodrigoasd123/TalentIA`.
- Rama de trabajo: `codex/greenfield-rubrica-100`.
- HEAD local y remoto: `f304fa5 fix(ci): install optional verification extras`.
- La consolidacion inicial de runtime (SPEC-031) fue ajustada localmente, pero aun no debe marcarse como verificada: el workflow remoto de GitHub Actions sigue fallando en `pip check`.
- CI fallido: [run 34816292576](https://github.com/rodrigoasd123/TalentIA/actions/runs/34816292576).

## Evidencia ejecutada

- `pytest -q tests/greenfield`: 81 pruebas aprobadas, 2 advertencias.
- `ruff check`: aprobado sobre el codigo mantenido y scripts.
- `ruff format --check`: aprobado, 89 archivos formateados.
- `mypy src/talentia`: aprobado, 65 archivos sin errores.
- `scripts/check_repository.py`: repositorio seguro, 341 archivos revisados.
- `scripts/check_brand_identity.py`: identidad visible `TalentIA` verificada.
- Migraciones Alembic greenfield sobre SQLite vacio: aprobadas.
- Instalacion limpia base: sin LangGraph, LangChain ni MLflow transitivos.
- Docker no pudo verificarse en esta maquina porque el comando `docker` no esta disponible.

La evidencia local no sustituye una ejecucion verde de CI, UAT humano ni etiquetas independientes para el benchmark.

## Trabajo pendiente de implementacion

Progreso del 2026-09-14: el bloque 1 fue implementado y verificado localmente mediante el
refinamiento de SPEC-006. Queda sujeto a CI remoto verde antes de considerarlo cerrado.
El bloque 2 permanece bloqueado por `BIZ-009`. El bloque 3 (AG-01) fue implementado localmente
salvo la similitud configurable de nombres, bloqueada expresamente por `BIZ-004`.
Los bloques 4 (AG-02) y 5 (AG-03) ya estaban cubiertos por SPEC-030 y sus pruebas; OCR concreto es
opcional y el fallback manual está implementado. El bloque 6 (traza AG-04) fue ampliado localmente.

### 1. Seguridad e inicializacion

- Eliminar contrasenas y usuarios de laboratorio predecibles del runtime y de los seeds, incluido `Laboratorio-TalentIA-2026!`.
- Definir provision segura del usuario piloto mediante variables de entorno o mecanismo equivalente, sin secretos en el repositorio.
- Completar politica de contrasenas, longitud minima, expiracion, revocacion de sesiones, rate limit y bloqueo por intentos.
- Verificar RBAC por endpoint y recurso, CSRF, expiracion de sesion, auditoria y aislamiento entre clientes.
- Agregar pruebas de login, bloqueo, revocacion, autorizacion y arranque seguro.

### 2. Estados y reglas de negocio

- Alinear el catalogo definitivo de estados con la rubrica, sus transiciones validas, roles autorizados, motivo obligatorio, responsable, fecha, correlacion y auditoria.
- Implementar bloqueo optimista y transiciones reversibles sin perder historial.
- Definir migracion y compatibilidad para datos con estados antiguos.
- Cubrir intentos invalidos, permisos, concurrencia y trazabilidad con pruebas.

### 3. AG-01: deduplicacion

- Implementar coincidencia exacta determinista, coincidencia probable por telefono y similitud configurable de nombre.
- Procesar todos los candidatos sin limite artificial de 200.
- No fusionar automaticamente: mostrar evidencia, permitir decision humana y registrar auditoria.
- Preservar multiples postulaciones, aislamiento por cliente y referencias a documentos.
- Cubrir positivos, negativos, ambiguos, datos incompletos y errores de normalizacion.

### 4. AG-02: lector de CV

- Completar extraccion hibrida para PDF y DOCX, incluyendo documentos ilegibles y OCR con fallback controlado.
- Separar PII, atributos protegidos, evidencia, confianza e inferencias.
- No inferir edad, genero, foto, nacionalidad u otros atributos protegidos.
- Permitir revision y correccion manual con auditoria.
- Garantizar ejecucion acotada por documento y manejo seguro de prompt injection.

### 5. AG-03: evaluador

- Implementar evaluacion independiente por requisito, con reglas deterministas y semantica opcional.
- Devolver veredicto, puntaje, evidencia, confianza, faltantes y razones por campo.
- Un requisito sin evidencia no debe convertirse en cero automatico sin explicacion.
- La evaluacion no debe cambiar estados por si sola.
- Permitir correccion humana y conservar versionado/auditoria del resultado.

### 6. AG-04: trazabilidad

- Construir una linea de tiempo real por candidato con postulaciones, documentos, evaluaciones, revisiones, cambios de estado y decisiones.
- Mostrar actor, fecha, razon, evidencia y correlacion de cada evento.
- Incorporar filtros y una vista entendible para la revision humana.

### 7. AG-05: exclusiones y lotes

- Implementar exclusiones por proveedor y lote, con simulacion previa.
- Exigir confirmacion, idempotencia, auditoria, cancelacion y reversa segura.
- Exportar CSV protegiendo formulas y sin inventar fechas de vigencia.
- Cubrir conflictos, reintentos, permisos y aislamiento entre clientes.

### 8. Orquestacion y fallback

- Auditar y completar el `StateGraph` tipado, modelos Pydantic, aristas condicionales, reintentos, timeouts, checkpoints, leases, idempotencia, correlacion y versionado de prompts.
- Implementar fallback determinista para fallos de proveedor, timeout, salida invalida y dependencia no disponible.
- Mantener AG-01, AG-04 y AG-05 sin depender innecesariamente de LangGraph.
- Verificar que LangGraph y benchmark sean opcionales y que un fallo de observabilidad no rompa el flujo principal.

### 9. Persistencia y base de datos

- Completar esquema, indices, claves foraneas, timestamps, retencion y consultas sin N+1.
- Consolidar una sola configuracion Alembic y documentar la base oficial.
- Probar migraciones desde base vacia y desde datos existentes, compatibilidad y rollback operativo.

### 10. Privacidad, archivos y documentos

- Aplicar permisos sobre archivos y documentos por cliente, candidato, vacante y rol.
- Implementar retencion, eliminacion, reemplazo de CV y limpieza de derivados.
- Excluir atributos protegidos de ranking/evaluacion.
- Definir cifrado y gestion de secretos para un entorno compartido de produccion.

### 11. Metricas y observabilidad

- Medir latencia y errores de frontend, API, base de datos, proveedor y procesamiento documental.
- Incorporar metricas de calidad de negocio, seguridad, costos y privacidad.
- Mantener MLflow offline y opcional, sin depender de LangSmith.
- Registrar correlacion, version de prompt/modelo y resultado sin exponer PII innecesaria.

### 12. Dataset dorado y benchmark

- Sustituir cualquier benchmark auto-confirmatorio por etiquetas independientes y versionadas.
- Incluir casos positivos, negativos, ambiguos, ilegibles, prompt injection, atributos protegidos y duplicados.
- Medir precision, recall, falso avance, falso descarte, acuerdo de campos/evidencia, latencia y costo.
- Fallar el benchmark si no carga o ignora las etiquetas; no declarar calidad sin validacion humana.

### 13. UX greenfield

- Completar navegacion, filtros, estados, vista 360 del candidato, evaluacion, revision, reemplazo de CV y feedback.
- Verificar responsive, accesibilidad, estados vacios/carga/error, permisos y mensajes para usuarios no tecnicos.
- Validar el flujo completo con UAT de RRHH.

### 14. Rendimiento

- Medir tiempos de frontend, API, consultas, documentos y LLM.
- Corregir N+1, lecturas repetidas, falta de paginacion y limites de concurrencia.
- Registrar una linea base antes de introducir infraestructura adicional.

### 15. Calidad, CI y release

- Corregir el fallo remoto actual de `pip check` y repetir el workflow completo.
- Ejecutar en CI todas las pruebas mantenidas, migraciones, benchmark, instalacion limpia y smoke de la aplicacion.
- Verificar build y runtime Docker cuando exista un entorno con Docker.
- Crear cada spec con `spec.md`, `acceptance.md`, `plan.md`, `tasks.md` y `verification.md`, siguiendo el flujo SDD.
- Usar un commit por bloque, exigir CI verde y abrir PR a `main` solo despues de completar y revisar la evidencia.

## Orden recomendado para continuar

1. Resolver `pip check` en CI y cerrar SPEC-031 con evidencia remota verde.
2. Crear y ejecutar la especificacion de seguridad e inicializacion.
3. Implementar estados y reglas de negocio.
4. Continuar secuencialmente con AG-01 a AG-05 y los bloques restantes.
5. Ejecutar UAT, benchmark con etiquetas independientes, seguridad y release antes de declarar completitud.

## Criterio de completitud

No declarar el proyecto como 100% terminado hasta contar con implementacion, pruebas, evidencia en `verification.md`, CI verde, validacion de seguridad, UAT humano y benchmark con etiquetas independientes para cada bloque.
