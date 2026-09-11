# Criterios de aceptación — SPEC-021

## AC-021-001 — Configuración por criterio

```gherkin
Característica: Configuración de criterios de una vacante
  Escenario: Configurar inglés como criterio ponderado
    Dado un usuario autorizado editando una vacante en borrador
    Cuando configura inglés B2 como ponderado con una penalización válida
    Entonces la vista previa muestra su impacto máximo en el puntaje
    Y aprobar la vacante conserva esa configuración en una nueva versión
```

## AC-021-002 — Ausencia de evidencia

```gherkin
Característica: Evaluación documental prudente
  Escenario: El CV no declara nivel de inglés
    Dado que inglés B2 es un criterio ponderado requerido
    Cuando el CV no contiene evidencia suficiente del nivel
    Entonces el resultado del criterio es no_acreditado
    Y la evaluación de las demás dimensiones continúa
    Y el puntaje recibe únicamente la penalización configurada
    Y la candidatura requiere revisión humana
```

## AC-021-003 — Nivel inferior declarado

```gherkin
Característica: Penalización determinística
  Escenario: El CV declara un nivel inferior al requerido
    Dado que inglés B2 es ponderado
    Y el CV acredita inglés B1
    Cuando se calcula la evaluación
    Entonces el criterio queda como no_cumple
    Y se aplica la penalización configurada sin anular las demás dimensiones
    Y se explica el nivel esperado, el observado y el impacto numérico
```

## AC-021-004 — Filtro realmente excluyente

```gherkin
Característica: Conservación de filtros excluyentes
  Escenario: Incumplir de forma acreditada un requisito excluyente
    Dado un criterio aprobado como excluyente
    Y existe evidencia suficiente de que el candidato no lo cumple
    Cuando se ejecuta la evaluación
    Entonces el grafo puede omitir la evaluación semántica
    Y el resultado muestra No calculada en lugar de 0%
    Y explica el bloqueante y exige revisión humana antes de cualquier decisión
```

## AC-021-005 — Presentación no contradictoria

```gherkin
Característica: Resultado explicable
  Escenario: Algunos criterios se cumplen y otro no está acreditado
    Dado un resultado con criterios cumplidos y un criterio ponderado no acreditado
    Cuando RR. HH. abre el detalle
    Entonces ve por separado el puntaje calculado y la cobertura de criterios
    Y no se presenta la ausencia de cálculo como cero mérito
    Y puede identificar qué criterio causó la revisión
```

## AC-021-006 — Versionado y trazabilidad

```gherkin
Característica: Gobierno de criterios
  Escenario: Cambiar inglés de excluyente a ponderado
    Dado que una vacante tiene una versión aprobada
    Cuando un usuario autorizado cambia el tipo o la penalización del criterio
    Entonces se crea una nueva versión en borrador
    Y la vacante requiere nueva aprobación antes de evaluar
    Y las evaluaciones anteriores conservan su versión y resultado originales
```

## AC-021-007 — Cálculo independiente del modelo

```gherkin
Característica: Cálculo gobernado
  Escenario: El proveedor de IA devuelve una sugerencia distinta de penalización
    Dado que la vacante contiene una penalización aprobada
    Cuando el modelo produce su salida estructurada
    Entonces el backend ignora cualquier total o penalización propuesta por el modelo
    Y calcula el resultado usando únicamente la política aprobada
```

## AC-021-008 — Compatibilidad histórica

```gherkin
Característica: Migración segura
  Escenario: Consultar una evaluación anterior al cambio
    Dado que existe una evaluación creada con la política anterior
    Cuando RR. HH. consulta su trazabilidad
    Entonces conserva el puntaje, filtros y versión originales
    Y solo una reevaluación explícita genera un resultado con la política nueva
```
