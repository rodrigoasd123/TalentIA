# TalentIA — selección y análisis documental gobernados

TalentIA es una sola aplicación para administrar vacantes, candidatos, CV,
postulaciones, evaluaciones, revisión humana, pipeline, Candidate 360,
comunicaciones, importaciones, reportes, auditoría y análisis documental con OCR,
ranking y consulta RAG basada en evidencia.

> Entorno de laboratorio: usa únicamente datos ficticios. No cargues CV reales ni
> despliegues el sistema como servicio compartido sin aprobación legal, de privacidad
> y seguridad.

## Inicio rápido en Windows

TalentIA requiere Python 3.12. Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed.py --reset
```

`seed.py --reset` elimina la base configurada: úsalo exclusivamente con datos
prescindibles. Inicia la API y la interfaz en terminales separadas:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m streamlit run ats_frontend/streamlit_app.py
```

Interfaz: `http://localhost:8501`. API: `http://127.0.0.1:8000/docs`.

## Configuración

Las variables oficiales usan el prefijo `TALENTIA_`. Consulta `.env.example`.
Durante dos versiones menores se aceptan aliases con prefijo `VERA_`; TalentIA
siempre tiene prioridad y emite una advertencia que no contiene el valor.

Los secretos de desarrollo nuevos se guardan en `.talentia_dev_key`. Si existe
únicamente el archivo de clave heredado, se copia de forma compatible. Si ambos
archivos difieren, el arranque se detiene.

## Base de datos SQLite

La fuente de verdad es `talentia.db`, gobernada por SQLAlchemy y Alembic. CSV y
Excel solo sirven para importación histórica y exportación controlada.

Cuando se usa la URL predeterminada:

- sin bases existentes, TalentIA crea `talentia.db`;
- con solo `talentia.db`, la usa y aplica migraciones pendientes;
- con solo `vera.db`, crea respaldo y copia verificados mediante SHA-256,
  `PRAGMA integrity_check`, revisión Alembic y conteos antes de promover una copia
  atómicamente;
- con ambas bases, no modifica ninguna y exige seleccionar una ruta explícita con
  `TALENTIA_DATABASE_URL`.

Los respaldos y sus manifiestos quedan en `.talentia-backups/`. El archivo de origen
no se elimina automáticamente. Para revertir: detén TalentIA, verifica el SHA-256
del respaldo indicado en el manifiesto y cópialo a una ruta desocupada; nunca
sobrescribas una base existente. Después configura esa ruta mediante
`TALENTIA_DATABASE_URL` y ejecuta `alembic current` antes de iniciar.

Una URL configurada explícitamente nunca se mueve ni renombra automáticamente.

## Operación

1. Crea y aprueba una vacante.
2. Gestiona la tabla general de candidatos desde **Candidatos**: busca, filtra,
   selecciona una fila para editarla o registra una persona nueva.
3. Ejecuta evaluaciones y resuelve revisiones humanas.
4. Gestiona estados por postulación y vacante desde Pipeline.
5. Usa **Análisis documental** para comparar PDF, ejecutar OCR local y consultar
   evidencia RAG dentro de la misma navegación.
6. Consulta Candidate 360, reportes y auditoría.

La importación CSV/XLSX y la exportación CSV son mecanismos opcionales. La tabla
general siempre se carga desde FastAPI y persiste sus cambios en SQLite.

El puntaje documental es orientativo. El agente no cambia estados, no envía correos
y no decide contrataciones.

## Compatibilidad interna

Algunos identificadores heredados permanecen deliberadamente: revisiones Alembic,
eventos históricos, nombres internos de adaptadores, emisor JWT temporal y el salt
criptográfico usado para descifrar secretos existentes. No representan productos
separados y no deben renombrarse destruyendo trazabilidad o compatibilidad.

El entrypoint documental anterior se conserva temporalmente como rollback técnico
no enlazado. La navegación y operación ordinaria se realizan exclusivamente desde
`ats_frontend/streamlit_app.py`.

## Brechas conocidas

El piloto no implementa todavía cifrado de todas las columnas PII en reposo,
política corporativa de retención/eliminación ni backups operativos administrados.
SQLite y la sesión de desarrollo no son adecuados para producción multiusuario.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp
.\.venv\Scripts\ruff.exe check app ats_frontend tests
.\.venv\Scripts\mypy.exe
```

La especificación vigente de consolidación está en
`specs/019-consolidacion-definitiva-talentia/`.
