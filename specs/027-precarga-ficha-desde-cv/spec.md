# SPEC-027 — Precarga de ficha desde CV

- **Estado:** VERIFIED
- **Fuente:** Documento TCS, agente lector.

## Problema y alcance

La extracción estructurada hoy alimenta la evaluación pero no reduce el registro manual. TalentIA debe proponer campos del CV para que RR. HH. los revise y confirme.

## Requisitos

- **FR-027-001:** tras procesar un CV se generan sugerencias estructuradas de experiencia, tecnologías, formación, contacto y disponibilidad con procedencia/confianza.
- **FR-027-002:** ninguna sugerencia sobrescribe la ficha sin confirmación humana por campo.
- **FR-027-003:** RR. HH. puede aceptar, corregir o descartar sugerencias conservando el formulario.
- **FR-027-004:** lo no presente en el CV queda pendiente para la llamada, nunca inventado.
- **NFR-027-001:** extracción fallida no bloquea la postulación y deriva a carga manual/revisión.
- **SEC-027-001:** atributos sensibles no se precargan ni puntúan; el acceso requiere permisos de candidato.
- **SEC-027-002:** aceptación/corrección queda auditada con fuente CV y versión.

## Fuera de alcance

Autocompletar DNI, nacimiento, deudas, antecedentes o inferir datos ausentes. Sin preguntas bloqueantes.
