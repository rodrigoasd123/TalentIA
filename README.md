# TalentIA — ATS gobernado de selección

TalentIA consolida PostulaIA con **VERA ATS**. El ATS principal permite administrar vacantes, candidaturas, evaluación explicable, revisión humana, pipeline, Candidate 360 y auditoría. El analizador documental anterior permanece disponible como rollback.

> **Entorno de laboratorio:** usa únicamente datos ficticios. No cargues CV reales ni despliegues el sistema como servicio compartido sin aprobación legal, de privacidad y seguridad.

## Inicio rápido del ATS en Windows (Python 3.12)

La versión reproducible y validada por CI y Docker es **Python 3.12**. Otras
versiones pueden funcionar, pero no forman parte de la matriz de pruebas.

No necesitas activar PowerShell. Desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed.py --reset
```

Abre dos terminales. En la primera inicia la API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

En la segunda inicia la interfaz:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ats_frontend/streamlit_app.py
```

Visita `http://localhost:8501`. La documentación de la API está en `http://127.0.0.1:8000/docs`. En desarrollo local la interfaz usa una sesión limitada de recruiter; los entornos distintos de `development` exigen autenticación real.

Si PowerShell bloquea `Activate.ps1`, `pip` muestra `Permission denied` o
aparece `ModuleNotFoundError`, consulta la
[guía de instalación y solución de problemas](docs/INSTALACION_WINDOWS.md).
Los comandos anteriores invocan directamente el Python de `.venv`, por lo que
no necesitan cambiar la política de ejecución del sistema.

El adaptador simulado funciona sin API key. Gemini se configura opcionalmente desde **Configuración** y el secreto queda cifrado en la base local; nunca debe escribirse en el repositorio. Los correos permanecen en borrador y `DRY_RUN`.

`alembic upgrade head` es la vía normal para actualizar el esquema. `seed.py
--reset` elimina y recrea únicamente la base local configurada, por lo que debe
usarse solo con datos prescindibles. Una base creada por versiones anteriores
sin `alembic_version` debe respaldarse y recrearse; el sistema no adopta ni
marca automáticamente un esquema desconocido.

## Importación histórica CSV/XLSX

La página **Importación Histórica** permite cargar un archivo, seleccionar una
hoja XLSX, revisar el mapeo sugerido, corregirlo y guardar una plantilla. La
validación ocurre en staging y no modifica candidatos ni candidaturas. Solo un
HR Manager puede confirmar filas elegibles.

- Límites iniciales: 20 MB y 10 000 filas, configurables con
  `VERA_IMPORT_MAX_FILE_MB` y `VERA_IMPORT_MAX_ROWS`.
- Identidad fuerte: documento, correo normalizado o teléfono normalizado. Un
  nombre sin esos datos permanece en revisión manual y no crea un candidato.
- Todo candidato histórico nuevo entra como `restricted_review` y con estado
  legal `unknown`; queda fuera de IA, redescubrimiento, contacto automático e
  intercambio con proveedores hasta una revisión autorizada.
- El archivo se guarda con una clave generada bajo
  `VERA_IMPORT_STORAGE_PATH`; nunca se utiliza el nombre recibido como ruta.

Para probar la confirmación en el laboratorio usa
`manager@vera-lab.test / Laboratorio-VERA-2026!`. Todos los datos de prueba
deben ser ficticios.

## Ejecución con Docker

El contenedor también usa Python 3.12 y SQLite en un volumen local compartido:

```powershell
docker compose build
docker compose run --rm api python scripts/seed.py --reset
docker compose up
```

API: `http://localhost:8000`; Streamlit: `http://localhost:8501`. Este compose
es para el piloto local y no sustituye controles de producción.

## Recorrido recomendado

1. En **Ingreso**, crea y aprueba una vacante o usa las fixtures sembradas.
2. Registra una candidatura ficticia con consentimiento y carga PDF/DOCX.
3. Ejecuta la evaluación: filtros y total se calculan en backend; el modelo solo propone dimensiones estructuradas.
4. Resuelve alertas desde **Revisión** y mueve estados autorizados en el pipeline.
5. Consulta Candidate 360 y verifica la cadena en **Auditoría**.
6. Desde **Vacantes**, genera una consulta Boolean para copiar manualmente a LinkedIn Recruiter. La aplicación no navega ni extrae datos de LinkedIn.

## Rollback al analizador documental anterior

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_postulacion.py
```

Este comando mantiene la carga múltiple, OCR, ranking documental y consulta RAG previos; su base de datos no es la fuente de verdad del ATS.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp
.\.venv\Scripts\ruff.exe check app ats_frontend tests
.\.venv\Scripts\mypy.exe
```

---
# Analizador documental heredado

PostulaIA ayuda a un equipo de Recursos Humanos a comparar varios CV en PDF frente a un perfil de puesto. Extrae requisitos verificables, calcula una coincidencia documental reproducible y muestra la evidencia por página. El resultado sirve para priorizar la revisión; **no aprueba, rechaza ni recomienda contratar candidatos**.

