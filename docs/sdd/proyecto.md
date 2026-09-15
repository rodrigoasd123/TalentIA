# Contexto del proyecto — TalentIA

> **Documento historico.** Desde SPEC-031 el unico runtime oficial vive en `src/talentia`, usa
> FastAPI/Jinja2/HTMX y arranca con `python -m uvicorn talentia.main:app`. Las rutas heredadas
> mencionadas debajo se conservan solo como trazabilidad y no son instrucciones vigentes.

> Estado: contexto inicial observado el 2026-08-20. Los campos marcados como `POR CONFIRMAR` no se deducen de forma fiable del repositorio.
## Actualización operativa TCS — SPEC-023 a SPEC-029 (2026-09-12)

- **Problema objetivo:** TalentIA prioriza las 10 horas semanales repetitivas descritas por TCS: gestión histórica y cruce con proveedor. Las 15 horas de búsqueda/contacto en LinkedIn conservan juicio y ejecución humana; no se añadió scraping ni contacto automático.
- **Identidad antes del CV:** Postulaciones ofrece preflight por documento, correo, teléfono y nombre normalizado, muestra procesos anteriores y solo alerta; nunca fusiona personas automáticamente.
- **Lectura del CV:** la extracción estructurada persiste con el documento y Candidate 360 permite revisar, corregir y confirmar únicamente conocimiento técnico y disponibilidad, con versión y auditoría.
- **Filtro temprano:** se conserva la evaluación explicable, ponderada y con revisión humana. La IA no decide contratación.
- **Trazabilidad:** la auditoría encadenada y las trazas exportables permanecen como fuente de explicación de cada cambio.
- **Proveedor:** Reportes expone una lista determinística de exclusiones con vigencia y CSV neutralizado para Excel.
- **Alta desde CV:** Base general permite cargar hasta 50 CV, precargar campos presentes y alertar por coincidencias con ex-TCS o restricciones TCS sin decidir por RR. HH.
- **Medición:** Reportes muestra CV útiles, evaluaciones tempranas, duplicados advertidos y horas potenciales con parámetros visibles. Son indicadores del piloto, no ROI ni ahorro validado.
- **Modelos:** catálogo único para Gemini, GenAI Lab y OpenAI; cada proveedor usa una credencial cifrada independiente. El benchmark usa una suite sintética versionada, máximo cinco modelos, confirmación explícita y quality gate contra baseline.
- **Privacidad MLflow:** no se habilita autologging de prompts/respuestas. Solo se registran metadatos técnicos; Streamlit consulta la API y no abre SQLite directamente.
- **Evidencia local:** instalación editable reproducible, migraciones completas, identidad visual, compilación y 310 pruebas aprobadas.

La línea base inmediatamente anterior queda trazada por SPEC-021 (criterios ponderados sin
descarte automático) y SPEC-022 (integridad de CV, cola humana, filtros y fuente Adecco). Ambas
se verificaron nuevamente junto con esta actualización.

## Actualización consolidada — SPEC-004 (2026-09-10)

Esta sección prevalece sobre las descripciones iniciales que entren en conflicto con ella.

- **Nombre y flujo principal:** TalentIA. Es una sola aplicación con FastAPI y un cliente Streamlit; el analizador documental se ofrece como capacidad interna.
- **Capacidades entregadas:** alta y aprobación humana de vacantes, ingreso consentido de candidaturas PDF/DOCX, OCR local de respaldo, evaluación explicable, filtros determinísticos, anonimización antes del LLM, revisión humana, pipeline, Candidate 360, dashboard, auditoría y consulta Boolean manual para LinkedIn.
- **Arquitectura:** `app/domain` contiene reglas puras; `app/application` casos de uso y unidad de trabajo; `app/infrastructure` SQLite, documentos, seguridad y proveedores; `app/api` expone FastAPI; `ats_frontend` consume la API sin ejecutar reglas de negocio.
- **Gobierno de IA:** el modelo propone dimensiones estructuradas; los filtros, total, estados y acciones autorizadas se calculan en backend. El sistema rechaza instrucciones incrustadas, retira PII antes del proveedor y conserva evidencia/auditoría.
- **Persistencia:** SQLite local para el ATS y caché FAISS/SQLite con TTL de 24 horas para el analizador heredado. `.env`, claves, bases, almacenamiento y temporales están excluidos de Git.
- **Operacion vigente:** `python -m uvicorn talentia.main:app --host 127.0.0.1 --port 8000`.
- **Evidencia:** 256 pruebas aprobadas, seed reproducible, smoke de API/Streamlit y escáner de publicación aprobados. CI ejecuta escáner y pytest.
- **Límites vigentes:** laboratorio local y datos ficticios; SQLite y sesión de desarrollo no son aptos para producción multiusuario; Gmail permanece en borrador/DRY_RUN; no existe RSC, scraping ni automatización de LinkedIn; no cargar CV reales ni desplegar como servicio compartido sin revisión legal, de privacidad y seguridad.

