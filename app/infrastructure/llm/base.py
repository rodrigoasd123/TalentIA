"""Tipos comunes de los adaptadores de LLM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLMResponse:
    """Respuesta normalizada de cualquier proveedor.

    Se normaliza en el adaptador para que ni el grafo ni los nodos conozcan la
    forma concreta de la respuesta de Gemini, de OpenAI o de quien sea.
    """

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    finish_reason: str = ""
    raw: dict | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def was_truncated(self) -> bool:
        """Una respuesta cortada por límite de tokens produce JSON inválido.

        Detectarlo permite dar un mensaje útil en lugar de un error de parseo
        incomprensible.
        """
        return self.finish_reason.upper() in {"MAX_TOKENS", "LENGTH"}


__all__ = ["LLMResponse"]
