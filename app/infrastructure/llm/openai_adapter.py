"""Adaptador de OpenAI para integrar el servicio a LLMPort."""

from __future__ import annotations

import json
from typing import Any

from app.core.exceptions import LLMError, LLMNotConfigured, LLMTimeout
from app.infrastructure.llm.base import LLMResponse
from app.services.openai_service import OpenAIService, OpenAIServiceError


class OpenAIAdapter:
    """Implementa ``LLMPort`` utilizando OpenAIService."""

    provider = "openai"

    def __init__(self) -> None:
        self.service = OpenAIService()

    @property
    def model_name(self) -> str:
        return self.service.settings.openai_model

    @property
    def is_configured(self) -> bool:
        return bool(self.service.api_key)

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        if not self.is_configured:
            raise LLMNotConfigured("La API key de OpenAI no está configurada.")

        messages = [
            {
                "role": "system",
                "content": (
                    "Return only one valid json object. "
                    f"{system_instruction}"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Return the result as a valid json object. "
                    f"{user_content}"
                ),
            },
        ]
        
        try:
            result = self.service.call_model(
                messages=messages,
                feature="evaluation_llm_port",
                temperature=temperature,
                max_tokens=max_output_tokens,
                response_format={"type": "json_object"}
            )
            
            if not result.get("success"):
                raise LLMError(result.get("error_message", "Error desconocido"))
                
            return LLMResponse(
                text=result["response"],
                prompt_tokens=result["input_tokens"],
                completion_tokens=result["output_tokens"],
                model=result["model"],
                finish_reason="stop"
            )
        except OpenAIServiceError as e:
            raise LLMError(str(e)) from e

    def list_models(self) -> list[str]:
        return ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-4o", "gpt-4o-mini"]
