# Aceptación — SPEC-013

## AC-013-001 — Cadena íntegra

Cada evento enlaza con el anterior y una cadena intacta verifica correctamente.

**Evidencia:** pruebas de génesis, enlace y verificación en `test_persistence_and_audit.py`.

## AC-013-002 — Manipulación detectable

Modificar o eliminar un evento rompe la verificación de integridad.

**Evidencia:** pruebas adversariales de modificación y eliminación.

## AC-013-003 — Traza aislada

La historia de una postulación se devuelve cronológicamente sin mezclar eventos de otra postulación e incluye procedencia de IA.

**Evidencia:** pruebas de decision trail y procedencia.

## AC-013-004 — Línea de tiempo 360

Tras crear postulación, documento y evaluación, la traza del candidato contiene los cuatro tipos
de recurso, conserva correlación y permite filtrar una acción sin mezclar otras personas.
