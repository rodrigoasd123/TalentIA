"""Observabilidad LLM sin enviar contenido ni secretos a MLflow."""

from __future__ import annotations

from types import SimpleNamespace

from app.infrastructure.llm.base import LLMResponse
from app.infrastructure.observability import mlflow_tracker


class _LLM:
    provider = "gemini"
    model_name = "gemini-3.6-flash"
    is_configured = True

    def list_models(self) -> list[str]:
        return [self.model_name]

    def generate_json(self, **kwargs) -> LLMResponse:
        return LLMResponse(
            text='{"ok": true}',
            prompt_tokens=12,
            completion_tokens=4,
            model=self.model_name,
        )


def test_adaptador_observado_agrega_tokens_por_modelo(monkeypatch) -> None:
    monkeypatch.setattr(
        mlflow_tracker,
        "get_settings",
        lambda: SimpleNamespace(mlflow_enabled=False),
    )
    tracker = mlflow_tracker.MlflowLLMTracker()
    monkeypatch.setattr(mlflow_tracker, "MLFLOW_TRACKER", tracker)

    response = mlflow_tracker.ObservedLLMAdapter(_LLM()).generate_json(
        system_instruction="s", user_content="u"
    )

    assert response.total_tokens == 16
    row = tracker._usage[("gemini", "gemini-3.6-flash")]
    assert row["calls"] == 1
    assert row["prompt_tokens"] == 12
    assert row["completion_tokens"] == 4
    assert row["total_tokens"] == 16
