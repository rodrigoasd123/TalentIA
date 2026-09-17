---
id: SPEC-037
titulo: Flujo jerárquico por cuentas, convocatorias y selección
estado: VERIFICADO
responsable_producto: Usuario
creado: 2026-09-16
actualizado: 2026-09-17
---

# SPEC-037 — Flujo jerárquico por cuentas, convocatorias y selección

## Problema y resultado esperado

TalentIA presenta perfiles, postulaciones, candidatos y estados como módulos separados, por lo que
el flujo de trabajo no refleja con claridad cómo opera el equipo de reclutamiento. Las reclutadoras
trabajan para cuentas concretas, comparten candidatos y antecedentes solo con compañeras de la
misma cuenta y necesitan distinguir un perfil reutilizable de una convocatoria con cupos y fechas.

TalentIA debe organizar la operación con la jerarquía observable:

```text
Cuenta → Perfil → Convocatoria → Reclutadores asignados → Candidaturas
```

El resultado esperado es un flujo guiado en el que un gestor de contratación asigna reclutadores,
se abre una convocatoria para cubrir un número definido de vacantes, las reclutadoras mantienen
el estado de cada candidatura en una única base y una persona autorizada elige finalistas, conserva
un pool de backup y cierra la convocatoria cuando se cubren sus cupos.

## Usuarios y necesidades

- **Gestor de contratación / Hiring Manager:** administrar las cuentas bajo su alcance, asignar
  reclutadores, crear perfiles y convocatorias, elegir finalistas y cerrar convocatorias.
- **Reclutador:** trabajar únicamente con cuentas asignadas, conocer el contacto previo realizado
  por compañeras de esa cuenta y actualizar el avance de las candidaturas.
- **Administrador:** configurar cuentas, usuarios, roles y alcances sin participar obligatoriamente
  en las decisiones de selección.
- **Auditor:** reconstruir asignaciones, cambios de estado, selección de finalistas, backups y cierre.

## Alcance

### Incluido

1. Usar `Cliente` como la cuenta operativa (por ejemplo BCP, BBVA o Scotia).
2. Mantener perfiles versionados y reutilizables dentro de una cuenta.
3. Incorporar una entidad `Convocatoria` separada del perfil, con código, versión de perfil, número
   de vacantes, fechas, estado y motivo de cierre o cancelación.
4. Gestionar la asignación de reclutadores a cuentas y definir responsables de cada convocatoria.
5. Vincular cada candidatura a una convocatoria, no solo a una versión de perfil.
6. Mostrar un espacio de trabajo guiado por cuenta y convocatoria, con resumen de cupos, equipo,
   candidatos por estado, alertas de contacto previo y siguientes acciones válidas.
7. Permitir decisiones humanas de aptitud, selección final, backup, oferta, contratación, descarte
   y retiro mediante una máquina de estados auditada.
8. Mantener los cambios sincronizados en SQLite como única fuente operativa; Excel queda como
   importación o exportación opcional.
9. Migrar las postulaciones históricas a convocatorias de compatibilidad sin perder evidencia.

### Fuera de alcance

- Seleccionar, rechazar, ofertar o contratar automáticamente mediante IA.
- Compartir PII, historial de contacto o coincidencias entre cuentas no autorizadas.
- Contactar candidatos, publicar ofertas o coordinar entrevistas automáticamente.
- Sustituir los perfiles versionados por texto libre dentro de cada convocatoria.
- Microservicios, colas externas o infraestructura adicional para el piloto local.

## Requisitos funcionales

- **FR-037-001:** la navegación operativa debe comenzar por una cuenta y mostrar, en orden, sus
  perfiles, convocatorias, responsables y candidaturas, conservando el contexto seleccionado.
- **FR-037-002:** un perfil debe pertenecer a una cuenta, admitir versiones inmutables publicadas y
  poder ser reutilizado por más de una convocatoria.
- **FR-037-003:** una convocatoria debe referenciar una versión publicada del perfil y registrar al
  menos código, cantidad de vacantes, fecha de apertura, fecha objetivo y estado.
