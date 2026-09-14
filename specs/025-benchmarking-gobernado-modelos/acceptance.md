# Aceptación — SPEC-025

## AC-025-001 — Comparación reproducible

**Cubre:** FR-025-001, FR-025-002

```gherkin
Dada una suite sintética versionada y dos modelos falsos
Cuando se ejecuta el benchmark
Entonces ambos reciben los mismos casos y se devuelven detalle, hash, versión y ranking estable
```

## AC-025-002 — Quality gate

**Cubre:** FR-025-003

```gherkin
Dado un baseline y un candidato con peor calidad o errores excesivos
Cuando se agregan resultados
Entonces el candidato queda failed con motivos verificables
```

## AC-025-003 — Control humano y presupuesto

**Cubre:** FR-025-004, NFR-025-001, SEC-025-002

```gherkin
Dado un usuario autorizado
Cuando selecciona más modelos de los permitidos o no confirma la ejecución
Entonces no se realizan llamadas ni se cambia la configuración activa
```

## AC-025-004 — Sin red en tests

**Cubre:** NFR-025-002, SEC-025-001

```gherkin
Dada la suite automatizada
Cuando se ejecuta en CI
Entonces usa dobles, datos sintéticos y cero llamadas externas
```

**Evidencia (2026-09-12):** suite sintética versionada y sin red; pruebas de ranking, quality gate y ocultación de respuestas incluidas en 310 passed.

## Refinamiento R1 aprobado y verificado

### AC-025-005 — Histórico e indicadores comparables

**Cubre:** FR-025-005, FR-025-006, FR-025-007, NFR-025-003

```gherkin
Dadas varias ejecuciones persistidas con modelos y suites diferentes
Cuando el administrador filtra y abre una comparación
Entonces ve procedencia, versiones, calidad, errores, p50/p95, tokens de entrada/salida y costo
Y el ranking se reproduce a partir de los mismos resultados
```

### AC-025-006 — Sin activación automática

**Cubre:** FR-025-008

```gherkin
Dado que un modelo obtiene el mejor indicador del benchmark
Cuando finaliza la comparación
Entonces el panel puede destacarlo con las reglas aplicadas
Pero la configuración activa permanece sin cambios
```

### AC-025-007 — MLflow opcional y enlace seguro

**Cubre:** FR-025-009, NFR-025-004, SEC-025-003

```gherkin
Dada una ejecución registrada
Cuando MLflow está disponible el backend entrega un enlace seguro a su run
Y cuando no está disponible el histórico local continúa visible sin enlace
```

### AC-025-008 — Benchmark sin contenido sensible

**Cubre:** SEC-025-004

```gherkin
Dado un benchmark ejecutado desde el panel
Cuando se revisan API, SQLite, logs y MLflow
Entonces no aparecen prompts, respuestas ni contenido de los casos sintéticos
```
