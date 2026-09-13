"""LangGraph de evaluacion con nodos idempotentes y salida HITL."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from typing import Any

from talentia.ai.workflows.estado import EstadoEvaluacion

NODOS = (
    "validar_entradas",
    "cargar_documento",
    "sanitizar_pii",
    "extraer_cv",
    "validar_fuentes",
    "relacionar_requisitos",
    "verificar_evidencia_original",
    "veredicto_deterministico",
    "persistir_evaluacion",
    "revision_humana",
)


def _nodo(nombre: str) -> Callable[[EstadoEvaluacion], EstadoEvaluacion]:
    def ejecutar(estado: EstadoEvaluacion) -> EstadoEvaluacion:
        completados = list(estado.get("nodos_completados", []))
        if nombre not in completados:
            completados.append(nombre)
        salida = dict(estado)
        salida["nodos_completados"] = completados
        if nombre == "revision_humana":
            salida["revision_requerida"] = True
        return salida  # type: ignore[return-value]

    return ejecutar


def construir_grafo() -> Any:
    from langgraph.graph import END, START, StateGraph

    constructor = StateGraph(EstadoEvaluacion)
    for nombre in NODOS:
        constructor.add_node(nombre, _nodo(nombre))
    constructor.add_edge(START, NODOS[0])
    for origen, destino in pairwise(NODOS):
        constructor.add_edge(origen, destino)
    constructor.add_edge(NODOS[-1], END)
    return constructor.compile()
