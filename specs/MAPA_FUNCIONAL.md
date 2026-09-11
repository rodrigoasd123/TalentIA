# Mapa funcional de especificaciones — TalentIA

Este mapa distribuye la línea base consolidada por capacidad sin modificar el alcance ni la evidencia histórica de `SPEC-004` y `SPEC-005`.

| Dominio | Spec propietaria | Origen histórico |
|---|---|---|
| Identidad, sesión y RBAC | SPEC-006 | SPEC-004 SEC-002, SEC-003, SEC-009 |
| Vacantes, criterios y sourcing manual | SPEC-007 | SPEC-004 FR-001, FR-002, FR-013 |
| Candidatos, documentos y postulaciones | SPEC-008 | SPEC-004 FR-003–FR-005 |
| Evaluación IA gobernada | SPEC-009 | SPEC-004 FR-006–FR-008 |
| Revisión humana y pipeline | SPEC-010 | SPEC-004 FR-009, FR-011 |
| Candidate 360, ranking y comparación | SPEC-011 | SPEC-004 FR-010, FR-012 |
| Comunicaciones gobernadas | SPEC-012 | SPEC-004 FR-014 |
| Auditoría y trazabilidad | SPEC-013 | SPEC-004 FR-015 |
| Configuración e integraciones | SPEC-014 | SPEC-004 FR-016 y SEC-009 |
| Dashboard y reportes operativos | SPEC-015 | Línea base implementada en SPEC-004 |
| Operación, persistencia y rollback | SPEC-016 | SPEC-004 NFR-003–NFR-008, FR-017 |
| Importación histórica CSV/XLSX | SPEC-005 | Spec funcional independiente |
| Rediseño integral del frontend | SPEC-017 | Cambio nuevo pendiente de aprobación |
| Base general de candidatos y seguimiento | SPEC-018 | Ampliación aprobada por el usuario |
| Consolidación de identidad, SQLite y análisis documental | SPEC-019 | Consolidación aprobada por el usuario |

## Reglas de mantenimiento

- `SPEC-004` permanece archivada e inmutable como evidencia de consolidación.
- `SPEC-005` conserva la propiedad completa de la importación histórica.
- `SPEC-006` a `SPEC-016` son vistas derivadas del comportamiento ya verificado; no autorizan cambios nuevos.
- Las vistas derivadas contienen `spec.md`, `acceptance.md`, `plan.md`, `tasks.md` y `verification.md`.
- Sus planes y tareas reconstruyen retrospectivamente la trazabilidad de SPEC-004/005; no representan una segunda implementación ni cambios de comportamiento.
- Todo cambio futuro debe refinar la spec propietaria y añadir requisitos/criterios nuevos sin renumerar los heredados.
- `SPEC-017` permanece en borrador hasta aprobación explícita; no autoriza modificar el frontend.