## Actualización — SPEC-020 (2026-09-11)

- **Gestión de candidatos:** la pantalla Candidatos presenta una tabla general
  centralizada con búsqueda, filtros, selección, alta y edición de ficha completa.
- **Fuente de verdad:** la interfaz consume FastAPI y SQLite; CSV/XLSX queda solo
  como importación o exportación opcional.
- **Privacidad:** el DataFrame y el CSV omiten por completo las columnas PII cuando
  el rol no dispone de `candidate:pii:read`.
- **Evidencia:** 285 pruebas aprobadas, lint y compilación correctos, smoke de
  Streamlit sin red y guardado manual verificado sobre datos ficticios.

## Restricción de agentes de IA aprobada (2026-09-10)

- Todo componente catalogado como AI Agent usará LangGraph; las capacidades
  deterministas siguen como servicios Python.
- Los agentes dependen del puerto `LLMProvider`; Gemini será el primer adaptador
  y no aparecerá directamente en graphs, routers ni Streamlit.
- MLflow Tracing se integra centralmente con redacción de PII. Su caída, o la de
  Gemini, no bloquea el core ATS ni participa en commits de negocio.
- La free tier solo admite datos sintéticos. Enviar CV reales o PII permanece
  deshabilitado hasta aprobación explícita de Security/Legal.
- Estado, nodos, schemas, tools, guards, prompts versionados, límites,
  Human-in-the-Loop/checkpointing y pruebas por agente son obligatorios.
- Esta decisión está desarrollada en ADR-007 y no autoriza crear agentes antes
  de completar sus prerrequisitos de fase.

## 1. Nombre, misión y usuarios

- **Nombre vigente:** TalentIA.
- **Misión actual observada:** asistir a equipos de Recursos Humanos en la comparación de CV en PDF contra requisitos explícitos de un perfil de puesto, con puntaje documental reproducible y evidencia por página, sin automatizar decisiones de contratación.
- **Usuario principal observado:** analista o responsable de selección de personal.
- **Usuario heredado:** persona postulante que necesita interpretar una convocatoria. Este flujo sigue disponible en `streamlit_postulacion.py`, aunque la documentación principal dirige al flujo de RR. HH.
- **Misión de negocio definitiva y métricas de éxito:** `POR CONFIRMAR` por el responsable de producto.

## 2. Alcance actual y exclusiones

### Funcionalidades actuales verificadas

1. Carga de un perfil de puesto y entre uno y veinte CV en PDF.
2. Lectura normal con `pdfplumber` y respaldo con `pypdf`.
3. OCR local seleccionable con `pypdfium2`, `RapidOCR` y ONNX Runtime.
4. Extracción determinista de requisitos explícitos mediante reglas léxicas, conservando la página fuente.
5. Exclusión del puntaje de criterios sensibles detectados por una lista conservadora de patrones.
6. Puntaje entero de 0 a 100 por cobertura de términos, detalle por requisito y ranking estable por puntaje y nombre de archivo.
7. Aislamiento de errores por CV y límite de 20 MB por archivo en el flujo de RR. HH.
8. Consulta sobre el perfil y un CV seleccionado con recuperación local; redacción opcional mediante Gemini u Ollama y fallback léxico con citas.
9. Interfaz Streamlit con estado de chat en memoria de sesión, caché vectorial/respuestas local con TTL fijo de 24 horas, visualización aislada por perfil/CV, métricas de reutilización y borrado individual o total.
10. Flujo heredado de análisis de una convocatoria, extracción de requisitos/fechas/condiciones/alertas y chat con historial SQLite.

### Exclusiones declaradas por la especificación vigente

- Aprobar, rechazar, contactar o recomendar candidatos automáticamente.
- Inferir personalidad, salud, biometría o atributos personales sensibles.
- Integraciones con ATS, correo, calendarios o bolsas de trabajo.
- Autenticación, autorización, multiempresa y operación alojada en producción.
- Persistencia de expedientes de candidatos en el flujo de RR. HH.
- Verificación de autenticidad documental o de competencia profesional real.

