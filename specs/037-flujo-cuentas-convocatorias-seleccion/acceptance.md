# Criterios de aceptación — SPEC-037

**Característica:** flujo jerárquico por cuentas, convocatorias y selección.

## AC-037-001 — Navegación guiada por jerarquía

**Cubre:** FR-037-001, FR-037-002, FR-037-003, NFR-037-004

```gherkin
Escenario: abrir el espacio de trabajo de una convocatoria
  Dado que el usuario tiene acceso a la cuenta BCP
  Y existe un perfil publicado y una convocatoria abierta de esa cuenta
  Cuando selecciona Cuenta BCP, el perfil y la convocatoria
  Entonces TalentIA conserva esa ruta como contexto visible
  Y muestra cupos, responsables, estados y acciones válidas de la convocatoria
```

**Evidencia requerida:** prueba web y verificación visual reproducible.

## AC-037-002 — Perfil reusable y convocatoria independiente

**Cubre:** FR-037-002, FR-037-003

```gherkin
Escenario: abrir dos convocatorias desde el mismo perfil
  Dado un perfil Full Stack publicado dentro de una cuenta
  Cuando el gestor crea dos convocatorias con cupos y fechas diferentes
  Entonces ambas referencian la versión aprobada del perfil
  Y cada convocatoria conserva de manera independiente sus cupos, fechas, responsables y estado
```

**Evidencia requerida:** prueba de dominio, repositorio y API.

## AC-037-003 — Colaboración dentro de una cuenta

**Cubre:** FR-037-006, FR-037-007, SEC-037-001

```gherkin
Escenario: advertir contacto previo realizado por una compañera
  Dado que Ana y Beatriz están asignadas a la cuenta BCP
  Y Ana registró previamente a una persona en una convocatoria de BCP
  Cuando Beatriz intenta registrar la misma identidad en BCP
  Entonces TalentIA muestra una advertencia determinística con el proceso, fecha y reclutador previo
  Y no crea silenciosamente una identidad duplicada
```

**Evidencia requerida:** prueba de integración con documento o correo exacto.

## AC-037-004 — Aislamiento entre cuentas

**Cubre:** FR-037-006, SEC-037-001, SEC-037-002

```gherkin
Escenario: impedir que una reclutadora descubra datos de otra cuenta
  Dado que Ana solo está asignada a BCP
  Y existe una persona registrada exclusivamente en BBVA
  Cuando Ana busca, filtra, consulta una URL directa o ejecuta la deduplicación
  Entonces TalentIA no devuelve PII, historial ni confirmación de existencia de esa persona
  Y registra el intento IDOR según la política de seguridad
```

**Evidencia requerida:** pruebas API/web de RBAC, IDOR y ausencia de filtración lateral.

## AC-037-005 — Asignación gobernada de reclutadores

**Cubre:** FR-037-008, SEC-037-003, SEC-037-004

```gherkin
Escenario: asignar una reclutadora a una cuenta autorizada
  Dado que el hiring manager administra la cuenta BCP
  Cuando asigna una reclutadora activa a BCP
  Entonces la reclutadora obtiene el alcance de BCP sin recibir acceso a otras cuentas
  Y TalentIA audita actor, cuenta, usuario y cambio de alcance
```

**Evidencia requerida:** prueba de servicio, invalidación de sesión y auditoría.

## AC-037-006 — Decisión humana de aptitud y selección

**Cubre:** FR-037-009, FR-037-010, SEC-037-005

```gherkin
Escenario: elegir finalistas sin decisión automática
  Dado que una convocatoria tiene dos vacantes y cuatro candidaturas aptas
  Cuando el gestor selecciona explícitamente dos candidaturas como finalistas
  Entonces TalentIA acepta como máximo dos finalistas activos
  Y conserva las otras candidaturas aptas sin seleccionarlas automáticamente
  Y registra la decisión humana y su justificación
```

**Evidencia requerida:** pruebas de dominio, concurrencia, API y auditoría.

## AC-037-007 — Cierre y pool de backup

**Cubre:** FR-037-011, FR-037-012

```gherkin
Escenario: cerrar una convocatoria con vacantes cubiertas
  Dado que las contrataciones confirmadas cubren todos los cupos
  Y existen candidaturas aptas no elegidas
  Cuando el gestor revisa la vista previa y confirma el cierre
  Entonces la convocatoria queda cerrada por vacantes cubiertas
  Y las candidaturas aptas no elegidas quedan disponibles como backup según la regla aprobada
  Y ninguna candidatura nueva puede agregarse sin reabrir la convocatoria con permiso
```

**Evidencia requerida:** prueba transaccional y verificación web.

## AC-037-008 — Estado centralizado y concurrente

**Cubre:** FR-037-005, FR-037-009, FR-037-013, NFR-037-003

```gherkin
Escenario: evitar que dos reclutadoras sobrescriban el mismo estado
  Dado que dos reclutadoras abren la misma candidatura de una cuenta compartida
  Cuando ambas intentan guardar transiciones desde la misma versión
  Entonces solo la primera transición válida se confirma
  Y la segunda recibe un conflicto con el estado actualizado sin perder su comentario
```

**Evidencia requerida:** prueba de concurrencia y bloqueo optimista.

## AC-037-009 — Migración de postulaciones históricas

**Cubre:** FR-037-014, NFR-037-005

```gherkin
Escenario: asociar una postulación histórica sin alterar su evidencia
  Dado que existe una postulación anterior vinculada directamente a una versión de perfil
  Cuando se ejecuta la migración
  Entonces la postulación queda asociada a una convocatoria de compatibilidad de la misma cuenta
  Y conserva candidato, estado, fuente, CV, evaluación, revisión y marcas de tiempo
  Y el downgrade restaura el esquema anterior sin pérdida de registros
```

**Evidencia requerida:** prueba de migración upgrade/downgrade y comparación de integridad.

## AC-037-010 — Funcionamiento sin IA

**Cubre:** NFR-037-001, NFR-037-006

```gherkin
Escenario: operar el flujo con proveedores de IA deshabilitados
  Dado que Gemini y OpenAI no están configurados
  Cuando se crean cuentas, perfiles, convocatorias, asignaciones y transiciones
  Entonces todo el flujo operativo funciona de forma determinística
  Y las decisiones humanas y la auditoría permanecen disponibles
```

**Evidencia requerida:** prueba de integración sin red ni claves de proveedor.
