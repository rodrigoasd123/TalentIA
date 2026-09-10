---
id: SPEC-007
titulo: Vacantes, criterios y sourcing manual
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-007 — Vacantes, criterios y sourcing manual

## Propósito

Administrar vacantes y criterios versionados que constituyen la fuente de verdad de la evaluación, manteniendo aprobación humana y sourcing externo manual.

## Alcance vigente

- Crear, listar y editar vacantes.
- Requisitos obligatorios/deseables, pesos, umbrales y plazo.
- Aprobación humana antes de abrir o evaluar.
- Nueva versión y retorno a borrador al cambiar criterios.
- Consulta Boolean para ejecución manual en LinkedIn Recruiter.

## Fuera de alcance

Publicación automática, scraping, RSC, bots de navegador, InMail y creación de vacantes desde importaciones.

## Requisitos heredados

- **FR-007-001 (SPEC-004 FR-001):** crear y editar una vacante en borrador con criterios y pesos válidos.
- **FR-007-002 (SPEC-004 FR-002):** exigir aprobación humana antes de abrir o evaluar.
- **FR-007-003 (SPEC-004 FR-013):** producir términos y consulta Boolean sin operar LinkedIn.
- **FR-007-004:** editar criterios invalida la aprobación anterior y crea una versión trazable.

## Implementación y evidencia

`Job` y reglas en `app/domain/`, rutas de jobs/sourcing en `operations.py`, página `2_Vacantes.py` y `tests/ats/test_intake_api.py`.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