- **FR-037-004:** una candidatura debe vincular una persona candidata con una convocatoria y debe
  ser única para la combinación cuenta, convocatoria y persona.
- **FR-037-005:** el estado de selección debe pertenecer a la candidatura; el estado general de la
  persona no puede sobrescribir el resultado independiente de otras convocatorias.
- **FR-037-006:** una reclutadora debe poder consultar el contacto y los procesos previos de una
  persona únicamente dentro de las cuentas que tiene asignadas.
- **FR-037-007:** al registrar o cargar un CV, TalentIA debe ejecutar deduplicación determinística
  dentro de la cuenta y advertir qué reclutador contactó a la persona, cuándo y en qué convocatoria.
- **FR-037-008:** el gestor de contratación debe poder asignar y retirar reclutadores de las cuentas
  bajo su alcance y designar responsables de convocatoria sin conceder acceso a otras cuentas.
- **FR-037-009:** las transiciones de candidatura deben limitarse a las acciones válidas para el
  estado actual, el rol y la cuenta, y deben exigir motivo cuando impliquen descarte o reversión.
- **FR-037-010:** marcar una candidatura como apta no debe convertirla automáticamente en finalista;
  la selección final debe ser una acción humana explícita y limitada por los cupos de la convocatoria.
- **FR-037-011:** al cubrir o cerrar una convocatoria, TalentIA debe conservar como backup a las
  candidaturas aptas no elegidas según la regla de negocio aprobada y registrar las demás salidas.
- **FR-037-012:** las vistas de cuenta y convocatoria deben mostrar cupos totales, cubiertos y
  pendientes, equipo asignado y cantidades por estado sin contar a una persona dos veces.
- **FR-037-013:** cada alta, asignación, transición, selección, reversión y cierre debe actualizarse
  transaccionalmente en la base central y reflejarse al recargar cualquier módulo relacionado.
- **FR-037-014:** las postulaciones históricas existentes deben asociarse a una convocatoria de
  compatibilidad identificable, sin alterar su estado, evaluación, documento ni trazabilidad.

## Requisitos no funcionales

- **NFR-037-001:** el flujo, la deduplicación, los cupos y las transiciones deben ser determinísticos
  y no depender de un LLM.
- **NFR-037-002:** listados y contadores deben paginarse y responder sobre índices de cuenta,
  convocatoria, estado, candidato y reclutador.
- **NFR-037-003:** las escrituras deben usar transacciones y control optimista para no perder cambios
  concurrentes de dos reclutadoras.
- **NFR-037-004:** la interfaz debe ocultar acciones no válidas, explicar por qué una acción está
  bloqueada y mantener filtros y contexto tras errores recuperables.
- **NFR-037-005:** la migración debe ser reversible, preservar datos históricos y permitir restaurar
  un respaldo anterior al cambio.
- **NFR-037-006:** el piloto debe seguir ejecutándose con Python, FastAPI, Jinja2/HTMX, SQLAlchemy y
  SQLite WAL, sin Node.js ni infraestructura adicional en producción.

## Seguridad y privacidad

- **SEC-037-001:** todo acceso debe aplicar alcance de cuenta en backend; los filtros de interfaz no
  sustituyen la autorización ni la protección contra IDOR.
- **SEC-037-002:** un reclutador no debe recibir nombres, PII, historial, conteos de coincidencias ni
  confirmación de existencia de personas pertenecientes exclusivamente a otra cuenta.
- **SEC-037-003:** el gestor de contratación solo debe administrar asignaciones de cuentas dentro de
  su propio alcance; la administración global continúa reservada al rol administrador.
- **SEC-037-004:** los cambios de asignación deben invalidar sesiones o alcances obsoletos conforme a
  SPEC-006 y quedar auditados con actor, cuenta, valor anterior y valor nuevo.
- **SEC-037-005:** decisiones de aptitud, finalista, backup, oferta, contratación y descarte deben
  registrar actor, fecha, motivo y transición anterior/nueva, sin delegarse a agentes de IA.
- **SEC-037-006:** exportaciones deben respetar el alcance de cuenta, minimizar PII y neutralizar
  fórmulas para hojas de cálculo.

