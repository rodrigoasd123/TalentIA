"""Motor de ejecución del grafo.

TalentIA usa LangGraph cuando está instalado y, si no lo está, un motor nativo
incluido aquí con la misma semántica: nodos, aristas fijas, aristas
condicionales y un estado tipado que se propaga.

Puede parecer redundante mantener dos motores, pero tiene una razón práctica y
otra de diseño:

* **Práctica**: el laboratorio arranca sin dependencias pesadas. El sistema
  funciona con ``pip install`` de lo mínimo, y quien quiera LangGraph lo añade.
* **De diseño**: obliga a que la lógica viva en los nodos y no en el motor. Si
  un nodo empezara a depender de una particularidad de LangGraph, el motor
  nativo dejaría de pasar los tests y nos enteraríamos enseguida.

El motor nativo tiene además un límite de pasos que corta ciclos infinitos. Un
grafo mal cableado debe fallar con un error claro, no consumir presupuesto en
un bucle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.ai.nodes.base import Node
from app.ai.state import WorkflowState
from app.core.logging import get_logger

logger = get_logger(__name__)

END = "__end__"
START = "__start__"

Router = Callable[[WorkflowState], str]


class GraphEngine(Protocol):
    def invoke(self, state: WorkflowState) -> WorkflowState: ...


@dataclass(slots=True)
class GraphDefinition:
    """Descripción declarativa del grafo, independiente del motor que lo ejecute."""

    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)
    conditional: dict[str, tuple[Router, dict[str, str]]] = field(default_factory=dict)
    entry_point: str = ""
    max_steps: int = 40

    def add_node(self, node: Node) -> GraphDefinition:
        self.nodes[node.spec.name] = node
        return self

    def add_edge(self, source: str, target: str) -> GraphDefinition:
        self.edges[source] = target
        return self

    def add_conditional_edges(
        self, source: str, router: Router, mapping: dict[str, str]
    ) -> GraphDefinition:
        self.conditional[source] = (router, mapping)
        return self

    def set_entry_point(self, name: str) -> GraphDefinition:
        self.entry_point = name
        return self

    def validate(self) -> None:
        """Comprueba que el grafo está bien cableado antes de ejecutarlo.

        Detectar aquí una arista rota es mucho más barato que descubrirla a
        mitad de una evaluación real.
        """
        if not self.entry_point:
            raise ValueError(f"El grafo «{self.name}» no declara punto de entrada")
        if self.entry_point not in self.nodes:
            raise ValueError(f"El punto de entrada «{self.entry_point}» no es un nodo")
        for source, target in self.edges.items():
            if source not in self.nodes:
                raise ValueError(f"Arista desde un nodo inexistente: {source}")
            if target != END and target not in self.nodes:
                raise ValueError(f"Arista hacia un nodo inexistente: {source} → {target}")
        for source, (_, mapping) in self.conditional.items():
            if source not in self.nodes:
                raise ValueError(f"Arista condicional desde un nodo inexistente: {source}")
            for target in mapping.values():
                if target != END and target not in self.nodes:
                    raise ValueError(
                        f"Arista condicional hacia un nodo inexistente: {source} → {target}"
                    )
        unreachable = self._unreachable_nodes()
        if unreachable:
            raise ValueError(f"Nodos inalcanzables en «{self.name}»: {', '.join(unreachable)}")

    def _unreachable_nodes(self) -> list[str]:
        reachable: set[str] = set()
        pending = [self.entry_point]
        while pending:
            current = pending.pop()
            if current in reachable or current == END:
                continue
            reachable.add(current)
            if current in self.conditional:
                pending.extend(self.conditional[current][1].values())
            elif current in self.edges:
                pending.append(self.edges[current])
        return sorted(set(self.nodes) - reachable)

    def next_node(self, current: str, state: WorkflowState) -> str:
        if current in self.conditional:
            router, mapping = self.conditional[current]
            key = router(state)
            target = mapping.get(key)
            if target is None:
                raise ValueError(
                    f"El enrutador de «{current}» devolvió «{key}», que no está en el mapeo"
                )
            return target
        return self.edges.get(current, END)

    def to_mermaid(self) -> str:
        """Diagrama del grafo generado desde su propia definición."""
        lines = ["flowchart TD", f"    {START}([inicio]) --> {self.entry_point}"]
        for source, target in sorted(self.edges.items()):
            label = END if target == END else target
            lines.append(f"    {source} --> {label}")
        for source, (_, mapping) in sorted(self.conditional.items()):
            for key, target in mapping.items():
                lines.append(f"    {source} -->|{key}| {target}")
        lines.append(f"    {END}([fin])")
        return "\n".join(lines)


class NativeGraphEngine:
    """Motor incluido. Ejecuta el grafo paso a paso, sin dependencias externas."""

    def __init__(self, definition: GraphDefinition) -> None:
        definition.validate()
        self.definition = definition

    def invoke(self, state: WorkflowState) -> WorkflowState:
        current = self.definition.entry_point
        steps = 0

        while current != END:
            steps += 1
            if steps > self.definition.max_steps:
                raise RuntimeError(
                    f"El grafo «{self.definition.name}» superó {self.definition.max_steps} pasos; "
                    "posible ciclo infinito"
                )
            node = self.definition.nodes[current]
            state = node.execute(state)

            if state.get("terminated_early"):
                logger.warning(
                    "Grafo interrumpido tras un fallo no recuperable",
                    node=current,
                    reason=state.get("termination_reason", ""),
                )
                # Aun interrumpido, se pasa por auditoría para dejar constancia.
                if "audit" in self.definition.nodes and current != "audit":
                    state = self.definition.nodes["audit"].execute(state)
                return state

            current = self.definition.next_node(current, state)

        return state


class LangGraphEngine:
    """Adaptador sobre LangGraph, cuando está disponible.

    La conversión es directa porque el modelo mental es el mismo. Los nodos no
    cambian: se envuelven en una función que delega en ``Node.execute``.
    """

    def __init__(self, definition: GraphDefinition) -> None:
        definition.validate()
        self.definition = definition
        self._compiled = self._compile()

    def _compile(self):  # noqa: ANN202 — el tipo lo aporta LangGraph
        from langgraph.graph import END as LG_END
        from langgraph.graph import StateGraph

        builder = StateGraph(dict)
        for name, node in self.definition.nodes.items():
            builder.add_node(name, self._wrap(node))
        builder.set_entry_point(self.definition.entry_point)

        for source, target in self.definition.edges.items():
            builder.add_edge(source, LG_END if target == END else target)

        for source, (router, mapping) in self.definition.conditional.items():
            translated = {k: (LG_END if v == END else v) for k, v in mapping.items()}
            builder.add_conditional_edges(source, router, translated)

        return builder.compile()

    @staticmethod
    def _wrap(node: Node):  # noqa: ANN202
        def _run(state: dict) -> dict:
            return dict(node.execute(state))  # type: ignore[arg-type]

        return _run

    def invoke(self, state: WorkflowState) -> WorkflowState:
        return self._compiled.invoke(dict(state))  # type: ignore[return-value]


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


def build_engine(definition: GraphDefinition, *, prefer_langgraph: bool = True) -> GraphEngine:
    """Devuelve el motor disponible, prefiriendo LangGraph si está instalado."""
    if prefer_langgraph and langgraph_available():
        try:
            engine = LangGraphEngine(definition)
            logger.info("Grafo compilado con LangGraph", graph=definition.name)
            return engine
        except Exception as exc:  # noqa: BLE001 — degradar es preferible a fallar
            logger.warning(
                "No se pudo compilar con LangGraph; se usa el motor nativo",
                error=str(exc)[:200],
            )
    logger.info("Grafo compilado con el motor nativo", graph=definition.name)
    return NativeGraphEngine(definition)


__all__ = [
    "END", "START", "GraphDefinition", "GraphEngine", "LangGraphEngine",
    "NativeGraphEngine", "build_engine", "langgraph_available",
]
