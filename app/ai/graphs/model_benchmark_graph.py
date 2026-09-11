"""LangGraph reproducible para comparar modelos con casos sintéticos idénticos."""

from __future__ import annotations

import json
import time
from typing import Any

from app.ai.graphs.runner import END, GraphDefinition, GraphEngine, build_engine
from app.ai.nodes.base import FunctionNode, NodeSpec
from app.infrastructure.llm.factory import build_llm_for_model
from app.infrastructure.llm.model_catalog import provider_for_model
from app.infrastructure.observability.mlflow_tracker import MLFLOW_TRACKER

GRAPH_NAME = "model_benchmark"
GRAPH_VERSION = "1.0.0"

DEFAULT_CASES = (
    {"id": "arithmetic", "prompt": "Calcula 17 * 6.", "expected": {"answer": 102}},
    {
        "id": "extraction",
        "prompt": "Extrae nombre y años de: Ana tiene 8 años de experiencia.",
        "expected": {"name": "Ana", "years": 8},
    },
    {
        "id": "instruction",
        "prompt": "Devuelve el estado solicitado.",
        "expected": {"status": "ok"},
    },
)


def _node(name: str, description: str, fn) -> FunctionNode:
    return FunctionNode(
        NodeSpec(name=name, reads=frozenset(), writes=frozenset(), description=description),
        fn,
    )


def _initialize(state: dict[str, Any]) -> dict[str, Any]:
    state.update(model_index=-1, case_index=-1, results=[], ranking=[])
    return state


def _select_model(state: dict[str, Any]) -> dict[str, Any]:
    state["model_index"] += 1
    state["case_index"] = -1
    state["model"] = state["models"][state["model_index"]]
    return state


def _select_case(state: dict[str, Any]) -> dict[str, Any]:
    state["case_index"] += 1
    state["case"] = state["cases"][state["case_index"]]
    return state


def _invoke(state: dict[str, Any]) -> dict[str, Any]:
    case = state["case"]
    started = time.perf_counter()
    try:
        llm = build_llm_for_model(state["store"], state["model"])
        response = llm.generate_json(
            system_instruction="Responde solo con un objeto JSON válido.",
            user_content=case["prompt"],
            temperature=0.0,
            max_output_tokens=256,
            timeout_seconds=60,
        )
        state["observation"] = {
            "text": response.text,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
            "latency_seconds": time.perf_counter() - started,
            "error": "",
        }
    except Exception as exc:
        state["observation"] = {
            "text": "", "prompt_tokens": 0, "completion_tokens": 0,
            "total_tokens": 0, "latency_seconds": time.perf_counter() - started,
            "error": type(exc).__name__,
        }
    return state


def _validate(state: dict[str, Any]) -> dict[str, Any]:
    observation = state["observation"]
    valid, quality = False, 0.0
    try:
        text = observation["text"].strip()
        payload = json.loads(text[text.find("{") : text.rfind("}") + 1])
        expected = state["case"]["expected"]
        valid = isinstance(payload, dict)
        quality = sum(payload.get(k) == v for k, v in expected.items()) / len(expected)
    except (ValueError, json.JSONDecodeError):
        pass
    observation.update(json_valid=valid, quality=round(quality, 4))
    return state


def _record(state: dict[str, Any]) -> dict[str, Any]:
    state["results"].append(
        {"model": state["model"], "case": state["case"]["id"], **state["observation"]}
    )
    return state


def _aggregate(state: dict[str, Any]) -> dict[str, Any]:
    rows = [r for r in state["results"] if r["model"] == state["model"]]
    summary = {
        "model": state["model"],
        "provider": provider_for_model(state["model"]),
        "quality": round(sum(r["quality"] for r in rows) / len(rows), 4),
        "success_rate": round(sum(not r["error"] for r in rows) / len(rows), 4),
        "total_tokens": sum(r["total_tokens"] for r in rows),
        "avg_latency_seconds": round(
            sum(r["latency_seconds"] for r in rows) / len(rows), 4
        ),
    }
    state.setdefault("summaries", []).append(summary)
    MLFLOW_TRACKER.record_benchmark_summary(summary)
    return state


def _rank(state: dict[str, Any]) -> dict[str, Any]:
    state["ranking"] = sorted(
        state["summaries"],
        key=lambda row: (row["quality"], row["success_rate"], -row["total_tokens"]),
        reverse=True,
    )
    return state


def _more_cases(state: dict[str, Any]) -> str:
    return "more" if state["case_index"] + 1 < len(state["cases"]) else "done"


def _more_models(state: dict[str, Any]) -> str:
    return "more" if state["model_index"] + 1 < len(state["models"]) else "done"


def build_model_benchmark_graph(*, prefer_langgraph: bool = True) -> GraphEngine:
    graph = GraphDefinition(name=GRAPH_NAME, max_steps=1000)
    for name, description, fn in (
        ("initialize_benchmark", "Prepara suite y acumuladores", _initialize),
        ("select_model", "Selecciona el siguiente modelo", _select_model),
        ("select_case", "Selecciona un caso idéntico", _select_case),
        ("invoke_model", "Ejecuta el modelo con clave interna", _invoke),
        ("validate_output", "Valida JSON y exactitud", _validate),
        ("record_result", "Registra tokens, error y calidad", _record),
        ("aggregate_model", "Agrega métricas del modelo", _aggregate),
        ("rank_models", "Ordena por calidad, éxito y eficiencia", _rank),
    ):
        graph.add_node(_node(name, description, fn))
    graph.set_entry_point("initialize_benchmark")
    graph.add_edge("initialize_benchmark", "select_model")
    graph.add_edge("select_model", "select_case")
    graph.add_edge("select_case", "invoke_model")
    graph.add_edge("invoke_model", "validate_output")
    graph.add_edge("validate_output", "record_result")
    graph.add_conditional_edges(
        "record_result", _more_cases, {"more": "select_case", "done": "aggregate_model"}
    )
    graph.add_conditional_edges(
        "aggregate_model", _more_models, {"more": "select_model", "done": "rank_models"}
    )
    graph.add_edge("rank_models", END)
    return build_engine(graph, prefer_langgraph=prefer_langgraph)


def run_model_benchmark(store: Any, models: list[str]) -> dict[str, Any]:
    engine = build_model_benchmark_graph()
    result = engine.invoke({"store": store, "models": models, "cases": list(DEFAULT_CASES)})
    return {"graph": GRAPH_NAME, "version": GRAPH_VERSION, "ranking": result["ranking"]}


__all__ = [
    "DEFAULT_CASES",
    "GRAPH_NAME",
    "GRAPH_VERSION",
    "build_model_benchmark_graph",
    "run_model_benchmark",
]
