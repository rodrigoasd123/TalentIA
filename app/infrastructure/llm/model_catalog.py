"""Catálogo de modelos habilitados en el laboratorio GenAI Lab.

Los identificadores se conservan literalmente porque el gateway los usa para
enrutar la petición.  No todos sirven para el puerto de chat de TalentIA:
embeddings y transcripción se muestran como capacidades disponibles, pero no se
ofrecen como modelo de evaluación.
"""

from __future__ import annotations

GENAI_LAB_CHAT_MODELS: tuple[str, ...] = (
    "azure_ai/genailab-maas-Llama-4-Maverick-17B-128E-Instruct-FP8",
    "azure_ai/genailab-maas-Phi-4-reasoning",
    "azure/genailab-maas-gpt-4.1",
    "azure/genailab-maas-gpt-4.1-mini",
    "azure/genailab-maas-gpt-4.1-nano",
    "azure/genailab-maas-gpt-4o-mini",
    "azure/genailab-maas-gpt-5-mini",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "genailab-maas-gpt-35-turbo",
    "genailab-maas-gpt-4o",
    "genailab-maas-gpt-5.0",
    "genailab-maas-gpt-5.1",
    "genailab-maas-gpt-5.2",
    "genailab-maas-gpt-5.4",
    "genailab-maas-gpt-5.4-mini",
    "genailab-maas-gpt-5.4-nano",
    "genailab-maas-gpt-5.2-codex",
    "genailab-maas-gpt-5.3-codex",
)

GENAI_LAB_EMBEDDING_MODELS: tuple[str, ...] = (
    "azure/genailab-maas-text-embedding-3-large",
)

GENAI_LAB_TRANSCRIPTION_MODELS: tuple[str, ...] = (
    "azure/genailab-maas-whisper",
    "azure/gpt-realtime-whisper",
)

GENAI_LAB_ALL_MODELS = (
    GENAI_LAB_CHAT_MODELS
    + GENAI_LAB_EMBEDDING_MODELS
    + GENAI_LAB_TRANSCRIPTION_MODELS
)


def gateway_model_id(model: str) -> str:
    """Traduce aliases antiguos sin alterar identificadores vigentes."""
    aliases = {
        "azure/genailab-maas-gpt-35-turbo": "genailab-maas-gpt-35-turbo",
        "azure/genailab-maas-gpt-4o": "genailab-maas-gpt-4o",
        "azure_ai/genailab-maas-DeepSeek-V3-0324": (
            "genailab-maas-DeepSeek-v3-0324"
        ),
    }
    return aliases.get(model, model)

__all__ = [
    "GENAI_LAB_ALL_MODELS",
    "GENAI_LAB_CHAT_MODELS",
    "GENAI_LAB_EMBEDDING_MODELS",
    "GENAI_LAB_TRANSCRIPTION_MODELS",
    "gateway_model_id",
]
