# Pendientes de implementacion de TalentIA

## Proposito

Este documento permite que otra IA continue `SPEC-030` sin rehacer trabajo ni inventar reglas.
La fuente funcional completa es `IMPLEMENTATION_SPEC.md` y el flujo SDD vive en
`specs/030-reconstruccion-greenfield-talentia/`.

## Estado Git

- Rama: `codex/implementacion-greenfield-talentia`.
- Base sincronizada originalmente con `origin/main` en `97b7c7c`.
- Runtime nuevo: `src/talentia/`.
- Runtime anterior: se conserva solamente como rollback; no ampliar Streamlit.
- Base nueva: `talentia_greenfield.db`, administrada con `alembic_greenfield.ini`.

## Capacidades terminadas

1. Arquitectura greenfield FastAPI, Jinja2, HTMX, Bootstrap local, SQLAlchemy y Alembic.
2. Autenticacion, RBAC, alcance por cliente, CSRF, cabeceras seguras y auditoria encadenada.
3. Base general de candidatos, preflight de identidad, alta API/web, busqueda, ficha y traza.
4. Optimistic locking por campos: fusiona cambios disjuntos y devuelve conflicto en solapados.
5. Staging y confirmacion idempotente de CSV/XLSX; crea candidatos y excolaboradores reales.
6. Excolaboradores almacenados con hash de documento, nunca con el documento crudo.
7. Perfiles versionados, postulaciones, uploads seguros, jobs, checkpoints y modo manual.
8. Agentes deterministicos, guardrails de PII/inyeccion, LangGraph y corpus golden sintetico.
9. Scripts Windows de migracion, arranque, worker, backup, restore y verificacion.
10. Administracion de acceso mediante API y web: asignacion idempotente de roles/clientes,
    auditoria y bloqueo de autoampliacion de privilegios.

## Pendientes implementables sin decisiones nuevas

### 1. Pantallas operativas restantes

Reemplazar `src/talentia/web/templates/modulo.html` por vistas y formularios reales para perfiles,
postulaciones, documentos, trabajos, lotes, excolaboradores y metricas. Mantener reglas en la capa
de aplicacion, filtros del servidor, CSRF y alcance por cliente. Agregar pruebas E2E de cada flujo.

### 2. Evaluacion y revision humana completas

Persistir resultados de `evaluations`, `requirement_assessments`, `human_reviews` y
`field_corrections`; crear casos de uso y endpoints para aceptar/corregir sugerencias y resolver
revisiones. El worker debe guardar el checkpoint antes de interrumpir y reanudarse sin duplicar.
La ausencia de evidencia debe quedar como `requiere_revision`, nunca como incumplimiento.

### 3. Observabilidad y rendimiento

Persistir eventos de metricas del piloto, tiempos de request/job/agente y errores sanitizados.
Crear benchmark reproducible con volumen representativo y documentar resultados reales.

### 4. Suite historica

La suite greenfield pasa, pero la suite completa historica no recolecto en el entorno local porque
faltaba la dependencia declarada `langchain_openai`. Instalar el proyecto con `pip install -e
".[dev]"` en un entorno limpio y ejecutar `pytest -q`; no acoplar el runtime nuevo al anterior para
forzar el resultado.

## Decisiones bloqueadas: no inventar

`BIZ-001` vigencia de descarte; `BIZ-002` reapertura de no apto; `BIZ-003` reversa de blacklist;
`BIZ-004` umbral de nombres; `BIZ-005` requisito obligatorio sin evidencia; `BIZ-006` CV util;
`BIZ-007` retencion; `BIZ-008` alcance global o cliente de identidad; `BIZ-009` correspondencia de
estados; `BIZ-010` BGC/Equifax. Mantener fallo cerrado o revision humana hasta recibir definicion.

## Verificacion obligatoria al continuar

```powershell
$env:PYTHONPATH = "src"
pytest -q tests/greenfield
ruff check src/talentia migrations_greenfield tests/greenfield
ruff format --check src/talentia migrations_greenfield tests/greenfield
mypy src/talentia
python scripts/check_repository.py
```

Actualizar `tasks.md` y `verification.md` solo con evidencia ejecutada. No declarar completa la
Definition of Done global mientras exista una decision `BIZ` requerida o una tarea P0/P1 abierta.