## 3. Arquitectura y flujo de datos

### Componentes activos

| Componente | Responsabilidad observada |
|---|---|
| `ats_frontend/views/document_analysis.py` | Interfaz integrada de carga múltiple, resultados, advertencias y consulta por candidato. |
| `backend/pdf_reader.py` | Lectura normal y OCR local; entrega páginas como `PageText`. |
| `backend/cv_screening.py` | Extracción de criterios, filtro sensible, puntaje, ranking, carga aislada y contexto de consulta. |
| `backend/retrieval.py` | Normalización, tokenización, fragmentación y recuperación léxica. |
| `backend/rag_engine.py` | Recuperación híbrida y redacción opcional con Gemini. En RR. HH. se desactivan embeddings remotos. |
| `backend/agent.py` | Orquesta moderación, caché de respuestas, recuperación y fallbacks Gemini → Ollama → respuesta léxica. |
| `backend/cache_models.py` | Identidades SHA-256, versiones y contratos de la caché. |
| `backend/local_embeddings.py` | Adaptador FastEmbed local e inyectable. |
| `backend/vector_cache.py` | Fragmentos SQLite e índices FAISS por documento. |
| `backend/answer_cache.py` | Reutilización exacta y semántica de respuestas aislada por contexto; migración aditiva, listado minimizado, métricas locales y borrado individual. |
| `backend/cache_service.py` | Fachada de TTL, estadísticas, métricas y borrado individual/total seguro bajo `data/cache/`. |
| `backend/models.py` | Contratos internos mediante `dataclass`. |
| `backend/history.py` | Persistencia SQLite heredada; no es invocada por la interfaz principal de RR. HH. |
| `streamlit_postulacion.py` | Interfaz heredada para postulantes; analiza un PDF y persiste preguntas y respuestas. |
| `agente_postulacion/` | Capa heredada/compatibilidad. Parte de sus módulos duplica o antecede a `backend/`. |

### Flujo principal de RR. HH.

```text
Perfil PDF + CV PDF (bytes en Streamlit)
  → lectura normal u OCR local
  → PageText por página
  → reglas de requisitos + filtro de criterios sensibles
  → comparación léxica determinista por CV
  → ranking, brechas y evidencia en la sesión Streamlit
  → consulta opcional sobre perfil + un CV
      → moderación de entrada
      → caché de respuesta exacta/semántica del mismo contexto
      → registro local de hit exacto/semántico o un miss por interacción documental
      → FAISS local sobre el perfil y CV activos; fallback léxico
      → Gemini: solo fragmentos recuperados, si hay clave
      → Ollama local, si se activa
      → fallback extractivo local
```

Los PDF originales no se escriben a disco. `st.cache_data` limita la extracción a 24 horas y 64 entradas. La SPEC-003 persiste bajo `data/cache/` fragmentos derivados, embeddings FAISS y respuestas durante un TTL fijo de 24 horas. La interfaz lista únicamente metadatos minimizados del perfil/CV activos, permite borrar una respuesta sin tocar FAISS y conserva métricas agregadas hasta el borrado total. El borrado total elimina todo y desactiva su regeneración hasta reactivación explícita.

### Flujo heredado

```text
Convocatoria PDF
  → lectura y análisis por reglas
  → recuperación y respuesta opcional
  → interfaz Streamlit
  → pregunta, respuesta y nombre del documento en data/agente_postulacion.db
```

La base SQLite existe localmente y su conservación/borrado no está gobernado por una política documentada.

## 4. Tecnologías y versiones detectadas

### Restricciones declaradas

- Python 3.10 o superior según el manual.
- Streamlit `>=1.37,<2.0`.
- pdfplumber `>=0.10,<1.0`; pypdf `>=5,<7`.
- pypdfium2 `>=4.30,<5.0`; Pillow `>=10,<13`.
- RapidOCR `>=3.8,<4`; ONNX Runtime `>=1.20,<2`.
- LangChain y LangChain Community `>=0.2,<0.4`.
- LangChain Google GenAI `>=1,<3`; FAISS CPU `>=1.7.4`.
- FastEmbed `>=0.8,<0.9`; NumPy `>=2,<3`; modelo local multilingüe MiniLM de 384 dimensiones.
- pytest `>=8.3,<9`.

### Entorno local inspeccionado

