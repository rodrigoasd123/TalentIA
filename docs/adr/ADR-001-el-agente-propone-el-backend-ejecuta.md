# ADR-001 — El agente propone, el backend ejecuta

- **Estado:** Aceptada
- **Fecha:** 2026-09-09
- **Decisores:** Equipo de arquitectura

## Contexto

VERA procesa CVs, que son contenido escrito por terceros con interés directo en
el resultado de la evaluación. Un modelo de lenguaje es un componente no
determinista que interpreta ese contenido.

La pregunta de partida es qué capacidad de acción concederle: ¿puede cambiar el
estado de una candidatura? ¿Puede enviar un correo? ¿Puede consultar la base de
datos?

## Decisión

**El agente no ejecuta ninguna acción.** Produce objetos `ProposedAction` que el
motor de políticas evalúa y la capa de aplicación ejecuta si procede.

En la fase de evaluación, los agentes **no tienen herramienta alguna**: son
transformadores puros de datos. Los datos los aporta el grafo mediante nodos
determinísticos que consultan los repositorios.

## Justificación

Conceder capacidad de ejecución a un modelo que procesa entrada no confiable
equivale a ejecutar instrucciones procedentes de un fichero subido por un
desconocido. Da igual lo bueno que sea el prompt: el modelo de confianza es el
que está mal.

Al invertirlo, el prompt injection tiene techo. Un atacante puede como mucho
alterar el contenido de un objeto Pydantic con campos acotados, que después será
validado, verificado contra el documento y sometido al motor de políticas. No
existe ningún camino desde el texto de un CV hasta un efecto en el mundo.

Como efecto secundario, la ausencia de herramientas elimina de raíz la categoría
completa de ataques por inyección de herramientas.

## Consecuencias

**Positivas.** El sistema es auditable: cada acción tiene un veredicto de política
registrado. Los nodos se prueban aisladamente sin infraestructura. El coste es
predecible porque el modelo no decide cuántas llamadas hace.

**Negativas.** Más código que un agente autónomo: hay que escribir explícitamente
cada política y cada transición. Añadir una capacidad nueva exige tocar el
catálogo de acciones, el motor de políticas y sus pruebas.

Esa fricción es intencionada: hace que ampliar los poderes del agente sea una
decisión consciente y no un efecto colateral.

## Alternativas descartadas

**Agente ReAct con herramientas de escritura.** Descartada: el control del flujo
quedaría en el modelo, la auditoría sería reconstructiva y la superficie de
prompt injection, ilimitada.

**Agente con herramientas de solo lectura.** Descartada para la fase de
evaluación: si el agente decide qué leer, un CV puede influir en esa decisión. Es
preferible que el grafo determine los datos y el agente solo los transforme. La
política de herramientas queda diseñada por si en el futuro se añade un agente
conversacional para el recruiter, que sí las necesitaría.
