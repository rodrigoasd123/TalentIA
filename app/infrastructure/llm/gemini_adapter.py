"""Adaptador para la API de Gemini (Google Generative Language API).

Se habla con el servicio por HTTP directamente, en lugar de usar el SDK oficial.
Es una decisión meditada:

* El SDK de Google ha cambiado de nombre y de interfaz varias veces
  (``google-generativeai`` y luego ``google-genai``). La API REST, en cambio, es
  estable y está documentada.
* Una dependencia menos que auditar y que pueda arrastrar vulnerabilidades.
* Control total sobre timeouts, reintentos y qué se registra en los logs, que en
  un sistema que maneja datos personales no es un detalle menor.

La API key nunca se escribe en un log ni se incluye en un mensaje de error. Se
envía como cabecera ``x-goog-api-key`` en lugar de como parámetro en la URL,
porque las URLs acaban en registros de servidores intermedios.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.crypto import mask_secret
from app.core.exceptions import LLMError, LLMNotConfigured, LLMTimeout
from app.core.logging import get_logger
from app.infrastructure.llm.base import LLMResponse

logger = get_logger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"

#: Modelos que el panel ofrece cuando no se puede consultar la lista real
#: (por ejemplo, sin conexión). Sirve para que el desplegable nunca esté vacío.
FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
)

#: Umbrales de seguridad del proveedor. Se ponen al mínimo de bloqueo porque un
#: CV legítimo puede mencionar términos médicos, militares o judiciales, y que el
#: filtro del proveedor descarte la respuesta produciría una evaluación fallida
#: sin motivo real. Nuestros propios guardrails siguen aplicándose enteros.
_SAFETY_SETTINGS = [
    {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
    for c in (
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    )
]


class GeminiAdapter:
    """Implementación de ``LLMPort`` sobre la API de Gemini."""

    provider = "gemini"

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        *,
        base_url: str = BASE_URL,
        default_timeout: int = 60,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or DEFAULT_MODEL).removeprefix("models/")
        self._base_url = base_url.rstrip("/")
        self._default_timeout = default_timeout

    # ── Propiedades del puerto ───────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def masked_key(self) -> str:
        return mask_secret(self._api_key)

    # ── Generación ───────────────────────────────────────────────────────────

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        """Pide una respuesta en JSON.

        Se usa ``responseMimeType: application/json``, que hace que el modelo
        devuelva JSON sin envolverlo en un bloque de código. Aun así, el
        llamante vuelve a validar: confiar en que el proveedor cumpla siempre su
        propio contrato sería una suposición innecesaria.
        """
        if not self.is_configured:
            raise LLMNotConfigured(
                "No hay API key de Gemini configurada. "
                "Añádela en el panel de configuración de VERA."
            )

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
                "candidateCount": 1,
            },
            "safetySettings": _SAFETY_SETTINGS,
        }

        url = f"{self._base_url}/models/{self._model}:generateContent"
        timeout = timeout_seconds or self._default_timeout

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(
                f"Gemini no respondió en {timeout} segundos (modelo {self._model})"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Error de red al contactar con Gemini: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise LLMError(self._describe_error(response))

        return self._parse(response.json())

    def list_models(self) -> list[str]:
        """Modelos disponibles para esta clave.

        Se filtran los que no admiten generación de contenido y los de embeddings,
        para que el desplegable del panel solo ofrezca opciones utilizables.
        """
        if not self.is_configured:
            return list(FALLBACK_MODELS)
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(f"{self._base_url}/models", headers=self._headers())
            if response.status_code != 200:
                logger.warning(
                    "No se pudo listar modelos de Gemini",
                    status=response.status_code,
                )
                return list(FALLBACK_MODELS)
            models = [
                m["name"].removeprefix("models/")
                for m in response.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
                and "embedding" not in m.get("name", "")
            ]
            return sorted(models, reverse=True) or list(FALLBACK_MODELS)
        except httpx.HTTPError as exc:
            logger.warning("Fallo al listar modelos", error=type(exc).__name__)
            return list(FALLBACK_MODELS)

    def verify_credentials(self) -> tuple[bool, str]:
        """Comprueba que la clave funciona, sin gastar una generación completa.

        Lo usa el panel de configuración para dar una respuesta inmediata al
        guardar la clave, en lugar de que el usuario descubra el error en mitad
        de una evaluación.
        """
        if not self.is_configured:
            return False, "No se ha introducido ninguna API key."
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(f"{self._base_url}/models", headers=self._headers())
        except httpx.HTTPError as exc:
            return False, f"No se pudo conectar con Gemini: {type(exc).__name__}"

        if response.status_code == 200:
            available = self.list_models()
            if self._model not in available:
                return True, (
                    f"La clave es válida, pero el modelo «{self._model}» no aparece "
                    f"disponible. Modelos accesibles: {', '.join(available[:5])}."
                )
            return True, f"Clave válida. Modelo «{self._model}» disponible."
        if response.status_code in (401, 403):
            return False, "La API key fue rechazada por Google (401/403). Revísala."
        if response.status_code == 429:
            return False, "La clave es válida pero se alcanzó el límite de cuota (429)."
        return False, f"Respuesta inesperada de Google: HTTP {response.status_code}."

    # ── Internos ─────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        # La clave va en cabecera, nunca en la URL: las URLs se registran en
        # proxies y servidores intermedios, las cabeceras normalmente no.
        return {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": "VERA-ATS/1.0",
        }

    @staticmethod
    def _describe_error(response: httpx.Response) -> str:
        """Traduce el error del proveedor a algo accionable.

        Nunca se incluye el cuerpo completo de la respuesta: podría contener
        fragmentos del contenido enviado, que incluye datos del candidato.
        """
        try:
            detail = response.json().get("error", {})
            message = str(detail.get("message", ""))[:300]
            status = detail.get("status", "")
        except (json.JSONDecodeError, ValueError):
            message, status = "", ""

        hints = {
            400: "Petición mal formada. Revisa el modelo seleccionado.",
            401: "API key inválida o ausente.",
            403: "Acceso denegado. La clave no tiene permiso sobre este modelo.",
            404: "El modelo indicado no existe o no está disponible para esta clave.",
            429: "Se superó la cuota o el límite de peticiones por minuto.",
            500: "Error interno de Google. Reintenta en unos segundos.",
            503: "El servicio está temporalmente sobrecargado.",
        }
        hint = hints.get(response.status_code, "Error no clasificado.")
        return f"Gemini devolvió HTTP {response.status_code}. {hint} {status} {message}".strip()

    def _parse(self, data: dict[str, Any]) -> LLMResponse:
        candidates = data.get("candidates") or []
        if not candidates:
            feedback = data.get("promptFeedback", {})
            blocked = feedback.get("blockReason", "")
            raise LLMError(
                "Gemini no devolvió ninguna respuesta"
                + (f" (bloqueada por: {blocked})" if blocked else "")
            )

        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        finish_reason = str(candidate.get("finishReason", ""))

        if finish_reason.upper() == "MAX_TOKENS":
            logger.warning(
                "Respuesta truncada por límite de tokens",
                model=self._model,
                chars=len(text),
            )

        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            prompt_tokens=int(usage.get("promptTokenCount", 0)),
            completion_tokens=int(usage.get("candidatesTokenCount", 0)),
            model=self._model,
            finish_reason=finish_reason,
        )

    def __repr__(self) -> str:
        return f"GeminiAdapter(model={self._model!r}, key={self.masked_key!r})"


__all__ = ["BASE_URL", "DEFAULT_MODEL", "FALLBACK_MODELS", "GeminiAdapter"]