- Python 3.13.7.
- Streamlit 1.61.1; pdfplumber 0.11.10; pypdf 6.15.0.
- RapidOCR 3.9.2; ONNX Runtime 1.28.0.
- LangChain 0.3.30; LangChain Community 0.3.31; LangChain Google GenAI 2.1.12.
- pytest 8.4.2.
- `python-dotenv` 1.2.2 está instalado y es importado por el producto, pero no está declarado directamente en `requirements.txt`.
- El entorno inspeccionado contiene pypdfium2 5.12.1, fuera del rango declarado `<5.0.0`; no debe considerarse una instalación reproducible de las restricciones actuales.

No existe archivo de bloqueo de dependencias Python. `skills-lock.json` corresponde a skills, no al runtime del producto.

## 5. Comandos reales

### Instalar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Ejecutar el flujo principal

```powershell
Comando retirado por SPEC-031; consultar el historial Git si se necesita evidencia.
```

### Ejecutar el flujo heredado

```powershell
Comando retirado por SPEC-031; consultar el historial Git si se necesita evidencia.
```

Este segundo comando se deduce del archivo ejecutable, pero no está presentado como ruta principal en `README.md`.

### Probar

```powershell
python -m pytest -q
```

Resultado observado el 2026-08-20 después de SPEC-003: **41 pruebas aprobadas** con clave Gemini vacía. La suite usa dobles de embeddings y no descarga modelos ni llama a proveedores. El modelo FastEmbed real se validó por separado con un vector finito de 384 dimensiones.

### Verificar estilo y tipos

`NO DISPONIBLE`: no se detectaron Ruff, Black, Flake8, mypy, pre-commit ni comandos equivalentes configurados.

## 6. Integraciones y fuentes de verdad

- **Gemini:** integración opcional mediante `langchain-google-genai`. En el flujo de RR. HH. la recuperación es local y se envían fragmentos al responder una pregunta; el proveedor sigue recibiendo posible información personal contenida en esos fragmentos.
- **Ollama:** endpoint local configurable con `OLLAMA_URL`; modelo predeterminado `llama3.2:3b` o `OLLAMA_MODEL`.
- **Google Fonts:** la interfaz principal importa fuentes desde `fonts.googleapis.com`; es una solicitud externa no mencionada en la documentación de privacidad.
- **SQLite:** historial heredado en `data/agente_postulacion.db` y metadatos/fragmentos/respuestas de SPEC-003 en `data/cache/cache.db`.
- **FAISS/FastEmbed:** índices persistentes por huella de documento; embeddings generados localmente con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **Observabilidad de caché:** métricas agregadas en SQLite local; LangSmith y cualquier telemetría externa están fuera del alcance actual.
- **Documentos cargados:** fuente de verdad para requisitos y evidencia durante cada ejecución.
- **Especificaciones de comportamiento:** `specs/000-hr-cv-screening/` verificada y `specs/003-cache-vectorial-respuestas/` en verificación.
- **Codigo ejecutable oficial:** `talentia.main:app`; el contenido anterior de esta seccion es
  exclusivamente historico.

## 7. Datos sensibles, propietarios y conservación

| Dato | Tratamiento observado | Propietario / conservación |
|---|---|---|
| CV, nombre de archivo y texto extraído | PDF original en memoria; fragmentos derivados e índices por SHA-256 bajo `data/cache/`. El nombre no es clave primaria. | TTL fijo de 24 horas o borrado manual; propietario: `POR CONFIRMAR`. |
| Perfil del puesto | PDF original en memoria; fragmentos e índice local con el mismo aislamiento. | TTL fijo de 24 horas o borrado manual; propietario: `POR CONFIRMAR`. |
| Preguntas y respuestas de RR. HH. | Sesión Streamlit y caché SQLite solo para respuestas documentales exitosas, aisladas por perfil/CV/ruta/versiones. La vista expone solo pregunta normalizada/truncada y metadatos. | TTL fijo de 24 horas o borrado individual/total; métricas agregadas hasta borrado total. |
| Fragmentos enviados a Gemini | Transmisión al proveedor solo durante consultas con clave válida. | Condiciones, región y retención del proveedor: `POR CONFIRMAR`. |
| API key Gemini | Variable de entorno o entrada de tipo contraseña durante la sesión. | Usuario/operador. Rotación y custodia: `POR CONFIRMAR`. |
| Historial heredado | Nombre de documento, pregunta, respuesta y fecha en SQLite. | Retención indefinida hasta borrado manual; propietario `POR CONFIRMAR`. |
| PDFs de `data/` y `output/` | El repositorio los describe como ficticios/de prueba. | Confirmación de anonimización y licencia: `POR CONFIRMAR`. |