## Reglas y fuentes de verdad

- `clients` es la fuente de verdad de las cuentas.
- `job_profiles` y `job_profile_versions` definen el perfil reusable y sus criterios aprobados.
- La nueva entidad `recruitment_campaigns` define cupos, vigencia y ciclo de vida de convocatorias.
- Una tabla de asignación cuenta–usuario controla visibilidad; una asignación adicional de
  convocatoria define responsabilidad operativa sin ampliar el alcance de cuenta.
- `applications` representa la candidatura y contiene su estado por convocatoria.
- La máquina de estados del dominio es la única fuente de transiciones válidas.
- `audit_events` conserva la trazabilidad; la interfaz no escribe estados directamente en SQLite.
- SPEC-006, SPEC-008, SPEC-010, SPEC-020, SPEC-022 y SPEC-026 continúan vigentes salvo los cambios
  explícitos de jerarquía y alcance de esta especificación.

## Supuestos confirmados

- “Cuenta” corresponde al concepto existente `Cliente`.
- El flujo se ejecutará en la aplicación TalentIA y SQLite será la fuente de verdad del piloto.
- Las reclutadoras colaboran y comparten antecedentes dentro de una misma cuenta.
- Las personas de cuentas no autorizadas no deben ser visibles entre sí.
- La decisión de aptitud, selección, backup y descarte es humana.
- Cada persona tendrá un expediente operativo independiente por cuenta durante el piloto; no habrá
  actualizaciones cruzadas de PII ni una identidad global visible para reclutadores.
- La asignación de usuario a cuenta concede visibilidad y permisos dentro de esa cuenta; la
  asignación a una convocatoria identifica responsables operativos y no amplía el alcance.
- La máquina de estados aprobada es `nueva → contactada → cv_recibido → en_evaluacion →
  revision_humana → apta → finalista → entrevista → oferta → contratada`, con salidas
  `no_apta`, `rechazada`, `backup` y `retirada`.
- Al cubrir los cupos, el gestor de contratación debe revisar una vista previa y confirmar el
  cierre; en esa misma operación las candidaturas aptas no elegidas pasan a `backup`.
- Un perfil es una plantilla reusable y versionada; cada convocatoria congela una versión y define
  sus propios cupos, fechas y responsables.

## Riesgos y fallos esperados

- Una asignación retirada mientras existe una sesión activa puede dejar permisos obsoletos si no se
  incrementa la versión de sesión.
- La migración incorrecta de postulaciones históricas puede perder el contexto del perfil evaluado.
- Contadores calculados desde estados globales de candidato producirían cifras inconsistentes; deben
  derivarse siempre de candidaturas por convocatoria.
- El cierre concurrente puede sobrepasar los cupos si no se valida dentro de la transacción.
- Una deduplicación global visible revelaría la existencia de una persona en otra cuenta.

## Preguntas abiertas

Ninguna bloqueante. Las cinco decisiones de alcance fueron aprobadas por la persona responsable de
producto el 2026-09-16 y se incorporaron a “Supuestos confirmados”.

## Historial de decisiones

| Fecha | Decisión | Responsable | Motivo |
|---|---|---|---|
| 2026-09-16 | Crear una jerarquía explícita por cuenta, perfil y convocatoria | Usuario | Hacer el flujo entendible y alineado con la operación de RR. HH. |
| 2026-09-16 | Mantener decisiones de selección bajo control humano | Usuario | Reclutadores y hiring managers editan y deciden estados |
| 2026-09-16 | Mantener la especificación en BORRADOR | Codex | Existen cinco decisiones de negocio bloqueantes |
| 2026-09-16 | Aprobar las cinco decisiones de alcance y los criterios AC-037-001 a AC-037-010 | Usuario | Autorizar expediente por cuenta, asignaciones, estados, cierre confirmado y perfiles reutilizables |
| 2026-09-16 | Cambiar el estado de la especificación a LISTO | Codex | No quedan decisiones bloqueantes |
| 2026-09-17 | Verificar la implementación corregida | Codex | AC-037-001 a AC-037-010 aprobados, 143 pruebas verdes y sin hallazgos mayores abiertos |
