# Plan — SPEC-005

## Resumen técnico

Cerrar primero la brecha de migraciones de PHASE 0 con Alembic y después añadir
un módulo de importación histórica sobre la arquitectura existente. FastAPI
recibe el archivo, un adaptador tabular seguro obtiene encabezados y filas,
la capa de aplicación gestiona staging, clasificación y confirmación, y
Streamlit consume exclusivamente la API.

## Arquitectura y límites afectados

- `app/core/config.py`: límites configurables de importación.
- `app/domain/imports.py` y `app/domain/ports.py`: estados, clasificaciones y puertos.
- `app/infrastructure/database/models.py`: lote, filas y plantillas; estado legal del candidato.
- `app/infrastructure/imports/`: lectura CSV/XLSX sin ejecutar fórmulas ni enlaces.
- `app/infrastructure/repositories/`: persistencia SQLAlchemy portable.
- `app/application/use_cases/historical_import.py`: reglas y transacción.
- `app/api/`: contratos y rutas versionadas con RBAC.
- `ats_frontend/`: cliente y página de importación.
- `migrations/`: baseline y migración SPEC-005.

## Flujo de datos

```text
archivo -> validación/límite/checksum -> ImportBatch UPLOADED
       -> mapeo sugerido/manual -> staging VALIDATING
       -> normalización + duplicados + reglas -> preview
       -> confirmación HR -> Candidate/Application + auditoría -> IMPORTED
```

## Decisiones y alternativas

- CSV se procesa con la biblioteca estándar y XLSX con `openpyxl` en modo
  lectura y `data_only`; pandas no entra en dominio ni es obligatorio para el flujo.
- El archivo temporal usa nombre generado y almacenamiento privado local.
- Los candidatos históricos sin base validada usan `RESTRICTED_REVIEW` y
  `legal_basis_status=unknown`; se preserva el consentimiento existente.
- El nombre sin identificador fuerte nunca crea un Candidate automáticamente.
- La confirmación reutiliza candidatos exactos y omite conflictos ambiguos.

## Compatibilidad, transición y reversión

- Migración aditiva; no elimina ni renombra columnas existentes.
- Los candidatos existentes reciben estado `allowed` para preservar comportamiento.
- Reversión de código: retirar rutas/UI; los datos de importación pueden quedar
  inertes. El downgrade de Alembic elimina solo tablas/columnas nuevas y no se
  ejecutará automáticamente.

## Seguridad, privacidad y fallos

- Permisos separados para cargar/ver/confirmar importaciones.
- Sin PII en logs o eventos; auditoría guarda IDs y conteos.
- Rechazo de macros, libros cifrados, encabezados duplicados y archivos que
  excedan límites.
- Neutralización de fórmulas en reportes CSV.
- Rollback de toda la confirmación si una creación falla.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-001 | automatizada | `tests/ats/test_historical_import.py` carga e idempotencia |
| AC-002 | automatizada | sugerencias, mapeo y contratos API |
| AC-003 | automatizada | staging sin escritura operativa |
| AC-004 | automatizada | clasificación exacta/manual/activa |
| AC-005 | automatizada | autorización, commit y rollback |
| AC-006 | automatizada | `RESTRICTED_REVIEW` bloquea procesamiento |
| AC-007 | automatizada | exportación neutralizada y minimizada |
| AC-008 | automatizada | cancelación y auditoría |

## Riesgos y mitigaciones

- Bloqueo SQLite: lote máximo configurable y confirmación breve.
- Archivos heterogéneos: mapeo explícito y errores por fila.
- Compatibilidad del esquema existente: baseline Alembic y migraciones aditivas.

## Aprobación

- [x] Plan aprobado por la persona responsable mediante la directiva de ejecución del 2026-09-10.
