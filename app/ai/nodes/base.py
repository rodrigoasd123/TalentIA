"""Contrato común de los nodos del grafo.

Todo nodo cumple la misma interfaz, lo que permite instrumentarlos de forma
transversal: cronometraje, reintentos, registro de errores y auditoría se
implementan una vez aquí en lugar de repetirse en cada nodo.

La parte más útil del contrato son ``reads`` y ``writes``. Declarar qué claves
del estado toca cada nodo convierte en verificable una propiedad que de otro
modo sería solo una intención: que el nodo de puntuación no puede leer el mapa
de datos personales.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.ai.state import NodeError, WorkflowState, add_error
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """Metadatos declarados por cada nodo."""

    name: str
    version: str = "1.0.0"
    timeout_seconds: float = 30.0
    max_retries: int = 0
    is_deterministic: bool = True
    reads: frozenset[str] = frozenset()
    writes: frozenset[str] = frozenset()
    description: str = ""


class Node(ABC):
    """Nodo del grafo. Responsabilidad única, entrada y salida explícitas."""

    spec: NodeSpec

    @abstractmethod
    def run(self, state: WorkflowState) -> WorkflowState:
        """Lógica del nodo. No debe capturar excepciones propias del sistema:
        de eso se encarga ``execute``, para que el tratamiento sea uniforme."""

    # ── Instrumentación común ────────────────────────────────────────────────

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Ejecuta el nodo con cronometraje, reintentos y registro de errores."""
        started = time.perf_counter()
        attempt = 0
        last_error: Exception | None = None

        while attempt <= self.spec.max_retries:
            attempt += 1
            try:
                result = self.run(state)
                self._record(result, started, attempt, succeeded=True)
                return result
            except Exception as exc:  # noqa: BLE001 — se reclasifica más abajo
                last_error = exc
                recoverable = self._is_recoverable(exc)
                logger.warning(
                    "Fallo en nodo",
                    node=self.spec.name,
                    attempt=attempt,
                    error_type=type(exc).__name__,
                    error=str(exc)[:300],
                    recoverable=recoverable,
                )
                if not recoverable or attempt > self.spec.max_retries:
                    break

        assert last_error is not None
        add_error(
            state,
            NodeError(
                node=self.spec.name,
                error_type=type(last_error).__name__,
                message=str(last_error)[:500],
                attempt=attempt,
                recoverable=self._is_recoverable(last_error),
            ),
        )
        state = self.on_failure(state, last_error)
        self._record(state, started, attempt, succeeded=False)
        return state

    def on_failure(self, state: WorkflowState, error: Exception) -> WorkflowState:
        """Qué hacer cuando el nodo agota sus intentos.

        Por defecto no se detiene el grafo: se registra el fallo y el caso
        acabará en revisión humana. Detener el flujo dejaría al candidato en un
        limbo sin que nadie se entere.
        """
        return state

    def _record(
        self, state: WorkflowState, started: float, attempt: int, *, succeeded: bool
    ) -> None:
        elapsed = time.perf_counter() - started
        state.setdefault("node_timings", {})[self.spec.name] = round(elapsed, 4)
        sequence = state.setdefault("node_sequence", [])
        sequence.append(self.spec.name if succeeded else f"{self.spec.name}!")
        logger.info(
            "Nodo ejecutado",
            node=self.spec.name,
            version=self.spec.version,
            elapsed_seconds=round(elapsed, 4),
            attempts=attempt,
            succeeded=succeeded,
            deterministic=self.spec.is_deterministic,
        )

    @staticmethod
    def _is_recoverable(error: Exception) -> bool:
        """Un error de red o un timeout merecen reintento; uno de validación
        de esquema, no: reintentar no cambiará un contrato incumplido."""
        from app.core.exceptions import (
            LLMTimeout,
            LLMValidationError,
            PolicyDenied,
            ValidationError,
        )

        if isinstance(error, (ValidationError, PolicyDenied)):
            return False
        if isinstance(error, LLMValidationError):
            # Sí se reintenta: el reintento incluye una instrucción reforzada,
            # y en la práctica resuelve la mayoría de salidas malformadas.
            return True
        if isinstance(error, LLMTimeout):
            return True
        return isinstance(error, (TimeoutError, ConnectionError, OSError))


class FunctionNode(Node):
    """Adaptador para escribir un nodo como función simple.

    Útil para nodos triviales donde una clase completa sería ceremonia sin
    beneficio.
    """

    def __init__(self, spec: NodeSpec, fn) -> None:  # noqa: ANN001
        self.spec = spec
        self._fn = fn

    def run(self, state: WorkflowState) -> WorkflowState:
        return self._fn(state)


def verify_contract(node: Node, before: WorkflowState, after: WorkflowState) -> list[str]:
    """Comprueba que un nodo solo escribió lo que declaró escribir.

    Se usa en tests, no en producción: en caliente el coste de comparar estados
    completos no compensa. Devuelve la lista de violaciones encontradas.
    """
    violations: list[str] = []
    ignored = {"node_timings", "node_sequence", "errors"}
    for key in after:
        if key in ignored:
            continue
        changed = key not in before or before.get(key) is not after.get(key)
        if changed and key not in node.spec.writes:
            if before.get(key) != after.get(key):
                violations.append(
                    f"El nodo «{node.spec.name}» escribió «{key}», que no declara en writes"
                )
    return violations


__all__ = ["FunctionNode", "Node", "NodeSpec", "verify_contract"]
