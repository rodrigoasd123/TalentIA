# Criterios de aceptación — SPEC-005

**Característica:** importación histórica gobernada desde CSV y XLSX.

## AC-001 — Carga segura e idempotente

**Cubre:** FR-001, FR-002, FR-011, NFR-007, SEC-002, SEC-003, SEC-004, SEC-010

```gherkin
Escenario: cargar dos veces el mismo archivo permitido
  Dado un CSV o XLSX ficticio que cumple los límites configurados
  Cuando un recruiter autorizado carga el mismo contenido dos veces
  Entonces el sistema devuelve el mismo lote lógico o señala que ya existe
  Y no duplica filas preparadas
  Y registra el checksum sin ejecutar fórmulas, macros, enlaces ni contenido incrustado
```

**Evidencia requerida:** prueba de integración FastAPI y prueba del adaptador tabular con archivos maliciosos y repetidos.

## AC-002 — Mapeo explícito sin hardcoding

**Cubre:** FR-003, FR-004, NFR-002, NFR-004

```gherkin
Escenario: mapear encabezados de una hoja a campos canónicos
  Dado un libro ficticio con encabezados que no coinciden con los nombres internos
  Cuando el recruiter selecciona la hoja y confirma un mapeo válido desde Streamlit
  Entonces FastAPI guarda el mapeo del lote
  Y muestra los campos obligatorios y transformaciones
  Y Streamlit no escribe SQLite ni decide la validez de las filas
```

**Evidencia requerida:** pruebas del caso de uso y del contrato API; smoke reproducible de la pantalla.

## AC-003 — Validación aislada en staging

**Cubre:** FR-005, FR-013, NFR-003, NFR-008, SEC-005

```gherkin
Escenario: validar un lote con filas válidas e inválidas
  Dado un lote cargado y un mapeo aprobado
  Cuando el sistema valida sus filas
  Entonces registra errores por fila y campo únicamente en staging
  Y publica conteos paginados
  Y no crea ni modifica candidatos o candidaturas
  Y el lote queda en READY_FOR_REVIEW o PARTIALLY_VALID según el resultado
```

**Evidencia requerida:** prueba de integración que compare las tablas operativas antes y después de validar, más inspección de logs sin PII.

## AC-004 — Duplicados y conflictos explicables

**Cubre:** FR-006, FR-007, FR-008, SEC-007

```gherkin
Escenario: clasificar filas frente a la fuente de verdad
  Dado un lote con una persona nueva, una coincidencia exacta, una posible coincidencia y una candidatura ya existente
  Cuando se genera la previsualización
  Entonces cada fila recibe una clasificación y señales explicables no sensibles
  Y las filas ambiguas o ya vinculadas no quedan seleccionadas para creación automática
```

**Evidencia requerida:** pruebas parametrizadas de clasificación y respuesta API minimizada por permiso.

## AC-005 — Confirmación autorizada y transaccional

**Cubre:** FR-009, FR-010, FR-011, NFR-005, SEC-001, SEC-007, SEC-008

```gherkin
Escenario: confirmar filas elegibles de un lote revisado
  Dado un lote READY_FOR_REVIEW con filas nuevas y una requisición existente
  Cuando un HR Manager autorizado confirma el lote con una clave de idempotencia
  Entonces el sistema crea Candidate y Application respetando sus reglas de dominio
  Y marca el lote IMPORTED en la misma transacción
  Y repetir la petición devuelve el resultado anterior sin nuevas filas de negocio
```

```gherkin
Escenario: revertir una confirmación fallida
  Dado un lote revisado cuya confirmación falla en una fila elegible
  Cuando se intenta confirmar
  Entonces no se conserva ningún candidato ni candidatura parcial de ese intento
  Y el lote mantiene un estado recuperable con evidencia del error sin PII
```

**Evidencia requerida:** pruebas de integración SQLite de autorización, rollback e idempotencia concurrente/controlada.

## AC-006 — Consentimiento histórico gobernado

**Cubre:** FR-004, FR-008, SEC-006, SEC-008

```gherkin
Escenario: encontrar una fila sin evidencia de tratamiento aprobada
  Dado un lote histórico con una fila sin evidencia de consentimiento o base autorizada
  Cuando el sistema valida la fila
  Entonces aplica la política que apruebe el responsable de producto
  Y nunca ejecuta matching, contacto, rechazo ni cambio automático de pipeline
```

**Evidencia requerida:** prueba de política pendiente de concretar al resolver la pregunta bloqueante de consentimiento.

## AC-007 — Reporte corregible y minimizado

**Cubre:** FR-012, SEC-005, SEC-006, SEC-009

```gherkin
Escenario: descargar errores de un lote parcialmente válido
  Dado un usuario autorizado y un lote con errores
  Cuando solicita el reporte de corrección
  Entonces el archivo identifica fila, campo y motivo
  Y neutraliza contenido que una hoja de cálculo interpretaría como fórmula
  Y omite o enmascara PII no necesaria según el permiso
```

**Evidencia requerida:** prueba del archivo exportado y prueba de autorización con roles distintos.

## AC-008 — Cancelación auditable

**Cubre:** FR-013, FR-014, SEC-001, SEC-005

```gherkin
Escenario: cancelar un lote antes de confirmarlo
  Dado un lote que todavía no está IMPORTED
  Cuando una persona autorizada lo cancela con una justificación
  Entonces el lote deja de estar disponible para confirmación
  Y la auditoría conserva actor, fecha, lote y motivo sin copiar sus filas
```

**Evidencia requerida:** prueba de transición de estado, autorización y cadena de auditoría.
