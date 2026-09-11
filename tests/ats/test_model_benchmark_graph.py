"""Topología y ranking reproducible del benchmark de modelos."""

from __future__ import annotations

from app.ai.graphs import model_benchmark_graph as benchmark
from app.infrastructure.llm.base import LLMResponse


class _FakeLLM:
    def __init__(self, model: str) -> None:
        self.model = model

    def generate_json(self, **kwargs):
        prompt = kwargs["user_content"]
        if "17 * 6" in prompt:
            text = '{"answer":102}'
        elif "Ana" in prompt:
            text = '{"name":"Ana","years":8}'
        else:
            text = '{"status":"ok"}'
        return LLMResponse(text=text, prompt_tokens=10, completion_tokens=5, model=self.model)


def test_benchmark_langgraph_tiene_ocho_nodos(monkeypatch) -> None:
    monkeypatch.setattr(
        benchmark, "build_llm_for_model", lambda store, model: _FakeLLM(model)
    )
    monkeypatch.setattr(
        benchmark.MLFLOW_TRACKER, "record_benchmark_summary", lambda summary: None
    )
    engine = benchmark.build_model_benchmark_graph(prefer_langgraph=True)
    result = engine.invoke(
        {"store": object(), "models": ["gemini-3.6-flash"], "cases": list(benchmark.DEFAULT_CASES)}
    )
    assert len(engine.definition.nodes) == 8
    assert result["ranking"][0]["quality"] == 1.0
    assert result["ranking"][0]["total_tokens"] == 45
