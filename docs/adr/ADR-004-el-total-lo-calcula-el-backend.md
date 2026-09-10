# ADR-004 — El total lo calcula el backend, no el modelo

- **Estado:** Aceptada
- **Fecha:** 2026-09-09

## Contexto

La evaluación produce puntuaciones por dimensión (técnica, experiencia,
formación, proyectos, encaje semántico) y una puntuación total que determina si
la candidatura supera el umbral de la vacante.

La opción evidente es pedir al modelo que devuelva ambas cosas.

## Decisión

El esquema de salida del modelo **no tiene campo `total_score`**. El modelo
puntúa dimensiones; el total lo calcula `app.domain.rules.scoring` con los pesos
configurados en la vacante.

Tampoco tiene campo para el destinatario de un correo, ni para el estado
resultante, ni para ninguna acción.

## Justificación

**Reproducibilidad.** Un total calculado en código es idéntico hoy y dentro de
dos años con los mismos insumos. Un total generado por un modelo depende de la
versión del proveedor, que puede cambiar sin aviso.

**Defensa contra la manipulación.** La forma más directa de influir en una
puntuación es pedírsela al modelo. Si no existe un campo donde escribirla, la
petición no tiene dónde aterrizar. El guardrail más sólido no es el que valida un
campo peligroso: es el que hace que ese campo no exista.

**Transparencia.** Cuando un candidato pregunta cómo se calculó su puntuación, la
respuesta es una fórmula con los pesos publicados en las bases de la convocatoria,
no "lo dijo el modelo".

**Renormalización.** Al calcularlo nosotros podemos decidir qué hacer cuando el
modelo omite una dimensión: se renormaliza sobre las presentes en lugar de contar
cero. Un fallo del modelo no debe traducirse en una penalización silenciosa al
candidato.

## Consecuencias

**Positivas.** El total es auditable y reproducible. Cambiar los pesos de una
vacante no exige tocar el prompt. La misma evaluación puede recalcularse con
criterios distintos para simular escenarios.

**Negativas.** El modelo pierde la posibilidad de aportar un juicio holístico que
no se descomponga en dimensiones. Se mitiga con la dimensión `semantic`, que
recoge precisamente el encaje global, y con el campo `recommendation`, que es
orientativo y no decide nada por sí solo.

## Regla derivada

Ningún esquema de salida del modelo debe contener un campo que exprese una
**acción** o una **decisión final**. Solo observaciones, puntuaciones parciales y
evidencia. Es una regla revisable en cada nuevo esquema que se añada.
