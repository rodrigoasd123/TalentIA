# TalentIA

TalentIA es un ATS asistido para el piloto de TCS. Administra candidatos, perfiles,
postulaciones, documentos, evaluaciones con evidencia, revision humana, lotes de proveedor,
exclusiones y auditoria. No aprueba, rechaza ni contrata automaticamente.

## Runtime oficial

La unica aplicacion mantenida vive en `src/talentia`:

- Backend y web: FastAPI + Jinja2 + HTMX.
- Persistencia del piloto: SQLite con WAL y migraciones Alembic.
- Orquestacion: LangGraph para el flujo durable de evaluacion.
- Ejecucion: Python 3.12. Node.js y Streamlit no son necesarios.

Los documentos de `specs/` y `docs/adr/` anteriores a la consolidacion se conservan
unicamente como trazabilidad historica.

## Inicio en Windows

Desde la raiz del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .

$env:TALENTIA_ENV="piloto"
$env:TALENTIA_SESSION_SECRET="genere-un-secreto-aleatorio-de-al-menos-32-caracteres"
$env:TALENTIA_ADMIN_EMAIL="admin@su-empresa.com"
$env:TALENTIA_ADMIN_PASSWORD="Ejemplo-Seguro-2026!"

.\scripts\migrate.ps1
.\scripts\start_api.ps1
```

Abra `http://127.0.0.1:8000/login`.

Para procesar trabajos de evaluacion, abra otra terminal:

```powershell
.\scripts\start_worker.ps1
```

### Contenedor opcional

Docker no es necesario en la computadora del piloto. Si esta disponible, la imagen usa el mismo
runtime `src/talentia` y recibe todos los secretos mediante variables de entorno:

```powershell
docker compose up --build
```

### Linea base de rendimiento

Con la API iniciada, el siguiente comando realiza solicitudes HTTP acotadas a `/health`, descarta
los cuerpos y reporta conteos, errores, promedio, p50 y p95 en JSON:

```powershell
.\.venv\Scripts\python.exe scripts\medir_rendimiento_piloto.py --solicitudes 50 --concurrencia 5
```

Un error HTTP o de conexion produce codigo de salida distinto de cero. Este resultado es una linea
base tecnica; no representa un SLA de TCS sin hardware y carga corporativos representativos.

No active un proveedor LLM ni cargue CV reales sin aprobacion de seguridad, privacidad y legal.
Sin proveedor, el sistema conserva el flujo manual y deterministico.

La guia completa esta en
[`docs/INSTALACION_GREENFIELD_WINDOWS.md`](docs/INSTALACION_GREENFIELD_WINDOWS.md).

## Desarrollo y verificacion

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\check_repository.py
.\.venv\Scripts\python.exe scripts\check_brand_identity.py
.\.venv\Scripts\ruff.exe check src\talentia migrations_greenfield tests\greenfield
.\.venv\Scripts\ruff.exe format --check src\talentia migrations_greenfield tests\greenfield
.\.venv\Scripts\mypy.exe src\talentia
.\.venv\Scripts\python.exe -m pytest -q tests\greenfield --basetemp .pytest-tmp
```

## Datos y recuperacion

- La base predeterminada es `talentia_greenfield.db`; esta excluida de Git.
- Los CV se almacenan fuera de los estaticos en `storage/greenfield`; tambien esta excluido.
- `scripts/backup.ps1` y `scripts/restore.ps1` realizan copias verificables sin sobrescribir.
- `scripts/seed_greenfield.py` genera unicamente datos ficticios para demostracion y nunca crea
  usuarios ni contrasenas. Las cuentas se provisionan exclusivamente mediante entorno.

## Benchmark opcional

MLflow es una herramienta offline de desarrollo y no una dependencia del piloto:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[benchmark]"
.\.venv\Scripts\python.exe scripts\ejecutar_benchmark_greenfield.py
```

El benchmark debe utilizar etiquetas humanas independientes antes de considerarse evidencia de
calidad o falso descarte.

## Arquitectura y gobierno

- Arquitectura: [`docs/architecture.md`](docs/architecture.md)
- API: [`docs/api.md`](docs/api.md)
- Seguridad: [`docs/security.md`](docs/security.md)
- Runbook: [`docs/pilot_runbook.md`](docs/pilot_runbook.md)
- Constitucion SDD: [`docs/sdd/constitucion.md`](docs/sdd/constitucion.md)
- Consolidacion del runtime: [`specs/031-consolidacion-runtime-greenfield/`](specs/031-consolidacion-runtime-greenfield/)
- Cierre de operabilidad: [`specs/032-cierre-operabilidad-rubrica/`](specs/032-cierre-operabilidad-rubrica/)
