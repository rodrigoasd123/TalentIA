"""Adaptador para el gateway OpenAI-compatible de GenAI Lab."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.crypto import mask_secret
from app.core.exceptions import LLMError, LLMNotConfigured, LLMTimeout
from app.infrastructure.llm.base import LLMResponse
from app.infrastructure.llm.model_catalog import GENAI_LAB_CHAT_MODELS, gateway_model_id

DEFAULT_GENAI_LAB_BASE_URL = "https://genailab.tcs.in"


class OpenAICompatibleAdapter:
    """Implementa ``LLMPort`` contra ``/v1/chat/completions``.

    El gateway decide el proveedor real a partir del identificador del modelo;
    por eso los nombres ``azure/...``, ``azure_ai/...`` y ``gemini-...`` deben
    llegar sin transformaciones.
    """

    provider = "genai_lab"

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = GENAI_LAB_CHAT_MODELS[0],
        base_url: str = DEFAULT_GENAI_LAB_BASE_URL,
        default_timeout: int = 90,
        verify_ssl: bool | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or GENAI_LAB_CHAT_MODELS[0]).strip()
        self._base_url = (base_url or DEFAULT_GENAI_LAB_BASE_URL).strip().rstrip("/")
        self._default_timeout = default_timeout
        self._verify_ssl = (
            verify_ssl
            if verify_ssl is not None
            else urlparse(self._base_url).hostname != "genailab.tcs.in"
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._valid_base_url())

    @property
    def masked_key(self) -> str:
        return mask_secret(self._api_key)

    def _endpoint(self, resource: str) -> str:
        prefix = self._base_url if self._base_url.endswith("/v1") else f"{self._base_url}/v1"
        return f"{prefix}/{resource.lstrip('/')}"

    def _valid_base_url(self) -> bool:
        parsed = urlparse(self._base_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TalentIA/1.0",
        }

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
            raise LLMNotConfigured(
                "Falta una API key o la URL base de GenAI Lab no es válida. "
                "La URL debe comenzar por https:// (o http:// para un gateway local)."
            )
        if self._model not in GENAI_LAB_CHAT_MODELS:
            raise LLMError(
                f"El modelo «{self._model}» no está habilitado para generación de texto."
            )

        routed_model = gateway_model_id(self._model)
        payload: dict[str, Any] = {
            "model": routed_model,
            "messages": [
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
            ],
            "response_format": {"type": "json_object"},
        }
        # El gateway enruta GPT-5 a la API Responses de Azure. Esa familia
        # rechaza ``max_tokens`` y temperaturas personalizadas, aunque exponga
        # el endpoint compatible de chat.
        if "gpt-5" in routed_model.lower():
            payload["max_completion_tokens"] = max_output_tokens
        else:
            payload["temperature"] = temperature
            payload["max_tokens"] = max_output_tokens
        timeout = timeout_seconds or self._default_timeout
        try:
            with httpx.Client(
                timeout=timeout, verify=self._verify_ssl, trust_env=False
            ) as client:
                response = client.post(
                    self._endpoint("chat/completions"),
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeout(
                f"GenAI Lab no respondió en {timeout} segundos (modelo {self._model})"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                f"Error de red al contactar con GenAI Lab: {type(exc).__name__}"
            ) from exc

        if response.status_code != 200:
            raise LLMError(self._describe_error(response))
        return self._parse(response.json())

    def list_models(self) -> list[str]:
        """Devuelve el catálogo permitido, intersectado con el gateway si responde."""
        if not self.is_configured:
            return list(GENAI_LAB_CHAT_MODELS)
        try:
            with httpx.Client(
                timeout=20, verify=self._verify_ssl, trust_env=False
            ) as client:
                response = client.get(self._endpoint("models"), headers=self._headers())
            if response.status_code != 200:
                return list(GENAI_LAB_CHAT_MODELS)
            available = {
                str(item.get("id", "")) for item in response.json().get("data", [])
            }
            selected = [
                model
                for model in GENAI_LAB_CHAT_MODELS
                if model in available or gateway_model_id(model) in available
            ]
            return selected or list(GENAI_LAB_CHAT_MODELS)
        except (httpx.HTTPError, ValueError, TypeError):
            return list(GENAI_LAB_CHAT_MODELS)

    def verify_credentials(self) -> tuple[bool, str]:
        if not self._valid_base_url():
            return False, (
                "La URL base del gateway no es válida. Debe ser una dirección completa "
                "que empiece por https:// (o http:// para un gateway local), no el "
                "nombre de un modelo."
            )
        if not self._api_key:
            return False, "No se ha introducido ninguna API key."
        try:
            with httpx.Client(
                timeout=20, verify=self._verify_ssl, trust_env=False
            ) as client:
                response = client.get(self._endpoint("models"), headers=self._headers())
        except httpx.HTTPError as exc:
            return False, f"No se pudo conectar con GenAI Lab: {type(exc).__name__}"
        if response.status_code == 200:
            return True, "Conexión válida con el gateway de GenAI Lab."
        if response.status_code in (401, 403):
            return False, "La API key fue rechazada por GenAI Lab (401/403)."
        return False, f"GenAI Lab respondió HTTP {response.status_code} al verificar la clave."

    @staticmethod
    def _describe_error(response: httpx.Response) -> str:
        try:
            detail = response.json().get("error", {})
            message = str(
                detail.get("message", detail) if isinstance(detail, dict) else detail
            )[:300]
        except (json.JSONDecodeError, ValueError):
            message = ""
        hints = {
            400: "Petición o parámetros no admitidos por el modelo.",
            401: "API key inválida o ausente.",
            403: "La clave no tiene permiso sobre este modelo.",
            404: "Revisa la URL base y el identificador del modelo.",
            429: "Se alcanzó la cuota o el límite de peticiones.",
            500: "Error interno del gateway.",
            503: "El servicio está temporalmente sobrecargado.",
        }
        hint = hints.get(response.status_code, "Error no clasificado.")
        return f"GenAI Lab devolvió HTTP {response.status_code}. {hint} {message}".strip()

    def _parse(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("GenAI Lab no devolvió ninguna respuesta.")
        choice = choices[0]
        content = choice.get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
            )
        usage = data.get("usage") or {}
        return LLMResponse(
            text=str(content),
            prompt_tokens=int(
                usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
            ),
            completion_tokens=int(
                usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
            ),
            model=str(data.get("model") or self._model),
            finish_reason=str(choice.get("finish_reason", "")),
        )


__all__ = ["DEFAULT_GENAI_LAB_BASE_URL", "OpenAICompatibleAdapter"]
