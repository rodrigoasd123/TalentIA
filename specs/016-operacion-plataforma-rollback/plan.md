# Plan — SPEC-016

## Resumen técnico

Documentar retrospectivamente la operación reproducible: Python 3.12 validado, dependencias, Alembic, seed ficticio, API/UI separadas, Docker, CI y entrada heredada de rollback.

## Arquitectura y límites afectados

- `requirements.txt`, `pyproject.toml`, Dockerfile/Compose y workflow CI.
- `alembic.ini`, `migrations/`, sesión SQLAlchemy y `scripts/seed.py`.
- `README.md`, `docs/INSTALACION_WINDOWS.md` y entrypoint heredado.
- Suites `tests/`, `tests/ats/` y scanner del repositorio.

## Flujo de datos

Entorno limpio → Python 3.12 → dependencias → `alembic upgrade head` → fixtures → FastAPI + Streamlit → health/smoke. Rollback: ejecutar el analizador heredado, que no usa la base ATS como fuente de verdad.

## Decisiones y alternativas

- Python 3.12 como matriz reproducible de CI/Docker.
- Invocar el Python de `.venv` sin `Activate.ps1`.
- Alembic como única evolución normal del esquema.
- SQLite para laboratorio; PostgreSQL/HA quedan fuera de alcance.

## Compatibilidad, transición y reversión

Alembic es la transición oficial. Una base sin `alembic_version` se respalda y recrea; no se marca automáticamente. La interfaz heredada permanece como rollback.

## Seguridad, privacidad y fallos

Fixtures ficticias, secretos fuera de Git y scanner obligatorio. `seed.py --reset` se limita a datos prescindibles. Una instalación incompleta se recupera en otro entorno sin borrar el anterior.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-016-001 | CI/sistema | instalación, suite, health y smoke |
| AC-016-002 | migración | Alembic sobre SQLite vacío |
| AC-016-003 | regresión | suite heredada y comando de rollback |

## Riesgos y mitigaciones

- Dependencias globales: comandos con `.venv` explícito.
- Política PowerShell: no se requiere activación.
- Esquema desconocido: respaldo y recreación controlada.
- Secretos/PII: `.gitignore` y scanner.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
