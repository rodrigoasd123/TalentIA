"""Fábrica de adaptadores de LLM.

Un único punto donde se decide qué proveedor se instancia. El resto del sistema
solo conoce el puerto ``LLMPort``, así que añadir OpenAI o Anthropic mañana es
escribir un adaptador y una línea aquí, sin tocar el dominio ni el grafo.

La degradación al simulador es deliberada: si no hay clave configurada, el
sistema arranca y funciona en modo simulado en lugar de fallar. Un laboratorio
que no arranca sin credenciales es un laboratorio que nadie prueba.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.domain.ports import LLMPort
from app.infrastructure.llm.gemini_adapter import DEFAULT_MODEL, GeminiAdapter
from app.infrastructure.llm.mock_adapter import MockLLMAdapter
from app.infrastructure.llm.model_catalog import provider_for_model
from app.infrastructure.llm.openai_compatible_adapter import OpenAICompatibleAdapter
from app.infrastructure.observability.mlflow_tracker import ObservedLLMAdapter

logger = get_logger(__name__)

PROVIDERS = ("genai_lab", "gemini", "mock")


def build_llm(
    provider: str = "mock",
    *,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    base_url: str = "",
    timeout_seconds: int = 60,
) -> LLMPort:
    """Devuelve el adaptador correspondiente al proveedor indicado."""
    normalized = (provider or "mock").strip().lower()

    if normalized == "gemini":
        if not api_key:
            logger.warning(
                "Se solicitó Gemini sin API key; se usa el simulador. "
                "Configura la clave en el panel para obtener resultados reales."
            )
            return MockLLMAdapter()
        return ObservedLLMAdapter(
            GeminiAdapter(api_key=api_key, model=model, default_timeout=timeout_seconds)
        )

    if normalized == "genai_lab":
        if not api_key or not base_url:
            logger.warning(
                "Se solicitó GenAI Lab sin URL base o API key; se usa el simulador."
            )
            return MockLLMAdapter()
        return ObservedLLMAdapter(
            OpenAICompatibleAdapter(
                api_key=api_key,
                model=model,
                base_url=base_url,
                default_timeout=timeout_seconds,
            )
        )

    if normalized == "mock":
        return MockLLMAdapter()

    logger.warning("Proveedor desconocido; se usa el simulador", provider=normalized)
    return MockLLMAdapter()


def build_llm_from_settings(store) -> LLMPort:
    """Construye el adaptador a partir de la configuración en caliente."""
    config = store.llm_config()
    return build_llm(
        config["provider"],
        api_key=config["api_key"],
        model=config["model"],
        base_url=config["base_url"],
    )


def build_llm_for_model(store, model: str) -> LLMPort:
    """Construye el proveedor y toma la clave interna según el modelo."""
    provider = provider_for_model(model)
    legacy_key = store.get("llm.api_key", "")
    if provider == "gemini":
        api_key = store.get("llm.gemini_api_key", "")
    else:
        api_key = store.get("llm.genai_lab_api_key", "") or legacy_key
    return build_llm(
        provider,
        api_key=api_key,
        model=model,
        base_url=store.get("llm.base_url", ""),
    )


def describe_provider(llm: LLMPort) -> dict[str, object]:
    """Resumen del proveedor activo para el panel y los health checks."""
    provider = getattr(llm, "provider", "unknown")
    return {
        "provider": provider,
        "model": llm.model_name,
        "configured": llm.is_configured,
        "is_simulated": provider == "mock",
        "warning": (
            "Modo simulado: los resultados no proceden de un modelo real."
            if provider == "mock"
            else ""
        ),
    }


__all__ = [
    "PROVIDERS",
    "build_llm",
    "build_llm_for_model",
    "build_llm_from_settings",
    "describe_provider",
]
