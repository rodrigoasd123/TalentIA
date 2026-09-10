# ADR-007 — Agentes LangGraph trazados centralmente con MLflow

- **Estado:** Aceptada
- **Fecha:** 2026-09-10

## Contexto

TalentIA prevé inteligencia de requisitos, CV, carrera, matching y
redescubrimiento. Sin una frontera uniforme, las llamadas a modelos podrían
dispersarse por servicios o interfaces, filtrar PII, producir salidas sin
validación y acoplar el dominio a un proveedor. El core ATS debe seguir
funcionando aunque el proveedor IA o la telemetría no estén disponibles.

## Decisión

Todo componente denominado AI Agent se implementa con LangGraph. No se crean
agentes para RBAC, workflow, auditoría, transacciones, duplicados exactos,
validación de archivos, políticas de recontacto ni scoring determinista.

Cada agente vive bajo `app/agents/<capacidad>/` y contiene como mínimo
`graph.py`, `state.py`, `nodes.py`, `schemas.py`, `tools.py`, `guards.py`,
`config.py`, prompts externos y tests. Usa estado explícito tipado, nodos de
responsabilidad única, conditional edges cuando correspondan, límites de pasos,
timeout, retries, validación Pydantic y Human-in-the-Loop/checkpointing para
ejecuciones reanudables. No habrá un mega-agent general.

Los grafos solo conocen el puerto `LLMProvider`. El primer adaptador es
`GeminiProvider`, mediante la integración Python mantenida de Google. Las claves
entran por variables de entorno y nunca por el repositorio. La free tier solo se
usa con datos sintéticos; el envío de CV reales o PII queda deshabilitado hasta
aprobación de Security/Legal.

MLflow Tracing se configura una sola vez en `app/agents/shared/tracing/` y cubre
grafos, nodos, tools y llamadas LLM. Registra IDs internos, versiones, modelo,
latencia, estado, errores y evaluación, pero un sanitizador elimina CV, documento,
email, teléfono y otra PII antes de exportar. La indisponibilidad de MLflow se
degrada a telemetría local segura y nunca decide el commit de negocio.

El único flujo de persistencia permitido es:

```text
LangGraph -> output Pydantic validado -> application service
          -> reglas de negocio -> transacción -> repositorio
```

## Consecuencias

- Los agentes iniciales serán `RequirementIntelligenceAgent`,
  `CVIntelligenceAgent`, `CareerIntelligenceAgent`, `MatchingAgent` y
  `RediscoveryAgent`, cada uno en su fase.
- Toda ejecución tendrá `agent_execution_id`, `thread_id` cuando aplique,
  `agent_version`, `graph_version`, `prompt_version`, `model` y `status`.
- Los prompts poseen ID y versión; no se incrustan como strings extensos en nodos.
- Se requieren pruebas de nodo, routing/grafo, output estructurado, redacción de
  PII y fallos de Gemini/MLflow.
- Hay más estructura inicial, pero se evitan acoplamiento, trazas opacas y
  escrituras directas del LLM.
- Esta decisión no autoriza implementar agentes antes de completar sus
  prerrequisitos de fase.

## Alternativas descartadas

- Llamadas directas al LLM desde services, routers o Streamlit: dispersan
  políticas y observabilidad.
- SDK Gemini dentro de cada grafo: acopla el agente al proveedor.
- Un agente general: mezcla responsabilidades, herramientas y permisos.
- Trazar inputs completos: expone PII y CV en un sistema de observabilidad.
- Hacer obligatoria la disponibilidad de MLflow para transacciones ATS: añade
  un punto de fallo ajeno al negocio.