No se observan autenticación, roles, cifrado de aplicación, consentimiento, auditoría, mecanismo de borrado ni política de conservación implementados.

## 8. Convenciones del repositorio

- Código y documentación orientados a español; nombres técnicos internos mayormente en inglés.
- Modelos internos con `dataclass`; lógica determinista separada de Streamlit.
- Pruebas con pytest y `monkeypatch`, sin red deliberadamente.
- Evidencia documental siempre asociada a número de página.
- El ranking se ordena por puntaje descendente y nombre de archivo como desempate estable.
- Las claves locales viven en `.env`, excluido por `.gitignore`; `.env.example` contiene solo marcadores.
- Las especificaciones viven en `specs/<id>-<slug>/` con `spec.md`, `plan.md`, `tasks.md` y `acceptance.md`.
- No hay una convención automatizada de formato, tipado, cobertura o commits documentada.

## 9. Restricciones de dependencias, despliegue y compatibilidad

- Aplicación local orientada a Windows 10/11; no hay artefacto de despliegue, contenedor ni CI detectado.
- La lectura OCR puede consumir memoria y tiempo de CPU; el límite actual es 20 CV y 20 MB por archivo, pero no hay límite de páginas ni presupuesto de tiempo.
- Gemini y Ollama son opcionales; el puntaje debe permanecer independiente de ambos.
- Deben preservarse las interfaces públicas usadas por pruebas y el flujo heredado hasta que exista una migración aprobada.
- No existe autenticación ni aislamiento multiusuario. No desplegar el prototipo como servicio compartido sin una especificación de seguridad y privacidad.
- La especificación verificada existente no se modifica durante esta inicialización.

## 10. Responsables y aprobaciones

- La especificación existente declara como owner genérico a “Product and engineering”.
- Responsable de aprobar alcance: `POR CONFIRMAR`.
- Responsable de privacidad y tratamiento de datos personales: `POR CONFIRMAR`.
- Responsable de seguridad: `POR CONFIRMAR`.
- Responsable de publicación/despliegue: `POR CONFIRMAR`.
- Responsable legal o de cumplimiento para criterios de selección laboral: `POR CONFIRMAR`.

Mientras no se asignen responsables, ningún cambio que amplíe tratamiento de CV, persistencia, proveedores externos, automatización de decisiones o despliegue compartido se considera aprobado.

## 11. Brechas detectadas y prioridad sugerida

| Prioridad | Brecha observada | Riesgo |
|---|---|---|
| Media | La caché local contiene fragmentos y respuestas sin cifrado de aplicación. | Requiere permisos de sistema operativo, uso local individual y borrado/TTL; no apta para despliegue compartido. |
| Alta | El flujo heredado persiste nombre, preguntas y respuestas en SQLite sin política ni borrado. | Contradicción con mensajes generales de privacidad y conservación indefinida. |
| Alta | No hay autenticación, autorización ni aislamiento de usuarios. | Impide un despliegue compartido seguro. |
| Media | Coexisten dos interfaces y dos árboles de módulos con comportamiento diferente. | Confusión operativa, regresiones y promesas de privacidad inconsistentes. |
| Media | `python-dotenv` no está declarado directamente; el entorno inspeccionado incumple el rango de pypdfium2. | Instalación no reproducible y fallos en entornos limpios. |
| Media | No existe CI, lint, tipado ni umbral de cobertura configurados. | Calidad depende de ejecución manual. |
| Media | Google Fonts realiza una solicitud externa no documentada. | Privacidad y funcionamiento offline incompletos. |
| Media | El filtro sensible se basa en patrones finitos en español. | Falsos negativos, variantes lingüísticas y requisitos sesgados no detectados. |
| Media | El puntaje sigue siendo estrictamente léxico; solo la consulta usa recuperación vectorial. | Sinónimos, negaciones y contexto pueden producir puntajes orientativos incompletos. |
| Baja | No hay límite de páginas, TTL de sesión ni presupuesto de OCR/LLM. | Agotamiento de recursos y latencia impredecible. |
| Baja | No hay estrategia de empaquetado, despliegue, observabilidad o recuperación. | El prototipo no tiene camino operativo definido. |

Estas brechas son diagnóstico, no alcance autorizado de implementación.
