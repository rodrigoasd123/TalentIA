"""Catálogo y adaptador del gateway GenAI Lab, sin llamadas de red reales."""

from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import LLMError
from app.infrastructure.llm.model_catalog import (
    GENAI_LAB_ALL_MODELS,
    GENAI_LAB_CHAT_MODELS,
    GENAI_LAB_EMBEDDING_MODELS,
    GENAI_LAB_TRANSCRIPTION_MODELS,
    gateway_model_id,
)
from app.infrastructure.llm.openai_compatible_adapter import OpenAICompatibleAdapter


def test_catalogo_conserva_identificadores_y_separa_capacidades() -> None:
    assert "azure_ai/genailab-maas-Phi-4-reasoning" in GENAI_LAB_CHAT_MODELS
    assert "genailab-maas-gpt-5.3-codex" in GENAI_LAB_CHAT_MODELS
    assert "azure/genailab-maas-text-embedding-3-large" in GENAI_LAB_EMBEDDING_MODELS
    assert "azure/genailab-maas-whisper" in GENAI_LAB_TRANSCRIPTION_MODELS
    assert len(GENAI_LAB_ALL_MODELS) == 25
    assert gateway_model_id("azure/genailab-maas-gpt-4o") == "genailab-maas-gpt-4o"
    assert gateway_model_id("azure/genailab-maas-gpt-4.1") == (
        "azure/genailab-maas-gpt-4.1"
    )
    assert gateway_model_id("azure_ai/genailab-maas-DeepSeek-V3-0324") == (
        "genailab-maas-DeepSeek-v3-0324"
    )


def test_endpoint_acepta_url_con_o_sin_v1() -> None:
    kwargs = {"api_key": "key", "model": GENAI_LAB_CHAT_MODELS[0]}
    without_v1 = OpenAICompatibleAdapter(base_url="https://lab.example", **kwargs)
    with_v1 = OpenAICompatibleAdapter(base_url="https://lab.example/v1", **kwargs)
    expected = "https://lab.example/v1/chat/completions"
    assert without_v1._endpoint("chat/completions") == expected
    assert with_v1._endpoint("chat/completions") == expected


def test_verificacion_rechaza_nombre_de_modelo_como_url() -> None:
    adapter = OpenAICompatibleAdapter(
        api_key="key",
        base_url="genailab-maas-gpt-5.3-codex",
        model="genailab-maas-gpt-5.3-codex",
    )
    ok, message = adapter.verify_credentials()
    assert ok is False
    assert "https://" in message
    assert "nombre de un modelo" in message


def test_modelo_no_generativo_se_rechaza_antes_de_la_red() -> None:
    adapter = OpenAICompatibleAdapter(
        api_key="key",
        base_url="https://lab.example/v1",
        model=GENAI_LAB_EMBEDDING_MODELS[0],
    )
    with pytest.raises(LLMError, match="no está habilitado"):
        adapter.generate_json(system_instruction="s", user_content="u")


def test_parsea_respuesta_openai_y_sus_tokens() -> None:
    adapter = OpenAICompatibleAdapter(
        api_key="key",
        base_url="https://lab.example/v1",
        model=GENAI_LAB_CHAT_MODELS[0],
    )
    response = adapter._parse(
        {
            "model": GENAI_LAB_CHAT_MODELS[0],
            "choices": [
                {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        }
    )
    assert response.text == '{"ok":true}'
    assert response.total_tokens == 16
    assert response.finish_reason == "stop"


def test_error_no_expone_la_clave() -> None:
    secret = "lab-secret-value"
    request = httpx.Request("POST", "https://lab.example/v1/chat/completions")
    response = httpx.Response(
        401,
        request=request,
        json={"error": {"message": "una credencial fue rechazada"}},
    )
    message = OpenAICompatibleAdapter._describe_error(response)
    assert "401" in message
    assert secret not in message


@pytest.mark.parametrize(
    "model",
    [
        "azure/genailab-maas-gpt-5-mini",
        "genailab-maas-gpt-5.4",
        "genailab-maas-gpt-5.3-codex",
    ],
)
def test_familia_gpt5_usa_parametros_compatibles(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    captured: dict[str, object] = {}

    def fake_post(self, url, *, headers, json):
        captured.update(json)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    adapter = OpenAICompatibleAdapter(
        api_key="key", base_url="https://lab.example", model=model
    )
    adapter.generate_json(
        system_instruction="Devuelve un resultado.",
        user_content="Evalúa.",
        temperature=0.7,
        max_output_tokens=321,
    )

    assert captured["max_completion_tokens"] == 321
    assert "max_tokens" not in captured
    assert "temperature" not in captured
    system = captured["messages"][0]["content"]  # type: ignore[index]
    user = captured["messages"][1]["content"]  # type: ignore[index]
    assert "json" in system
    assert "json" in user
