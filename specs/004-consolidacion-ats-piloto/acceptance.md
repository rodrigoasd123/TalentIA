# Criterios de aceptación — SPEC-004

**Característica:** consolidación de PostulaIA como ATS piloto gobernado.

## AC-001 — Alta completa de una candidatura

**Cubre:** FR-001, FR-002, FR-003, FR-004, FR-005; SEC-004

```gherkin
Escenario: recruiter registra una candidatura desde la interfaz
  Dado que existe una vacante abierta con criterios aprobados
  Y el recruiter registra consentimiento vigente del candidato
  Cuando carga un PDF o DOCX válido
  Entonces el sistema crea candidato, versión de CV y candidatura en una sola operación
  Y muestra el nuevo registro en el pipeline
```

**Evidencia requerida:** prueba de API transaccional y recorrido manual de interfaz.

## AC-002 — OCR local reutilizado

**Cubre:** FR-004; NFR-008; SEC-004

```gherkin
Escenario: CV escaneado sin capa de texto
  Dado un PDF válido cuya extracción normal es insuficiente
  Cuando el recruiter solicita el procesamiento con OCR
  Entonces el sistema utiliza el adaptador OCR local de PostulaIA
  Y conserva texto y referencias de página para verificar evidencia
```

**Evidencia requerida:** prueba con PDF ficticio escaneado y evidencia por página.

## AC-003 — Evaluación gobernada y reproducible

**Cubre:** FR-006, FR-007, FR-008; SEC-005, SEC-006, SEC-007

```gherkin
Escenario: evaluación de una candidatura elegible
  Dado un CV procesable y criterios versionados cuyos pesos suman 100
  Cuando se ejecuta la evaluación
  Entonces los filtros obligatorios se calculan en código
  Y cada dimensión generada contiene evidencia verificable
  Y el backend calcula el score total sin aceptar un total del modelo
```

**Evidencia requerida:** pruebas de filtros, esquema, evidencia y cálculo determinístico.

## AC-004 — Prompt injection no altera el resultado

**Cubre:** FR-006, FR-007; SEC-005, SEC-007, SEC-008

```gherkin
Escenario: CV contiene instrucciones dirigidas al agente
  Dado un CV ficticio con prompt injection
  Cuando el sistema lo evalúa
  Entonces detecta y registra el incidente
  Y la carga maliciosa no cambia el score respecto del contenido profesional equivalente
  Y ninguna acción de correo, transición o contratación se ejecuta
  Y el caso deriva a revisión humana
```

**Evidencia requerida:** prueba adversarial comparativa sin red.

## AC-005 — PII no llega al proveedor

**Cubre:** FR-006; SEC-003, SEC-006

```gherkin
Escenario: evaluación usa un adaptador LLM externo simulado
  Dado un CV que contiene nombre, correo, teléfono, dirección e identificadores
  Cuando se intercepta el payload real entregado al adaptador
  Entonces ninguna PII definida aparece en ese payload
  Y la información profesional necesaria permanece disponible
```

**Evidencia requerida:** prueba de frontera sobre el payload efectivo.

## AC-006 — Supervisión humana y transiciones

**Cubre:** FR-009, FR-011; SEC-002, SEC-008

```gherkin
Escenario: revisor resuelve una alerta
  Dado un elemento abierto en la cola de revisión
  Cuando un usuario autorizado lo reclama y decide con justificación
  Entonces el backend valida la transición
  Y conserva decisión propuesta, decisión humana, actor y motivo
  Y ningún usuario no autorizado puede ejecutar la misma acción
```

**Evidencia requerida:** pruebas positivas y negativas de RBAC, máquina de estados y auditoría.

## AC-007 — Candidate 360 y acceso auditado

**Cubre:** FR-010, FR-015; SEC-002, SEC-003

```gherkin
Escenario: usuario autorizado abre Candidate 360
  Dado una candidatura con evaluación y revisión
  Cuando el usuario consulta la vista consolidada
  Entonces visualiza CV, estado, score, evidencia e historial permitido por su rol
  Y el acceso a datos personales queda auditado con propósito
```

**Evidencia requerida:** prueba de contrato de API y permisos por rol.

## AC-008 — Ranking contextual y explicable

**Cubre:** FR-012

```gherkin
Escenario: comparación dentro de una vacante
  Dado dos candidaturas evaluadas para la misma vacante
  Cuando el recruiter solicita compararlas
  Entonces el sistema explica diferencias por dimensión y evidencia
  Y rechaza comparaciones entre vacantes distintas
```

**Evidencia requerida:** prueba funcional positiva y negativa.

## AC-009 — LinkedIn permanece bajo operación humana

**Cubre:** FR-013; SEC-007, SEC-008

```gherkin
Escenario: preparación de una búsqueda
  Dado un pedido de contratación validado
  Cuando el recruiter solicita ayuda para buscar perfiles
  Entonces el sistema propone keywords, sinónimos, filtros y una consulta Boolean
  Y no abre, navega, extrae ni ejecuta acciones en LinkedIn
```

**Evidencia requerida:** prueba de salida estructurada e inventario de dependencias sin automatización web.

## AC-010 — Comunicaciones sin efectos

**Cubre:** FR-014; SEC-008, SEC-009

```gherkin
Escenario: preparación de mensaje en el piloto
  Dado una plantilla aprobada y DRY_RUN activo
  Cuando el recruiter solicita una comunicación
  Entonces el sistema genera y registra únicamente un borrador
  Y no realiza ninguna solicitud de envío a Gmail
```

**Evidencia requerida:** prueba con adaptador espía que confirme cero envíos.

## AC-011 — Operación sin proveedor externo

**Cubre:** FR-016; NFR-003, NFR-004, NFR-006

```gherkin
Escenario: laboratorio sin API key
  Dado un entorno limpio con fixtures ficticios
  Cuando se siembra la base y se inicia API y frontend
  Entonces el recruiter puede recorrer vacantes, candidaturas, evaluación, revisión y auditoría
  Y ninguna prueba ni score requiere red
```

**Evidencia requerida:** instalación limpia, suite completa y recorrido reproducible.

## AC-012 — Migración reversible

**Cubre:** FR-017; NFR-007, NFR-008

```gherkin
Escenario: rollback durante la consolidación
  Dado que el ATS nuevo todavía no ha sido aceptado
  Cuando se ejecuta el entrypoint heredado de PostulaIA
  Entonces la carga PDF, OCR, ranking y consulta documental siguen funcionando
  Y la base ATS no altera sus resultados
```

**Evidencia requerida:** regresión de PostulaIA y comandos separados documentados.

## AC-013 — Publicación segura en GitHub

**Cubre:** NFR-003, NFR-008; SEC-001, SEC-010, SEC-011

```gherkin
Escenario: publicación del ATS consolidado
  Dado que la implementación y revisión fueron aprobadas
  Cuando se prepara el commit para PostulaIA-RRHH
  Entonces solo se incluyen código, pruebas, documentación y fixtures ficticios autorizados
  Y el escaneo no encuentra secretos, bases, CV reales, claves ni cachés
  Y el commit verificado se publica en la rama main
```

**Evidencia requerida:** lista staged explícita, escaneo del historial, suite aprobada y SHA remoto.
