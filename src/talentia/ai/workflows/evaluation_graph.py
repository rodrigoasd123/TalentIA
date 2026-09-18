"""LangGraph de evaluacion con nodos reales, rutas seguras e idempotencia."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any

from talentia.ai.workflows.estado import EstadoEvaluacion
from talentia.ai.workflows.nodos_evaluacion import ContextoNodosEvaluacion

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


GuardarCheckpoint = Callable[[str, EstadoEvaluacion], None]
NodoCompletado = Callable[[str, EstadoEvaluacion], None]


def _siguiente(estado: EstadoEvaluacion) -> str:
    completados = set(estado.get("nodos_completados", []))
    for nombre in NODOS:
        if nombre not in completados:
            return nombre
    return "fin"


class _GrafoNativo:
    """Ejecutor secuencial seguro cuando LangGraph no esta disponible."""

    def __init__(
        self,
        contexto: ContextoNodosEvaluacion,
        guardar_checkpoint: GuardarCheckpoint,
        nodo_completado: NodoCompletado | None,
    ) -> None:
        self._funciones = {nombre: getattr(contexto, nombre) for nombre in NODOS}
        self._guardar_checkpoint = guardar_checkpoint
        self._nodo_completado = nodo_completado

    def invoke(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        actual = estado
        indice_veredicto = NODOS.index("veredicto_deterministico")
        for indice, nombre in enumerate(NODOS):
            if nombre in actual.get("nodos_completados", []):
                continue
            if actual.get("error") and indice < indice_veredicto:
                continue
            salida: EstadoEvaluacion = self._funciones[nombre](actual)
            completados = list(salida.get("nodos_completados", []))
            completados.append(nombre)
            salida["nodos_completados"] = completados
            self._guardar_checkpoint(nombre, salida)
            if self._nodo_completado is not None:
                self._nodo_completado(nombre, salida)
            if indice < 5 and salida.get("revision_requerida"):
                desvio_temprano = True
            actual = salida
        return actual


def _ruta_segura(estado: EstadoEvaluacion, siguiente: str) -> str:
    if estado.get("revision_requerida"):
        return "veredicto_deterministico"
    return siguiente


def construir_grafo(
    contexto: ContextoNodosEvaluacion,
    guardar_checkpoint: GuardarCheckpoint,
    nodo_completado: NodoCompletado | None = None,
) -> Any:
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _GrafoNativo(contexto, guardar_checkpoint, nodo_completado)

    constructor = StateGraph(EstadoEvaluacion)
    funciones = {nombre: getattr(contexto, nombre) for nombre in NODOS}

    def envolver(nombre: str) -> Callable[[EstadoEvaluacion], EstadoEvaluacion]:
        def ejecutar(estado: EstadoEvaluacion) -> EstadoEvaluacion:
            if nombre in estado.get("nodos_completados", []):
                return estado
            salida: EstadoEvaluacion = funciones[nombre](estado)
            completados = list(salida.get("nodos_completados", []))
            completados.append(nombre)
            salida["nodos_completados"] = completados
            guardar_checkpoint(nombre, salida)
            if nodo_completado is not None:
                nodo_completado(nombre, salida)
            return salida

        return ejecutar

    for nombre in NODOS:
        constructor.add_node(nombre, envolver(nombre))
    rutas_inicio: dict[Hashable, str] = {nombre: nombre for nombre in NODOS}
    rutas_inicio["fin"] = END
    constructor.add_conditional_edges(START, _siguiente, rutas_inicio)
    for indice, nombre in enumerate(NODOS[:-1]):
        siguiente = NODOS[indice + 1]
        if nombre in NODOS[:5]:
            constructor.add_conditional_edges(
                nombre,
                lambda estado, destino=siguiente: _ruta_segura(estado, destino),
                {
                    siguiente: siguiente,
                    "veredicto_deterministico": "veredicto_deterministico",
                },
            )
        else:
            constructor.add_edge(nombre, siguiente)
    constructor.add_edge(NODOS[-1], END)
    return constructor.compile()
