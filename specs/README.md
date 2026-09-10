# Especificaciones de TalentIA

Consulta primero el [mapa funcional](./MAPA_FUNCIONAL.md), que define la spec propietaria de cada capacidad y evita volver a concentrar cambios distintos en una sola especificación.

## Funcionalidades ATS

- [`SPEC-005`](./005-importacion-historica-csv-xlsx/spec.md): Importación histórica gobernada CSV/XLSX (verificada).
- [`SPEC-006`](./006-identidad-acceso-rbac/spec.md): Identidad, sesión y RBAC (verificada por la evidencia de SPEC-004).
- [`SPEC-007`](./007-vacantes-criterios-sourcing/spec.md): Vacantes, criterios y sourcing manual (verificada por la evidencia de SPEC-004).
- [`SPEC-008`](./008-candidatos-documentos-postulaciones/spec.md): Candidatos, documentos y postulaciones (verificada por la evidencia de SPEC-004).
- [`SPEC-009`](./009-evaluacion-ia-gobernada/spec.md): Evaluación asistida por IA gobernada (verificada por la evidencia de SPEC-004).
- [`SPEC-010`](./010-revision-humana-pipeline/spec.md): Revisión humana y pipeline (verificada por la evidencia de SPEC-004).
- [`SPEC-011`](./011-candidate360-ranking/spec.md): Candidate 360, ranking y comparación (verificada por la evidencia de SPEC-004).
- [`SPEC-012`](./012-comunicaciones-gobernadas/spec.md): Comunicaciones gobernadas (verificada por la evidencia de SPEC-004).
- [`SPEC-013`](./013-auditoria-trazabilidad/spec.md): Auditoría y trazabilidad (verificada por la evidencia de SPEC-004).
- [`SPEC-014`](./014-configuracion-integraciones/spec.md): Configuración e integraciones (verificada por la evidencia de SPEC-004).
- [`SPEC-015`](./015-dashboard-reportes/spec.md): Dashboard y reportes operativos (verificada por la evidencia de SPEC-004).
- [`SPEC-016`](./016-operacion-plataforma-rollback/spec.md): Operación, persistencia y rollback (verificada por SPEC-004/005).

## Cambio pendiente de aprobación

- [`SPEC-017`](./017-redisenio-frontend-talentia/spec.md): Rediseño integral del frontend TalentIA (**borrador; no autoriza implementación**).

## Funcionalidades heredadas del analizador documental

- [`SPEC-000`](./000-hr-cv-screening/spec.md): Asistente de revisión de CV para RR. HH. (verificada).
- [`SPEC-001`](./001-filtro-lenguaje-ofensivo/spec.md): Filtro de lenguaje ofensivo para el agente (borrador).
- [`SPEC-002`](./002-interaccion-conversacional-basica/spec.md): Interacción conversacional básica (en verificación).
- [`SPEC-003`](./003-cache-vectorial-respuestas/spec.md): Caché vectorial y respuestas reutilizables (en verificación).

## Consolidación histórica

- [`SPEC-004`](./archive/004-consolidacion-ats-piloto/spec.md): Consolidación inicial como TalentIA ATS piloto gobernado (verificada y archivada).

## Contexto y gobierno

- [Contexto del proyecto](../docs/sdd/proyecto.md)
- [Constitución SDD](../docs/sdd/constitucion.md)
- [Archivo de especificaciones](./archive/README.md)