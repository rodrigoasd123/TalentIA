# Checklist de despliegue y rollback - fase 8

## Antes del despliegue

- [x] Rama aislada de `main` y commits separados por fase.
- [x] Suite greenfield, regresion, Ruff, formato, mypy y escaner aprobados.
- [x] Instalacion limpia de Windows y `pip check` aprobados.
- [x] Migraciones reversibles y backup/restauracion verificados.
- [x] UAT tecnica con datos sinteticos ejecutada.
- [x] `BIZ-001..010` explicitamente fuera del alcance del piloto.
- [x] Sin secretos, bases SQLite, CV, PII ni temporales versionados.
- [ ] Aceptacion funcional firmada por RR. HH. de TCS.
- [ ] Aprobacion expresa del propietario para promover o fusionar.

## Despliegue local del piloto

1. Seguir `docs/INSTALACION_GREENFIELD_WINDOWS.md`.
2. Configurar secretos `TALENTIA_*` fuera de Git.
3. Crear un respaldo integro de la base vigente.
4. Ejecutar `scripts/migrate.ps1` y `scripts/verify_pilot.ps1`.
5. Iniciar API y worker; comprobar login, un listado y un trabajo sintetico.
6. Conservar el respaldo y registrar la revision Alembic desplegada.

## Rollback

1. Detener API y worker.
2. Conservar la base fallida sin sobrescribirla.
3. Ejecutar `scripts/restore.ps1 -Origen <respaldo> -Destino <base-limpia>`.
4. Apuntar `TALENTIA_GREENFIELD_DATABASE_URL` a la copia restaurada.
5. Ejecutar migraciones hasta la revision aprobada y `scripts/verify_pilot.ps1`.
6. Reiniciar y validar login, integridad y acceso por cliente.

## Condiciones de bloqueo

No desplegar ni fusionar si falla una puerta, si aparece PII en el diff, si se necesita resolver una
decision BIZ o si falta autorizacion expresa. La base historica y `main` permanecen intactos.
