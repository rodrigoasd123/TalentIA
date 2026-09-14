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
        METRICS.increment("talentia.llm.total_tokens", prompt_tokens + completion_tokens, **labels)
        METRICS.observe("talentia.llm.latency_seconds", elapsed_seconds, **labels)

        # Solo se informa costo cuando existe una tarifa explícitamente configurada.
        cost: float | None = None
        if model == "gpt-5.6-luna":
            cost = (prompt_tokens / 1_000_000) * 1.0 + (completion_tokens / 1_000_000) * 2.0
        elif model == "gpt-5.6-terra":
            cost = (prompt_tokens / 1_000_000) * 10.0 + (completion_tokens / 1_000_000) * 30.0
        elif model == "gemini-3.6-flash":
            cost = (prompt_tokens / 1_000_000) * 0.075 + (completion_tokens / 1_000_000) * 0.30
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
                    mlflow.log_params({"provider": provider, "model": model, "status": status})
                    metrics = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "latency_seconds": elapsed_seconds,
                    }
                    if cost is not None:
                        metrics["estimated_cost_usd"] = cost
                    mlflow.log_metrics(metrics)
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
            usage_map = {key: dict(value) for key, value in self._usage.items()}
        if installed and settings.mlflow_enabled:
            try:
                from mlflow import MlflowClient

                client = MlflowClient(tracking_uri=settings.resolved_mlflow_tracking_uri)
                experiment = client.get_experiment_by_name(settings.mlflow_experiment_name)
                if experiment is not None:
                    usage_map = {}
                    for run in client.search_runs([experiment.experiment_id]):
                        provider = run.data.params.get("provider", "unknown")
                        model = run.data.params.get("model", "unknown")
                        row = usage_map.setdefault(
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
                        row["calls"] += 1
                        row["errors"] += int(run.data.params.get("status") != "ok")
                        for metric in (
                            "prompt_tokens",
                            "completion_tokens",
                            "total_tokens",
                            "latency_seconds",
                        ):
                            target = (
                                "total_latency_seconds" if metric == "latency_seconds" else metric
                            )
                            row[target] += run.data.metrics.get(metric, 0)
            except Exception as exc:  # pragma: no cover - conserva resumen en memoria
                logger.warning(
                    "No se pudo consultar el histórico de MLflow",
                    error=type(exc).__name__,
                )
        usage = [
            {
                "provider": provider,
                "model": model,
                **values,
                "avg_latency_seconds": round(
                    float(values["total_latency_seconds"]) / max(1, int(values["calls"])),
                    4,
                ),
            }
            for (provider, model), values in sorted(usage_map.items())
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

    def record_benchmark_summary(self, summary: dict[str, Any]) -> str:
        """Guarda calidad y eficiencia agregadas sin contenido de los casos."""
        settings = get_settings()
        if not settings.mlflow_enabled:
            return ""
        try:
            import mlflow

            with self._lock:
                mlflow.set_tracking_uri(settings.resolved_mlflow_tracking_uri)
                mlflow.set_experiment("TalentIA-Benchmark")
                with mlflow.start_run(run_name=str(summary["model"])) as run:
                    mlflow.log_params(
                        {
                            "model": summary["model"],
                            "provider": summary["provider"],
                            "suite_version": summary.get("suite_version", "unknown"),
                            "suite_hash": summary.get("suite_hash", "unknown"),
                        }
                    )
                    metrics = {
                        "quality_score": summary["quality"],
                        "success_rate": summary["success_rate"],
                        "total_tokens": summary["total_tokens"],
                        "prompt_tokens": summary.get("prompt_tokens", 0),
                        "completion_tokens": summary.get("completion_tokens", 0),
                        "avg_latency_seconds": summary["avg_latency_seconds"],
                        "p95_latency_seconds": summary.get("p95_latency_seconds", 0),
                    }
                    if summary.get("estimated_cost_usd") is not None:
                        metrics["estimated_cost_usd"] = summary["estimated_cost_usd"]
                    mlflow.log_metrics(metrics)
                    mlflow.set_tag("component", "model-benchmark")
                    return str(run.info.run_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("No se pudo registrar benchmark", error=type(exc).__name__)
        return ""

    def record_workflow_trace(self, run: Any, *, provider: str, model: str) -> str:
        """Registra un workflow y sus nodos como runs padre/hijo metadata-only."""
        settings = get_settings()
        if not settings.mlflow_enabled:
            return ""
        try:
            import mlflow

            with self._lock:
                mlflow.set_tracking_uri(settings.resolved_mlflow_tracking_uri)
                mlflow.set_experiment(settings.mlflow_experiment_name)
                with mlflow.start_run(run_name=f"workflow:{run.graph_name}") as parent:
                    mlflow.log_params(
                        {
                            "workflow_run_id": run.id,
                            "trace_id": run.trace_id,
                            "graph": run.graph_name,
                            "agent_version": run.agent_version,
                            "provider": provider,
                            "model": model,
                            "status": run.status.value,
                        }
                    )
                    usage = run.token_usage or {}
                    mlflow.log_metrics(
                        {
                            "duration_seconds": run.duration_seconds,
                            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                            "completion_tokens": int(usage.get("completion_tokens", 0)),
                            "total_tokens": int(usage.get("total_tokens", 0)),
                            "node_count": len(run.node_runs),
                        }
                    )
                    mlflow.set_tags({"component": "workflow", "privacy": "metadata-only"})
                    for node in run.node_runs:
                        with mlflow.start_run(run_name=f"node:{node['node']}", nested=True):
                            mlflow.log_params(
                                {
                                    "workflow_run_id": run.id,
                                    "node": node["node"],
                                    "node_version": node.get("version", ""),
                                    "sequence": node.get("sequence", 0),
                                    "status": node.get("status", "unknown"),
                                    "attempts": node.get("attempts", 1),
                                    "deterministic": node.get("deterministic", True),
                                }
                            )
                            mlflow.log_metrics(
                                {
                                    "duration_seconds": node.get("duration_seconds", 0),
                                    "prompt_tokens": node.get("prompt_tokens", 0),
                                    "completion_tokens": node.get("completion_tokens", 0),
                                    "total_tokens": node.get("total_tokens", 0),
                                }
                            )
                            mlflow.set_tags(
                                {
                                    "component": "graph-node",
                                    "error_type": node.get("error_type", ""),
                                    "privacy": "metadata-only",
                                }
                            )
                    return str(parent.info.run_id)
        except Exception as exc:  # pragma: no cover - observabilidad no bloquea negocio
            logger.warning("No se pudo registrar traza de workflow", error=type(exc).__name__)
            return ""


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
