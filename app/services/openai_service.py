"""Servicio centralizado para interactuar con la API de OpenAI."""

import logging
import time
import uuid

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Precios por 1 millón de tokens
MODEL_PRICING = {
    "gpt-5.6-luna": {
        "input": 1.00,  # Actualizar con los precios oficiales de OpenAI
        "output": 2.00,
    },
    "gpt-5.6-terra": {
        "input": 10.00,  # Actualizar con los precios oficiales de OpenAI
        "output": 30.00,
    },
}


class OpenAIServiceError(Exception):
    pass


class OpenAIService:
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.settings = get_settings()
        self.api_key = (api_key if api_key is not None else self.settings.openai_api_key).strip()
        self.model = model or self.settings.openai_model

        if not self.api_key:
            logger.warning("OPENAI_API_KEY no está configurada.")

        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def get_langchain_model(self, task: str = None, model: str = None, temperature: float = None):
        """Inicializa una instancia de ChatOpenAI para LangChain."""
        from app.services.ai_model_router import get_model_for_task

        if not model:
            model = get_model_for_task(task) if task else self.model

        temp = temperature if temperature is not None else self.settings.openai_temperature

        return ChatOpenAI(
            model=model,
            temperature=temp,
            api_key=self.api_key,
            max_retries=self.settings.llm_max_retries,
        )

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
        cost_input = (input_tokens / 1_000_000) * pricing["input"]
        cost_output = (output_tokens / 1_000_000) * pricing["output"]
        return cost_input + cost_output

    def _save_usage_log(self, data: dict):
        """Guarda la métrica de consumo en la base de datos."""
        try:
            from app.infrastructure.database.models import AIUsageLogModel
            from app.infrastructure.database.session import session_scope

            with session_scope() as session:
                log = AIUsageLogModel(
                    id=uuid.uuid4().hex,
                    provider="openai",
                    model=data.get("model", ""),
                    feature=data.get("feature", "general"),
                    input_tokens=data.get("input_tokens", 0),
                    output_tokens=data.get("output_tokens", 0),
                    total_tokens=data.get("total_tokens", 0),
                    estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
                    latency_ms=data.get("latency_ms", 0),
                    success=data.get("success", True),
                    error_message=data.get("error_message", ""),
                )
                session.add(log)
                session.commit()
        except Exception as e:
            logger.error(f"No se pudo guardar el log de uso de IA: {e}")

    def call_model(
        self,
        messages: list[dict[str, str]],
        model: str = None,
        feature: str = "general",
        temperature: float = None,
        max_tokens: int = None,
        response_format: dict = None,
    ) -> dict:
        """Llama al modelo de OpenAI y realiza seguimiento de consumo con reintentos."""

        if not model:
            model = self.model

        if temperature is None:
            temperature = self.settings.openai_temperature

        if max_tokens is None:
            max_tokens = self.settings.openai_max_output_tokens

        start_time = time.time()
        if self.client is None:
            raise OpenAIServiceError("La API key de OpenAI no está configurada.")
        retries = 0
        max_retries = self.settings.llm_max_retries

        # Exponential backoff base delay
        delay = 1.0

        while retries <= max_retries:
            try:
                # Models gpt-5.6-luna and gpt-5.6-terra do not support temperature changes (they only accept 1)
                # Or we can just omit the temperature parameter if it's one of these models.
                kwargs = {"model": model, "messages": messages, "max_completion_tokens": max_tokens}
                if model not in ("gpt-5.6-luna", "gpt-5.6-terra"):
                    kwargs["temperature"] = temperature

                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)
                latency = int((time.time() - start_time) * 1000)

                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens

                cost = self._calculate_cost(model, input_tokens, output_tokens)

                self._save_usage_log(
                    {
                        "model": model,
                        "feature": feature,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "estimated_cost_usd": cost,
                        "latency_ms": latency,
                        "success": True,
                    }
                )

                return {
                    "success": True,
                    "response": response.choices[0].message.content,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": cost,
                    "latency_ms": latency,
                }

            except AuthenticationError as e:
                # No reintentar
                self._save_usage_log(
                    {
                        "model": model,
                        "feature": feature,
                        "success": False,
                        "error_message": "API key inválida o ausente.",
                        "latency_ms": int((time.time() - start_time) * 1000),
                    }
                )
                raise OpenAIServiceError("API key de OpenAI es inválida o ausente.") from e

            except RateLimitError as e:
                error_msg = str(e).lower()
                if "quota" in error_msg or "billing" in error_msg or "balance" in error_msg:
                    # Saldo agotado. No reintentar.
                    self._save_usage_log(
                        {
                            "model": model,
                            "feature": feature,
                            "success": False,
                            "error_message": "No hay saldo disponible. Revisa Billing en platform.openai.com.",
                            "latency_ms": int((time.time() - start_time) * 1000),
                        }
                    )
                    raise OpenAIServiceError(
                        "No hay saldo disponible en la cuenta API de OpenAI. Revisa Billing en platform.openai.com."
                    ) from e

                if retries == max_retries:
                    self._save_usage_log(
                        {
                            "model": model,
                            "feature": feature,
                            "success": False,
                            "error_message": f"Rate limit: {e}",
                            "latency_ms": int((time.time() - start_time) * 1000),
                        }
                    )
                    raise OpenAIServiceError(f"Se alcanzó el límite de peticiones: {e}") from e

            except (APIConnectionError, APIError) as e:
                if retries == max_retries:
                    self._save_usage_log(
                        {
                            "model": model,
                            "feature": feature,
                            "success": False,
                            "error_message": str(e),
                            "latency_ms": int((time.time() - start_time) * 1000),
                        }
                    )
                    raise OpenAIServiceError(f"Error en la llamada a OpenAI: {e}") from e

            # Incrementar reintentos y esperar
            retries += 1
            time.sleep(delay)
            delay *= 2

        return {"success": False, "error_message": "No se pudo completar la llamada."}
