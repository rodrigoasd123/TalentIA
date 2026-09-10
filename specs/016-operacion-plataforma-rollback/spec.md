---
id: SPEC-016
titulo: Operación, persistencia y rollback
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004,SPEC-005
actualizado: 2026-09-10
---

# SPEC-016 — Operación, persistencia y rollback

## Propósito

Mantener un laboratorio reproducible, migrable y recuperable, con CI y una ruta explícita hacia el analizador documental heredado.

## Alcance vigente

- Python 3.12 como versión validada, instalación por `requirements.txt` y ejecución sin activar PowerShell.
- FastAPI y Streamlit como procesos separados.
- SQLite gobernado por Alembic; seed ficticio reproducible.
- Dockerfile/Compose para laboratorio.
- CI con escáner, pruebas, Ruff/MyPy focal y migración desde base vacía.
- Entry point heredado como rollback temporal.

## Fuera de alcance

Alta disponibilidad, backups administrados, PostgreSQL verificado, observabilidad productiva, Kubernetes y despliegue público con CV reales.

## Requisitos heredados

- **FR-016-001 (SPEC-004 FR-016):** permitir recorrido ficticio sin proveedor externo.
- **FR-016-002 (SPEC-004 FR-017):** conservar el analizador heredado ejecutable.
- **FR-016-003 (SPEC-004 NFR-003–NFR-008):** pruebas sin red, instalación reproducible y regresión.
- **FR-016-004 (SPEC-005):** aplicar migraciones Alembic antes de operar la importación histórica.

## Implementación y evidencia

`README.md`, `requirements.txt`, `alembic.ini`, `migrations/`, `scripts/seed.py`, Docker, workflow CI y verificaciones de SPEC-004/005.

## Brechas conocidas

Una base previa sin `alembic_version` debe respaldarse y recrearse; Docker no fue construido en el host local original y PostgreSQL no está validado.

## Historial

- 2026-09-10: creada como vista transversal de SPEC-004/005, sin cambio de comportamiento.
