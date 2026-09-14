# SPEC-024 — Observabilidad MLflow y consumo de IA

- **Estado:** VERIFIED (línea base y refinamiento R1)
- **Fecha:** 2026-09-12
- **Owner:** Product and engineering

## Problema

TalentIA necesita medir modelos sin registrar CV, prompts, respuestas, PII o secretos. La implementación reciente mezcla MLflow y una tabla OpenAI consultada directamente por Streamlit, y activa autologging que puede capturar contenido.

## Alcance

- Fuente única de telemetría accesible por FastAPI.
- Metadatos: proveedor, modelo, funcionalidad, tokens, latencia, costo estimado, estado y fecha.
- Persistencia local y panel autorizado.
- MLflow opcional, degradable y sin contenido.

## Fuera de alcance

- Observabilidad externa/productiva, LangSmith y almacenamiento de prompts/respuestas.

## Requisitos

- **FR-024-001:** cada llamada debe producir una métrica coherente por proveedor/modelo/función.
- **FR-024-002:** la UI debe consumir telemetría mediante FastAPI y respetar la base configurada.
- **FR-024-003:** MLflow debe persistir métricas entre reinicios y mostrar estado operativo.
- **NFR-024-001:** la caída de MLflow nunca bloquea el ATS ni una evaluación.
- **NFR-024-002:** los costos no conocidos deben mostrarse como no disponibles, no como cero real.
- **SEC-024-001:** trazas y runs no almacenan prompts, respuestas, CV, PII ni claves.
- **SEC-024-002:** la consulta requiere `settings:read`; configuración requiere `settings:write`.

## Riesgos

- Autologging captura contenido: se desactiva y se usa instrumentación explícita metadata-only.
- Doble conteo: una sola capa es responsable de persistir cada llamada.
- Sin preguntas bloqueantes.

## Referencias

Documento TCS, constitución y ADR-007.

## Refinamiento R1 — Exploración de procesos y acceso a MLflow

> Refinamiento aprobado por el propietario el 2026-09-13.

### Necesidad

La línea base agrega consumo por proveedor/modelo, pero Administración necesita inspeccionar cada
proceso como una traza navegable: workflow, grafo, nodos, tiempos y consumo de tokens de entrada y
salida. También necesita un acceso visible al panel local de MLflow.

### Alcance propuesto

- Nueva sección de observabilidad dentro del panel administrativo.
- Resumen por rango temporal, proveedor, modelo, función, estado y tipo de proceso.
- Lista paginada de procesos con identificadores de correlación y workflow.
- Detalle jerárquico `proceso → grafo → nodo → llamada de modelo` con duración, estado, reintentos,
  tokens de entrada/salida/total y costo únicamente cuando exista tarifa configurada.
- Topología Mermaid o representación equivalente derivada de la definición real del grafo, junto
  con los nodos efectivamente ejecutados.
- Botón “Abrir MLflow” usando la URL operativa devuelta por el backend y abriéndola en otra pestaña.
- MLflow conservará runs padre/hijo metadata-only para workflow, nodos y llamadas LLM.

### Requisitos nuevos

- **FR-024-004:** la API debe devolver procesos paginados y filtrables con correlación, workflow,
  proveedor, modelo, estado, tiempos y consumo agregado.
- **FR-024-005:** el administrador debe poder abrir un proceso y navegar sus nodos ejecutados en
  orden, con estado, duración, reintentos y tokens por llamada cuando aplique.
- **FR-024-006:** el detalle debe incluir la topología/version del grafo y distinguir nodos
  ejecutados, omitidos, fallidos y reintentados.
- **FR-024-007:** la UI debe mostrar tokens de entrada, salida y total por modelo, además de
  llamadas, errores, latencia y costo conocido/no disponible.
- **FR-024-008:** la UI debe ofrecer un botón para abrir el MLflow configurado solamente cuando el
  backend informe que está instalado, habilitado y accesible.
- **FR-024-009:** MLflow debe registrar relaciones padre/hijo entre proceso, nodos y llamadas sin
  almacenar contenido de entrada o salida.
- **NFR-024-003:** listas y agregados deben estar paginados/acotados y no cargar todos los runs en
  memoria para renderizar el panel.
- **NFR-024-004:** la pérdida de MLflow no elimina la telemetría mínima local ni bloquea el proceso
  de negocio.
- **SEC-024-003:** la URL de MLflow debe provenir de configuración confiable del servidor; no se
  aceptará una URL enviada por el navegador para construir el enlace.
- **SEC-024-004:** trazas, nombres de runs, parámetros, tags y errores solo incluirán metadatos
  permitidos; quedan prohibidos prompts, respuestas, fragmentos, nombres de candidatos, CV, PII y
  secretos.
- **SEC-024-005:** la vista requiere `settings:read`; el acceso a acciones administrativas sigue
  requiriendo `settings:write`.

### Compatibilidad y degradación

- El endpoint agregado existente se conserva.
- Si MLflow está deshabilitado o caído, el panel muestra el estado y la telemetría local disponible.
- El botón a MLflow se oculta o deshabilita cuando la URL no sea segura o el servicio no esté listo.
