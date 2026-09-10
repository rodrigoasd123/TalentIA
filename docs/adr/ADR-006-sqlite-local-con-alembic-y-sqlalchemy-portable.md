# ADR-006 — SQLite local con Alembic y SQLAlchemy portable

- **Estado:** Aceptada
- **Fecha:** 2026-09-10

## Contexto

El piloto de TalentIA debe ejecutarse únicamente con Python, FastAPI, Streamlit
y SQLite. Al mismo tiempo, el esquema necesita cambios reproducibles y no debe
acoplar la lógica de negocio a detalles exclusivos de SQLite.

## Decisión

SQLite es la base local y la fuente de verdad del piloto. SQLAlchemy 2 gestiona
la persistencia y Alembic es la única vía de evolución del esquema fuera de las
bases efímeras de pruebas. Los modelos evitan tipos y consultas exclusivos del
motor para conservar una ruta futura a PostgreSQL, sin afirmar compatibilidad
hasta que exista una suite ejecutada contra ese motor.

## Justificación

SQLite satisface la restricción operativa y reduce la infraestructura del
laboratorio. Alembic permite reproducir, auditar y revertir cambios de esquema;
SQLAlchemy mantiene el límite entre dominio y persistencia.

## Consecuencias

- El despliegue local no necesita un servicio de base de datos adicional.
- Cada cambio de esquema requiere una revisión Alembic versionada.
- Las confirmaciones masivas son transacciones breves y limitadas para reducir
  contención de escritura en SQLite.
- La portabilidad es un objetivo arquitectónico, no una garantía verificada.
- Una base local anterior a Alembic debe respaldarse y recrearse o adoptarse de
  forma explícita; el arranque no marca automáticamente esquemas desconocidos.

## Alternativas descartadas

- PostgreSQL en el piloto: contradice la restricción operativa vigente.
- `Base.metadata.create_all()` en producción: no versiona ni permite revisar la
  evolución del esquema.
- SQL escrito directamente desde Streamlit: rompe la API como frontera y el
  control transaccional del backend.
