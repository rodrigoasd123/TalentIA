# Instalación de TalentIA en Windows

## Requisitos previos

- Windows 10 u 11.
- Python 3.12 de 64 bits. Es la versión utilizada por CI y Docker.
- Git, si se clonará el repositorio. También se puede descargar el ZIP.
- Aproximadamente 2 GB libres para el entorno, OCR y modelos locales.

Comprueba que Python 3.12 esté disponible:

```powershell
py -3.12 --version
```

## Instalación recomendada

Ejecuta estos comandos desde la raíz del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed.py --reset
```

`seed.py --reset` recrea la base local y debe usarse únicamente con datos de
laboratorio prescindibles. En una instalación con datos que deban conservarse,
omite ese comando.

No es necesario activar el entorno virtual. Invocar
`.\.venv\Scripts\python.exe` evita el bloqueo habitual de `Activate.ps1` por la
política de ejecución de PowerShell y garantiza que `pip` instale dentro del
entorno correcto.

## Iniciar TalentIA

Abre dos terminales en la raíz del proyecto. En la primera ejecuta la API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

En la segunda ejecuta la interfaz:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ats_frontend/streamlit_app.py
```

Abre `http://localhost:8501`. La API debe responder en
`http://127.0.0.1:8000/health` y su documentación está en
`http://127.0.0.1:8000/docs`.

## Solución de problemas

### PowerShell bloquea `Activate.ps1`

No cambies la política de ejecución. Usa directamente los comandos con
`.\.venv\Scripts\python.exe` mostrados en esta guía.

### `ModuleNotFoundError`, por ejemplo `pdfplumber`

Normalmente significa que Streamlit se ejecutó con otro Python o que la
instalación quedó incompleta. Verifica e instala con el mismo intérprete:

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -c "import pdfplumber; print(pdfplumber.__version__)"
```

Después inicia Streamlit mediante
`.\.venv\Scripts\python.exe -m streamlit`; no uses `streamlit run` a secas.

### `Permission denied` dentro de la caché de `pip`

Cierra otros procesos de instalación y repite la instalación sin reutilizar la
caché:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
```

Si el entorno quedó parcialmente instalado, crea uno nuevo con otro nombre sin
borrar el anterior:

```powershell
py -3.12 -m venv .venv-clean
.\.venv-clean\Scripts\python.exe -m pip install --upgrade pip
.\.venv-clean\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
```

### `py -3.12` no encuentra una instalación

Instala Python 3.12 de 64 bits desde python.org y vuelve a abrir PowerShell. No
uses Microsoft Store si el alias `python` redirige a una instalación distinta.

### Verificación mínima

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import fastapi, streamlit, pdfplumber, sqlalchemy; print('Dependencias OK')"
```

La clave de Gemini es opcional. Nunca debe escribirse en `requirements.txt`, en
esta guía ni en ningún archivo que se publique. Configúrala desde la aplicación
o en un archivo `.env` local excluido por Git.