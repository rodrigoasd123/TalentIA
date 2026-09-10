"""Métricas, seguimiento de coste y cronometraje de nodos.

En laboratorio las métricas viven en memoria. La interfaz está pensada para que
sustituir el backend por Prometheus sea cambiar una implementación, no reescribir
los puntos de instrumentación repartidos por el código.
"""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Iterator

# Precios de referencia por millón de tokens (USD). Son estimaciones para
# presupuestar en laboratorio, no facturación real: el proveedor manda.
PRICE_TABLE_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # modelo: (entrada, salida)
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "mock": (0.0, 0.0),
}
_DEFAULT_PRICE = (0.30, 2.50)


@dataclass(slots=True)
class TokenUsage:
    """Consumo acumulado de tokens y coste estimado."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    estimated_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, prompt: int, completion: int, model: str) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.calls += 1
        self.estimated_cost_usd += estimate_cost(prompt, completion, model)

    def merge(self, other: TokenUsage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.calls += other.calls
        self.estimated_cost_usd += other.estimated_cost_usd

    def to_dict(self) -> dict[str, float | int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Coste estimado de una llamada. Busca por prefijo para tolerar sufijos de versión."""
    key = model.lower().removeprefix("models/")
    price = PRICE_TABLE_USD_PER_MTOK.get(key)
    if price is None:
        price = next(
            (v for k, v in PRICE_TABLE_USD_PER_MTOK.items() if key.startswith(k)),
            _DEFAULT_PRICE,
        )
    return (prompt_tokens * price[0] + completion_tokens * price[1]) / 1_000_000


def approximate_tokens(text: str) -> int:
    """Estimación de tokens cuando el proveedor no los devuelve.

    Regla práctica para español e inglés: ~4 caracteres por token. Solo se usa
    como respaldo; si el proveedor informa del consumo real, se prefiere ese.
    """
    return max(1, len(text) // 4)


@dataclass(slots=True)
class MetricsRegistry:
    """Registro de métricas en memoria, seguro entre hilos."""

    counters: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    histograms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _lock: Lock = field(default_factory=Lock)

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            self.counters[_key(name, labels)] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self.histograms[_key(name, labels)].append(value)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self.counters),
                "histograms": {
                    k: {
                        "count": len(v),
                        "avg": round(sum(v) / len(v), 4) if v else 0.0,
                        "max": round(max(v), 4) if v else 0.0,
                        "p95": round(_percentile(v, 95), 4) if v else 0.0,
                    }
                    for k, v in self.histograms.items()
                },
            }

    def reset(self) -> None:
        with self._lock:
            self.counters.clear()
            self.histograms.clear()


def _key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    rendered = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}{{{rendered}}}"


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct / 100))
    return ordered[index]


METRICS = MetricsRegistry()


@contextmanager
def timed(metric: str, **labels: str) -> Iterator[dict[str, float]]:
    """Cronometra un bloque y registra su duración en segundos."""
    started = time.perf_counter()
    holder: dict[str, float] = {}
    try:
        yield holder
    finally:
        elapsed = time.perf_counter() - started
        holder["elapsed_seconds"] = elapsed
        METRICS.observe(metric, elapsed, **labels)


class BudgetGuard:
    """Corta la ejecución cuando el coste acumulado supera el presupuesto.

    Un presupuesto agotado no degrada la calidad en silencio: lanza y el caso
    pasa a revisión humana. Es preferible un caso sin evaluar a media evaluación
    presentada como completa.
    """

    def __init__(self, limit_usd: float, *, warn_ratio: float = 0.8) -> None:
        self.limit_usd = limit_usd
        self.warn_ratio = warn_ratio
        self.spent_usd = 0.0

    def charge(self, amount_usd: float) -> None:
        self.spent_usd += amount_usd

    @property
    def exhausted(self) -> bool:
        return self.limit_usd > 0 and self.spent_usd >= self.limit_usd

    @property
    def should_warn(self) -> bool:
        return self.limit_usd > 0 and self.spent_usd >= self.limit_usd * self.warn_ratio

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.limit_usd - self.spent_usd)


__all__ = [
    "METRICS",
    "BudgetGuard",
    "MetricsRegistry",
    "TokenUsage",
    "approximate_tokens",
    "estimate_cost",
    "timed",
]
