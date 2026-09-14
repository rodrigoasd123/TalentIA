# Instalacion greenfield en Windows

## Requisitos

- Windows 10/11 de 64 bits.
- Python 3.12 de 64 bits disponible como `py -3.12`.
- Git para obtener el repositorio.
- Navegador moderno. Node.js y un proveedor LLM no son necesarios.

## Entorno limpio

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Use `.env.example` como lista de referencia, pero exporte las variables en PowerShell antes del
arranque; el runtime no carga el archivo `.env` automaticamente. No versionar secretos.

```powershell
$env:TALENTIA_ENV="desarrollo"
$env:TALENTIA_SESSION_SECRET="secreto-local-de-al-menos-32-caracteres"
$env:TALENTIA_ADMIN_EMAIL="admin@su-empresa.com"
$env:TALENTIA_ADMIN_PASSWORD="una-contrasena-segura"
```

## Preparacion y arranque

```powershell
.\scripts\migrate.ps1
.\scripts\verify_pilot.ps1
.\scripts\start_api.ps1
```

En otra terminal:

```powershell
.\scripts\start_worker.ps1
```

Abrir `http://127.0.0.1:8000/login`. Sin `TALENTIA_LLM_PROVIDER`, el sistema funciona en modo
determinista/manual.

Use `desarrollo` para esta prueba HTTP local. El ambiente `piloto` marca la cookie como segura y
requiere servir la aplicacion mediante HTTPS.

## Backup y restauracion

Detenga API y worker antes de una restauracion.

```powershell
.\scripts\backup.ps1 -Origen .\talentia_greenfield.db -Destino .\backups\talentia.db
.\scripts\restore.ps1 -Origen .\backups\talentia.db -Destino .\talentia_restaurada.db
```

Los comandos validan `PRAGMA integrity_check` y nunca sobrescriben el destino. Para usar la copia,
configure `TALENTIA_GREENFIELD_DATABASE_URL=sqlite:///./talentia_restaurada.db` y ejecute nuevamente
las migraciones.

## Dependencias

Las dependencias de runtime están en `[project.dependencies]` de `pyproject.toml`. Ruff, mypy,
pytest y pytest-cov pertenecen exclusivamente al extra `dev`. El soporte DOCX es parte del runtime
porque el piloto acepta ese formato.
