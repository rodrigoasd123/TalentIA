# SPEC-018 — Base general de candidatos y seguimiento

## Objetivo

Gestionar una ficha general por persona, separada del estado de sus postulaciones,
y generar un reporte verificable de candidatos de fuente Adecco, entrevistados o
descartados.

## Requisitos funcionales

- El alta y la edición manejan cliente, status general, fecha, reclutador, fuente,
  Q, fecha de nacimiento, edad, DNI, BGC, conocimientos técnicos, deuda Equifax,
  expectativa salarial, solicitado, CTC del rol, variación CTC, disponibilidad y
  observaciones.
- Los únicos status generales son: Apto, No apto, Backup, En proceso, No contesta,
  Pendiente contacto y Pendiente envío.
- La edad se calcula desde la fecha de nacimiento. Si esta no existe, puede
  conservarse una edad reportada.
- El reporte incluye las categorías Adecco, entrevistado y descartado; una persona
  puede pertenecer a más de una.
- El reporte puede descargarse como CSV.

## Seguridad y gobierno

- DNI, BGC, deuda, salarios, fecha de nacimiento y observaciones respetan el permiso
  `candidate:pii:read`.
- El reporte no contiene DNI, contacto, BGC, Equifax, salarios ni observaciones.
- El CSV neutraliza fórmulas de hoja de cálculo.
- La generación es determinística y no delega decisiones ni clasificación a un LLM.

