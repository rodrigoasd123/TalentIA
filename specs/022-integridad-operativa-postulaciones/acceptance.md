# Criterios de aceptación — SPEC-022

**Característica:** Integridad operativa de postulaciones.

## AC-001 — Identificación de CV faltante
**Cubre:** FR-001, FR-003
```gherkin
Escenario: postulación sin documento
  Dado que una postulación no tiene resume_id válido
  Cuando RR. HH. consulta los listados
  Entonces se muestra como "CV pendiente" y puede filtrarse
```
**Evidencia requerida:** prueba de API y vista manual.

## AC-002 — Asociación segura de CV
**Cubre:** FR-002, NFR-001, SEC-001, SEC-002, SEC-003
```gherkin
Escenario: asociar un CV a una postulación histórica
  Dado que la persona tiene consentimiento vigente
  Cuando un usuario autorizado carga un PDF o DOCX válido
  Entonces el documento queda asociado y la acción auditada sin duplicar contenido idéntico
```
**Evidencia requerida:** prueba de endpoint.

## AC-003 — Cola humana consistente
**Cubre:** FR-004, FR-005, NFR-001
```gherkin
Escenario: solicitar validación de un requisito no acreditado
  Dado que existe una evaluación y no hay un caso abierto
  Cuando RR. HH. solicita revisión
  Entonces se crea un caso abierto y una segunda solicitud reutiliza el mismo caso
```
**Evidencia requerida:** prueba de servicio/API.

## AC-004 — Filtros operativos
**Cubre:** FR-003, NFR-002
```gherkin
Escenario: reducir candidatos visibles
  Dado que existen postulaciones de varias vacantes y estados
  Cuando el usuario combina filtros
  Entonces tablero, tabla y selector muestran solo las coincidencias
```
**Evidencia requerida:** prueba focal de funciones y verificación Streamlit.

## AC-005 — Diagnóstico de auditoría
**Cubre:** FR-006
```gherkin
Escenario: cadena de auditoría inconsistente
  Dado que la verificación detecta un evento roto
  Cuando se abre Auditoría
  Entonces se explica el impacto y se indica investigar el evento sin repararlo automáticamente
```
**Evidencia requerida:** prueba de payload o verificación manual.
