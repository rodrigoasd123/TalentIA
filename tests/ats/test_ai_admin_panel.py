"""Panel administrable de IA, observabilidad por proceso e histórico de benchmark."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai.nodes.base import FunctionNode, NodeSpec
from app.core.config import reset_settings_cache
from app.core.observability import TokenUsage
from app.infrastructure.database.models import AuditEventModel, WorkflowRunModel
from app.infrastructure.database.session import session_scope


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("TALENTIA_DATABASE_URL", f"sqlite:///{tmp_path / 'ai-admin.db'}")
    monkeypatch.setenv("TALENTIA_ENVIRONMENT", "development")
    monkeypatch.setenv("TALENTIA_MLFLOW_ENABLED", "false")
    reset_settings_cache()
    from app.infrastructure.database.session import reset_engine

    reset_engine()
    from app.api.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    reset_settings_cache()


def test_admin_agrega_proveedor_modelo_y_credencial_sin_exponerla(
    client: TestClient,
) -> None:
    provider = client.post(
        "/api/v1/config/providers",
        json={
            "provider_id": "laboratorio_externo",
            "display_name": "Laboratorio externo",
            "base_url": "https://llm.example.test",
        },
    )
    assert provider.status_code == 200
    version = provider.json()["version"]

    secret = "credencial-ficticia-no-real-123456789"
    saved = client.post(
        "/api/v1/config/providers/laboratorio_externo/credential",
        json={"credential": secret, "expected_version": version},
    )
    assert saved.status_code == 204

    model = client.post(
        "/api/v1/config/providers/laboratorio_externo/models",
        json={
            "model_id": "modelo-lab-v1",
            "display_name": "Modelo laboratorio v1",
            "capabilities": ["generation"],
            "input_price_per_million": 0.5,
            "output_price_per_million": 1.25,
        },
    )
    assert model.status_code == 200

    catalog = client.get("/api/v1/config/providers")
    assert catalog.status_code == 200
    assert secret not in catalog.text
    custom = next(
        item for item in catalog.json()["providers"] if item["id"] == "laboratorio_externo"
    )
    assert custom["credential_is_set"] is True
    assert custom["models"][0]["model_id"] == "modelo-lab-v1"

    with session_scope() as database_session:
        events = database_session.query(AuditEventModel).all()
        assert {event.action for event in events} >= {
            "ai.provider.created",
            "ai.provider.credential_updated",
            "ai.model.created",
        }
        assert secret not in repr([(event.new_state, event.event_metadata) for event in events])

    activated = client.patch(
        "/api/v1/config/settings",
        json={"values": {"llm.model": "modelo-lab-v1"}},
    )
    assert activated.status_code == 200
    assert activated.json()["provider"] == "laboratorio_externo"
    assert secret not in activated.text


@pytest.mark.parametrize(
    "url",
    ["http://example.test", "https://localhost:8000", "https://127.0.0.1:9000"],
)
def test_alta_de_proveedor_rechaza_urls_inseguras(client: TestClient, url: str) -> None:
    response = client.post(
        "/api/v1/config/providers",
        json={"provider_id": "inseguro", "display_name": "Inseguro", "base_url": url},
    )
    assert response.status_code == 422


def test_bloqueo_optimista_impide_sobrescribir_catalogo(client: TestClient) -> None:
    provider = client.post(
        "/api/v1/config/providers",
        json={
            "provider_id": "concurrente",
            "display_name": "Concurrente",
            "base_url": "https://concurrente.example.test",
        },
    ).json()
    first = client.patch(
        "/api/v1/config/providers/concurrente",
        json={"expected_version": provider["version"], "display_name": "Actualizado"},
    )
    assert first.status_code == 200
    stale = client.patch(
        "/api/v1/config/providers/concurrente",
        json={"expected_version": provider["version"], "display_name": "Pisado"},
    )
    assert stale.status_code == 422


def test_fallback_local_no_puede_deshabilitarse(client: TestClient) -> None:
    providers = client.get("/api/v1/config/providers").json()["providers"]
    fallback = next(item for item in providers if item["id"] == "mock")
    provider_response = client.patch(
        "/api/v1/config/providers/mock",
        json={"expected_version": fallback["version"], "is_enabled": False},
    )
    assert provider_response.status_code == 422

    model = next(item for item in fallback["models"] if item["model_id"] == "mock")
    model_response = client.patch(
        f"/api/v1/config/models/{model['id']}",
        json={"expected_version": model["version"], "is_enabled": False},
    )
    assert model_response.status_code == 422


def test_nodos_registran_duracion_intentos_y_delta_de_tokens() -> None:
    def consume(state):
        state["token_usage"].add(12, 4, "mock")
        return state

    node = FunctionNode(NodeSpec(name="modelo", is_deterministic=False), consume)
    state = {"token_usage": TokenUsage(), "node_runs": [], "node_sequence": []}
    result = node.execute(state)

    trace = result["node_runs"][0]
    assert trace["node"] == "modelo"
    assert trace["status"] == "completed"
    assert trace["attempts"] == 1
    assert trace["prompt_tokens"] == 12
    assert trace["completion_tokens"] == 4
    assert trace["total_tokens"] == 16


def test_panel_navega_proceso_y_nodos_sin_contenido(client: TestClient) -> None:
    with session_scope() as session:
        session.add(
            WorkflowRunModel(
                id="workflow-observable",
                application_id="application-synthetic",
                graph_name="vera_evaluation",
                agent_version="TalentIA/1",
                status="completed",
                trace_id="trace-synthetic",
                node_timings={"sanitization": 0.01},
                node_runs=[
                    {
                        "sequence": 1,
                        "node": "sanitization",
                        "status": "completed",
                        "attempts": 1,
                        "duration_seconds": 0.01,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "error_type": "",
                    }
                ],
                token_usage={
                    "prompt_tokens": 12,
                    "completion_tokens": 4,
                    "total_tokens": 16,
                },
                mlflow_run_id="mlflow-synthetic",
            )
        )

    listing = client.get("/api/v1/observability/processes")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["token_usage"]["total_tokens"] == 16

    detail = client.get("/api/v1/observability/processes/workflow-observable")
    assert detail.status_code == 200
    assert detail.json()["node_runs"][0]["node"] == "sanitization"
    assert "flowchart" in detail.json()["topology"]
    assert "ana.ramirez@example.test" not in detail.text.casefold()


def test_benchmark_se_persiste_y_no_activa_el_ganador(client: TestClient, monkeypatch) -> None:
    from app.api import main

    fake = {
        "graph": "model_benchmark",
        "version": "1.0.0",
        "suite_version": "synthetic-test-v1",
        "suite_hash": "abc123",
        "baseline_model": "mock",
        "ranking": [
            {
                "model": "mock",
                "provider": "mock",
                "quality": 1.0,
                "success_rate": 1.0,
                "errors": 0,
                "prompt_tokens": 30,
                "completion_tokens": 12,
                "total_tokens": 42,
                "p50_latency_seconds": 0.01,
                "p95_latency_seconds": 0.02,
                "estimated_cost_usd": None,
                "gate_passed": True,
                "gate_reasons": [],
                "mlflow_run_id": "",
            }
        ],
        "results": [],
    }
    monkeypatch.setattr(main, "run_model_benchmark", lambda *args, **kwargs: fake)
    before = client.get("/api/v1/config/settings").json()["model"]
    response = client.post(
        "/api/v1/benchmarks/models",
        json={"models": ["mock"], "baseline_model": "mock", "confirmed": True},
    )
    assert response.status_code == 200
    history = client.get("/api/v1/benchmarks/models")
    assert history.status_code == 200
    assert history.json()["items"][0]["ranking"][0]["total_tokens"] == 42
    assert client.get("/api/v1/config/settings").json()["model"] == before


def test_workflow_mlflow_registra_solo_metadatos(monkeypatch) -> None:
    from app.infrastructure.observability import mlflow_tracker

    monkeypatch.setattr(
        mlflow_tracker,
        "get_settings",
        lambda: SimpleNamespace(mlflow_enabled=False),
    )
    tracker = mlflow_tracker.MlflowLLMTracker()
    run = SimpleNamespace(graph_name="g", node_runs=[], token_usage={})
    assert tracker.record_workflow_trace(run, provider="mock", model="mock") == ""


def test_paneles_nuevos_exigen_autenticacion_fuera_del_laboratorio(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("TALENTIA_ENVIRONMENT", "staging")
    reset_settings_cache()
    for path in (
        "/api/v1/config/providers",
        "/api/v1/observability/processes",
        "/api/v1/benchmarks/models",
    ):
        assert client.get(path).status_code == 401
