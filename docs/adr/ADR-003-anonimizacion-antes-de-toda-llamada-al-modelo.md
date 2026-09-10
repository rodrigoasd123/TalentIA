# ADR-003 — La anonimización precede a toda llamada al modelo

- **Estado:** Aceptada
- **Fecha:** 2026-09-09
- **Sustituye a:** una versión anterior del grafo que anonimizaba tras la extracción

## Contexto

El grafo hace dos llamadas al proveedor externo sobre el documento del candidato:
la extracción estructurada y la evaluación semántica.

El diseño inicial anonimizaba **entre ambas**. El razonamiento era que la
extracción necesita ver el documento completo para obtener idiomas, fechas y
tecnologías, mientras que el riesgo de sesgo se materializa en la evaluación.

Al escribir la prueba de frontera —la que intercepta el payload real enviado al
proveedor— quedó claro que ese razonamiento tenía un agujero: la extracción
también sale hacia un servicio externo, y estaba enviando nombre, edad, teléfono,
documento de identidad y dirección.

## Decisión

**La anonimización se ejecuta antes de la extracción.** Ambos nodos con modelo
trabajan sobre el texto anonimizado.

El orden del grafo pasa a ser:

```
validación → sanitización → anonimización → extracción → filtros → evaluación
```

Se añade una prueba estructural que verifica la propiedad por alcanzabilidad: si
se elimina el nodo de anonimización del grafo, ningún nodo con modelo debe seguir
siendo alcanzable desde la entrada.

## Justificación

El requisito del sistema es que **ninguna** información personal cruce hacia el
proveedor. El diseño anterior lo cumplía "casi siempre", que en materia de
protección de datos equivale a no cumplirlo.

Y no hacía falta el compromiso: la extracción necesita años de experiencia,
tecnologías, formación e idiomas, y nada de eso es información personal. El
nombre y el correo del candidato ya los tiene el sistema desde su registro; no
hay ninguna razón para volver a obtenerlos del documento.

Comprobar la propiedad por orden de recorrido no basta: un grafo con
ramificaciones puede tener un camino alternativo que se salte el nodo. La
comprobación correcta es de alcanzabilidad, y así se implementó.

## Consecuencias

**Positivas.** El sistema cumple su propio requisito de forma verificable. La
verificación de evidencia gana coherencia: se comprueba contra el mismo texto que
vio el modelo, no contra uno distinto.

**Negativas.** El nombre de la institución educativa llega tokenizado a la
extracción, así que no queda registrado en los datos estructurados. Es aceptable,
e incluso deseable: el prestigio de la institución es un indicador indirecto de
clase social que el sistema no debe considerar. El recruiter siempre puede
consultar el CV original.

## Lección

El fallo no estuvo en la implementación sino en el diseño, y solo apareció al
escribir una prueba que verificaba el comportamiento real en lugar del comportamiento
declarado. Una capa de anonimización sin un test que inspeccione el payload que
sale es una intención, no una garantía.
