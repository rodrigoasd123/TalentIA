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
