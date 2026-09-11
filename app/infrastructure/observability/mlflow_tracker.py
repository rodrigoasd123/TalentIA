"""Registro seguro de llamadas LLM en MLflow.

Solo se guardan metadatos operativos. Los prompts, respuestas y API keys nunca
se envían a MLflow porque pueden contener información de candidatos.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.observability import METRICS

logger = get_logger(__name__)


class MlflowLLMTracker:
    """Persiste una ejecución MLflow por llamada al modelo."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._warned = False
        self._usage: dict[tuple[str, str], dict[str, float | int]] = {}

    def record(
        self,
        *,
        provider: str,
        model: str,
        elapsed_seconds: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        status: str = "ok",
        error_type: str = "",
    ) -> None:
        labels = {"provider": provider, "model": model}
        METRICS.increment("talentia.llm.calls", status=status, **labels)
        METRICS.increment("talentia.llm.prompt_tokens", prompt_tokens, **labels)
        METRICS.increment("talentia.llm.completion_tokens", completion_tokens, **labels)
        METRICS.increment(
            "talentia.llm.total_tokens", prompt_tokens + completion_tokens, **labels
        )
        METRICS.observe("talentia.llm.latency_seconds", elapsed_seconds, **labels)

        with self._lock:
            usage = self._usage.setdefault(
                (provider, model),
                {
                    "calls": 0,
                    "errors": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "total_latency_seconds": 0.0,
                },
            )
            usage["calls"] += 1
            usage["errors"] += int(status != "ok")
            usage["prompt_tokens"] += prompt_tokens
            usage["completion_tokens"] += completion_tokens
            usage["total_tokens"] += prompt_tokens + completion_tokens
            usage["total_latency_seconds"] += elapsed_seconds

        settings = get_settings()
        if not settings.mlflow_enabled:
            return
        try:
            import mlflow

            with self._lock:
                mlflow.set_tracking_uri(settings.resolved_mlflow_tracking_uri)
                mlflow.set_experiment(settings.mlflow_experiment_name)
                with mlflow.start_run(run_name=f"{provider}:{model}"):
                    mlflow.log_params(
                        {"provider": provider, "model": model, "status": status}
                    )
                    mlflow.log_metrics(
                        {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                            "latency_seconds": elapsed_seconds,
                        }
                    )
                    mlflow.set_tags(
                        {
                            "component": "llm",
                            "error_type": error_type,
                            "privacy": "metadata-only",
                        }
                    )
        except Exception as exc:  # pragma: no cover - observabilidad no bloquea negocio
            if not self._warned:
                logger.warning("MLflow no disponible", error=type(exc).__name__)
                self._warned = True

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        try:
            import mlflow  # noqa: F401

            installed = True
        except ImportError:
            installed = False
        with self._lock:
            usage = [
                {
                    "provider": provider,
                    "model": model,
                    **values,
                    "avg_latency_seconds": round(
                        float(values["total_latency_seconds"])
                        / max(1, int(values["calls"])),
                        4,
                    ),
                }
                for (provider, model), values in sorted(self._usage.items())
            ]
        return {
            "enabled": settings.mlflow_enabled,
            "installed": installed,
            "tracking_uri": settings.resolved_mlflow_tracking_uri,
            "experiment": settings.mlflow_experiment_name,
            "ui_url": settings.mlflow_ui_url,
            "privacy": "Solo metadatos; no se registran prompts, respuestas ni claves.",
            "usage": usage,
        }


MLFLOW_TRACKER = MlflowLLMTracker()


class ObservedLLMAdapter:
    """Decorador transparente que mide toda generación del adaptador real."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def provider(self) -> str:
        return str(getattr(self._inner, "provider", "unknown"))

    @property
    def model_name(self) -> str:
        return str(self._inner.model_name)

    @property
    def is_configured(self) -> bool:
        return bool(self._inner.is_configured)

    def list_models(self) -> list[str]:
        return list(self._inner.list_models())

    def generate_json(self, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            response = self._inner.generate_json(**kwargs)
        except Exception as exc:
            MLFLOW_TRACKER.record(
                provider=self.provider,
                model=self.model_name,
                elapsed_seconds=time.perf_counter() - started,
                status="error",
                error_type=type(exc).__name__,
            )
            raise
        MLFLOW_TRACKER.record(
            provider=self.provider,
            model=self.model_name,
            elapsed_seconds=time.perf_counter() - started,
            prompt_tokens=int(response.prompt_tokens or 0),
            completion_tokens=int(response.completion_tokens or 0),
        )
        return response


__all__ = ["MLFLOW_TRACKER", "MlflowLLMTracker", "ObservedLLMAdapter"]
