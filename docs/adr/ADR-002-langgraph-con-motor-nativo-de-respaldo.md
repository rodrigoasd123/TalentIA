# ADR-002 — Orquestación con LangGraph y motor nativo de respaldo

- **Estado:** Aceptada
- **Fecha:** 2026-09-09

## Contexto

El flujo de evaluación tiene ramificaciones, reintentos acotados y puntos de
intervención humana. Necesita una orquestación explícita.

Las opciones consideradas fueron un agente ReAct de LangChain, LangGraph, o un
motor propio.

## Decisión

Se usa **LangGraph como capa de orquestación** cuando está instalado, con un
**motor nativo incluido** que implementa la misma semántica —nodos, aristas fijas,
aristas condicionales, estado tipado— y se activa automáticamente si LangGraph no
está disponible.

Los nodos son clases propias que cumplen un contrato del sistema, no de
LangGraph. El adaptador se limita a envolverlos.

## Justificación

**Por qué no un agente ReAct.** En un agente ReAct el modelo decide el siguiente
paso. Para un sistema de decisión sobre personas, el control del flujo debe estar
en el código: es lo único que hace la ejecución reproducible, el coste predecible
y la auditoría completa.

| Criterio | Agente ReAct | Grafo explícito |
|---|---|---|
| Control del flujo | El modelo | El código |
| Determinismo | Bajo | Alto |
| Auditabilidad | Reconstructiva | Cada nodo registra |
| Supervisión humana | Añadida a posteriori | Nativa |
| Superficie de injection | Amplia | Acotada |

**Por qué mantener dos motores.** Tiene una razón práctica y otra de diseño. La
práctica: el laboratorio arranca sin dependencias pesadas y el sistema funciona
con lo mínimo instalado. La de diseño, más importante: obliga a que la lógica viva
en los nodos y no en el motor. Si un nodo empezara a depender de una
particularidad de LangGraph, el motor nativo dejaría de pasar los tests y nos
enteraríamos en el mismo commit.

## Consecuencias

**Positivas.** Independencia real de un framework que evoluciona rápido. Los
diagramas del grafo se generan desde su definición, así que no pueden quedar
desactualizados. El motor nativo incluye validación de cableado —aristas rotas,
nodos inalcanzables— y un límite de pasos que corta ciclos infinitos.

**Negativas.** Hay que mantener la equivalencia entre ambos motores. Se mitiga
ejecutando la misma suite contra los dos y manteniendo la superficie del contrato
deliberadamente estrecha.

**Pendiente.** Los checkpoints persistentes y las interrupciones nativas de
LangGraph aún no se aprovechan; la cola de revisión humana se implementa como
estado del dominio. Se revisará cuando se conecte la persistencia completa.