## Flujo del producto

```text
Perfil del puesto ─┐
                   ├─ lectura normal/OCR ─ criterios verificables ─ comparador local ─ ranking + evidencia
CV 1..20 ──────────┘                                                        │
                                                                            └─ RAG opcional Gemini/Ollama
```

El puntaje no depende de Gemini ni de Ollama. Para cada requisito, el comparador calcula la proporción de términos presentes en el CV y promedia las coberturas. Los criterios sensibles, como edad, género, estado civil, religión o fotografía, se excluyen automáticamente del puntaje y se muestran como advertencia.

## Estructura

```text
PostulaIA/
├── backend/
│   ├── cv_screening.py       → criterios, filtro sensible, puntaje y ranking
│   ├── pdf_reader.py         → lectura PDF normal y OCR local
│   ├── rag_engine.py         → recuperación FAISS/léxica y Gemini opcional
│   ├── agent.py              → agente de consulta con evidencia
│   ├── vector_cache.py       → índices FAISS persistentes por documento
│   ├── answer_cache.py       → respuestas exactas/semánticas en SQLite
│   ├── cache_service.py      → TTL, estadísticas y borrado seguro
│   └── history.py            → componente heredado; no se usa en el flujo de RR. HH.
├── frontend/
│   └── streamlit_postulacion.py
├── specs/000-hr-cv-screening/ → especificación SDD, plan, tareas y aceptación
├── tests/
├── requirements.txt
└── MANUAL_USUARIO.md
```

## Instalación y ejecución en Windows

Descarga y descomprime el ZIP (o clona el repositorio), abre PowerShell dentro de la carpeta del proyecto y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_postulacion.py
```

No es necesario ejecutar `Activate.ps1`; invocar el Python del entorno directamente evita los bloqueos de políticas de ejecución de PowerShell. La instalación se realiza una sola vez. En ejecuciones posteriores basta con usar el último comando.

Abre `http://localhost:8501` si el navegador no se inicia automáticamente.

## Uso

1. Elige **Normal** para PDF con texto seleccionable u **OCR** para escaneos.
2. Carga un PDF con el perfil del puesto o la convocatoria.
3. Carga entre uno y veinte CV en PDF.
4. Revisa el ranking orientativo y abre el detalle de cada requisito.
5. Selecciona un candidato y consulta al agente para contrastar el perfil con ese CV.
6. Valida siempre el documento fuente antes de tomar una decisión laboral.

Un CV ilegible no detiene el resto del lote. Si el perfil no contiene requisitos explícitos, la aplicación no inventa criterios ni genera un ranking.

## IA y privacidad

- La lectura, OCR, fragmentación, criterios y puntaje se ejecutan localmente.
- Los PDF originales y las API keys no se guardan en la caché.
- Bajo `data/cache/` se conservan localmente fragmentos, embeddings FAISS y respuestas reutilizables durante un TTL fijo de 24 horas. Son datos derivados potencialmente personales.
- La caché se aísla por SHA-256 del perfil y CV, versiones del modelo, prompt y moderación; nunca reutiliza respuestas entre CV distintos.
- La pestaña **Caché local** muestra, solo para el perfil y CV activos, la pregunta normalizada y truncada, ruta, creación, vencimiento y cantidad de reutilizaciones; no expone la respuesta ni su evidencia.
- Las métricas locales distinguen aciertos exactos, aciertos semánticos y fallos; la tasa se calcula sobre esos eventos y las llamadas evitadas equivalen a los aciertos. Se conservan hasta el borrado total.
- RR. HH. puede borrar una respuesta concreta con confirmación sin afectar documentos, índices ni métricas históricas, o borrar toda la caché desde **Caché vectorial local · 24 h**. Después del borrado total queda desactivada hasta pulsar **Reactivar caché local**.
- Sin API key, el chat usa recuperación vectorial local cuando está disponible y conserva el fallback léxico con citas.
- Con Gemini, la recuperación es local y solo se envían los fragmentos recuperados del perfil y del CV seleccionado al hacer una pregunta.
- La clave pegada en la interfaz vive solo en la sesión. `.env` permanece excluido de Git.
- Ollama permite redactar respuestas localmente con `llama3.2:3b`.

La búsqueda vectorial usa FastEmbed con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensiones). La primera consulta descarga el modelo local, aproximadamente 200–250 MB. Si el modelo, SQLite o FAISS fallan, el chat continúa con recuperación léxica y el ranking no cambia. Esta versión depende de los permisos del sistema operativo, no cifra la caché a nivel de aplicación y está limitada a uso local por una sola persona; no debe desplegarse como servicio compartido.

## Configuración opcional

Copia `.env.example` a `.env` y configura una clave personal solo para desarrollo local:

```text
GEMINI_API_KEY=tu_clave
```

No publiques una clave personal. Cada usuario debe usar la suya.

## Pruebas

```powershell
python -m pytest -q
```

La trazabilidad de requisitos y evidencia se encuentra en `specs/000-hr-cv-screening/` y `specs/003-cache-vectorial-respuestas/`.
