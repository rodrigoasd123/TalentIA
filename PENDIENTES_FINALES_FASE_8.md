# Pendientes finales de TalentIA

Fecha: 2026-09-13

## Estado entregado

- Las fases tecnicas 1 a 8 de `SPEC-030` estan implementadas y verificadas.
- Rama: `codex/rubrica-greenfield-talentia`.
- Base funcional revisada: `fde1f74ce5cab3cfd3a6338ccc998ecb1aa7a672`.
- Pull request preparado: <https://github.com/rodrigoasd123/TalentIA/pull/2>.
- Verificacion final: 81 pruebas greenfield y 391 pruebas totales aprobadas.
- Ruff, formato, mypy, instalacion limpia, migraciones, backup, restauracion y escaner aprobados.
- Los fallos de CI detectados en el PR 2 (orden de imports y aislamiento de la base de migraciones)
  fueron corregidos y reproducidos localmente; GitHub Actions debe confirmar el commit de cierre.
- No se realizo merge ni modificacion directa de `main`.

## Pendientes externos

### 1. Decisiones de negocio de TCS

TCS debe aprobar valores concretos para `BIZ-001` a `BIZ-010`. Actualmente estan explicitamente
fuera del alcance del piloto y el sistema conserva el comportamiento seguro: fallo cerrado o
revision humana.

No implementar ninguna de estas reglas sin seguir este orden:

1. Registrar la decision expresa y su responsable.
2. Refinar `spec.md`, criterios de aceptacion y riesgos afectados.
3. Aprobar el plan de cambio.
4. Implementar pruebas y codigo en un commit separado.
5. Repetir UAT y puertas de calidad.

La matriz completa se encuentra en
`specs/030-reconstruccion-greenfield-talentia/decisiones-negocio-fase-8.md`.

### 2. Aceptacion humana de RR. HH.

Una persona designada por RR. HH. de TCS debe ejecutar o revisar los escenarios documentados en
`specs/030-reconstruccion-greenfield-talentia/uat-fase-8.md` y registrar:

- nombre y rol de la persona responsable;
- fecha y ambiente de validacion;
- resultado de cada escenario;
- incidencias y severidad;
- conformidad o rechazo formal.

La UAT tecnica equivalente ya aprobo 23 pruebas con datos sinteticos. Esa evidencia no sustituye la
firma humana.

### 3. Revision y promocion

1. Revisar el pull request numero 2.
2. Confirmar que los checks remotos de GitHub finalizan correctamente.
3. Resolver cualquier observacion mediante commits nuevos en la misma rama.
4. Obtener autorizacion expresa del propietario para fusionar.
5. Hacer merge a `main` solo despues de la aceptacion funcional y la autorizacion.

## Restricciones vigentes

- No usar CV reales, PII ni secretos en evidencias o Git.
- No inventar decisiones `BIZ-001..010`.
- No presentar sugerencias de IA como decisiones finales.
- Mantener SQLite como alcance del piloto local.
- No fusionar a `main` automaticamente.
