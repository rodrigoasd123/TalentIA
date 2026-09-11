# Criterios de aceptación — SPEC-020

## AC-020-001 — Tabla general como vista principal

**Cubre:** FR-020-001, FR-020-002, NFR-020-003

```gherkin
Escenario: consultar la base centralizada
  Dado un usuario con permiso de lectura y candidatos persistidos en SQLite
  Cuando abre Candidatos
  Entonces ve primero una tabla general con el total de resultados
  Y puede buscar y filtrar sin modificar la fuente de verdad
```

## AC-020-002 — Edición desde la fila seleccionada

**Cubre:** FR-020-003, FR-020-004, FR-020-005, SEC-020-004

```gherkin
Escenario: actualizar una ficha
  Dado un usuario con permiso de escritura
  Cuando selecciona una fila, modifica la ficha y guarda
  Entonces Streamlit envía la versión leída a FastAPI
  Y la ficha queda persistida y auditada
  Y una versión obsoleta no sobrescribe cambios recientes
```

## AC-020-003 — Alta integrada

**Cubre:** FR-020-005, NFR-020-001

```gherkin
Escenario: registrar una persona sin Excel
  Dado un usuario con permiso de escritura
  Cuando abre Nuevo candidato y completa los datos obligatorios
  Entonces FastAPI crea la ficha en SQLite
  Y la persona aparece en la tabla general al recargar
```

## AC-020-004 — Separación de estados

**Cubre:** FR-020-006, FR-020-007, SEC-020-005

```gherkin
Escenario: consultar seguimiento por vacante
  Dado un candidato con una o más postulaciones
  Cuando aparece en la tabla general
  Entonces se muestran sus estados asociados a cada vacante
  Y la pantalla no permite cambiar esos estados desde la ficha general
```

## AC-020-005 — Exportación opcional y segura

**Cubre:** FR-020-008, FR-020-009, SEC-020-002, SEC-020-003

```gherkin
Escenario: exportar la vista filtrada
  Dado un conjunto filtrado de candidatos permitido para el rol
  Cuando el usuario descarga el CSV
  Entonces el archivo contiene solo esas filas y columnas visibles
  Y neutraliza celdas que podrían interpretarse como fórmulas
  Y la pantalla mantiene claro que SQLite es la base operativa
```

## AC-020-006 — Regresión y experiencia

**Cubre:** NFR-020-002, NFR-020-004, NFR-020-005

La lógica pura debe tener pruebas unitarias, la vista debe superar un smoke de
Streamlit sin excepciones y la suite completa del repositorio debe aprobarse.
