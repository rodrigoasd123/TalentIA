# Runbook del piloto greenfield

## Preparacion

1. Instalar Python 3.12 y crear `.venv`.
2. Instalar `pip install -e ".[dev]"`.
3. Configurar secreto de sesion y administrador mediante variables `TALENTIA_*`.
4. Ejecutar `scripts/migrate.ps1` y `scripts/verify_pilot.ps1`.

## Operacion

Iniciar `scripts/start_api.ps1` y, en otra terminal, `scripts/start_worker.ps1`. Abrir
`http://127.0.0.1:8000/login`. Sin proveedor IA, los trabajos pasan a revision manual.

## Recuperacion

Detener API y worker. Ejecutar `scripts/backup.ps1`. Para comprobar una recuperacion, usar
`scripts/restore.ps1 -Origen <respaldo>`; nunca sobrescribe una base existente. Configure
`TALENTIA_GREENFIELD_DATABASE_URL` con la copia restaurada y ejecute migraciones.

## Limites

Piloto local, datos ficticios y un unico equipo. No desplegar como servicio compartido hasta
aprobar identidad, retencion, BGC/Equifax, responsables de seguridad, privacidad y publicacion.

