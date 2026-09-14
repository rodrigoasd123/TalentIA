"""Cliente HTTP minimo para sugerencias LLM estructuradas y medibles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from talentia.ai.guardrails.privacidad import delimitar_documento
from talentia.platform.configuracion_ia import GestorConfiguracionIA


class ProveedorLLMError(RuntimeError):
    """Fallo sanitizado del proveedor; nunca incluye secretos ni contenido."""


@dataclass(frozen=True, slots=True)
class RespuestaLLM:
    proveedor: str
    modelo: str
    requisitos: tuple[dict[str, object], ...]
    prompt_tokens: int
    completion_tokens: int


class ClienteLLM:
    def __init__(self, gestor: GestorConfiguracionIA, timeout: float = 60) -> None:
        self._gestor = gestor
        self._timeout = timeout

    @staticmethod
    def _prompt(texto: str, requisitos: tuple[tuple[str, str], ...]) -> str:
        lista = json.dumps(
            [{"codigo": codigo, "descripcion": descripcion} for codigo, descripcion in requisitos],
            ensure_ascii=True,
        )
        return (
            "Analiza solo evidencia explicita. No decidas contratacion. "
            "Devuelve JSON estricto con la forma "
            '{"requisitos":[{"codigo":"...","veredicto":"coincide|sin_evidencia|'
            'revision_manual","evidencia":"cita literal breve o vacio"}]}. '
            f"Requisitos: {lista}\n{delimitar_documento(texto)}"
        )

    @staticmethod
    def _texto_openai(datos: dict[str, object]) -> str:
        directo = datos.get("output_text")
        if isinstance(directo, str):
            return directo
        for item in cast(list[dict[str, object]], datos.get("output", [])):
            for contenido in cast(list[dict[str, object]], item.get("content", [])):
                texto = contenido.get("text")
                if isinstance(texto, str):
                    return texto
        raise ProveedorLLMError("respuesta_estructurada_invalida")

    @staticmethod
    def _texto_gemini(datos: dict[str, object]) -> str:
        try:
            candidatos = cast(list[dict[str, object]], datos["candidates"])
            contenido = cast(dict[str, object], candidatos[0]["content"])
            partes = cast(list[dict[str, object]], contenido["parts"])
            return str(partes[0]["text"])
        except (KeyError, IndexError, TypeError) as error:
            raise ProveedorLLMError("respuesta_estructurada_invalida") from error

    @staticmethod
    def _json(texto: str) -> dict[str, object]:
        try:
            resultado = json.loads(texto.strip())
        except json.JSONDecodeError as error:
            raise ProveedorLLMError("respuesta_json_invalida") from error
        if not isinstance(resultado, dict) or not isinstance(resultado.get("requisitos"), list):
            raise ProveedorLLMError("respuesta_json_invalida")
        return cast(dict[str, object], resultado)

    @staticmethod
    def _entero(valor: object) -> int:
        return int(valor) if isinstance(valor, int | str) else 0

    def evaluar(
        self, texto_sanitizado: str, requisitos: tuple[tuple[str, str], ...]
    ) -> RespuestaLLM | None:
        ajustes = self._gestor.obtener_interna()
        if ajustes.proveedor == "local":
            return None
        if not ajustes.api_key:
            raise ProveedorLLMError("credencial_no_configurada")
        prompt = self._prompt(texto_sanitizado, requisitos)
        if ajustes.proveedor == "openai":
            cuerpo = {
                "model": ajustes.modelo,
                "input": prompt,
                "max_output_tokens": ajustes.tokens_maximos,
            }
            solicitud = Request(
                "https://api.openai.com/v1/responses",
                data=json.dumps(cuerpo).encode(),
                headers={
                    "Authorization": f"Bearer {ajustes.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
        else:
            cuerpo = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": ajustes.tokens_maximos,
                    "responseMimeType": "application/json",
                },
            }
            solicitud = Request(  # noqa: S310 - URL HTTPS fija con modelo de lista permitida
                (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{ajustes.modelo}:generateContent"
                ),
                data=json.dumps(cuerpo).encode(),
                headers={"x-goog-api-key": ajustes.api_key, "Content-Type": "application/json"},
                method="POST",
            )
        try:
            with urlopen(solicitud, timeout=self._timeout) as respuesta:  # noqa: S310
                datos = cast(dict[str, object], json.loads(respuesta.read(2_000_000)))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ProveedorLLMError("proveedor_no_disponible") from error
        if ajustes.proveedor == "openai":
            texto = self._texto_openai(datos)
            uso = cast(dict[str, object], datos.get("usage", {}))
            entrada = self._entero(uso.get("input_tokens", 0))
            salida = self._entero(uso.get("output_tokens", 0))
        else:
            texto = self._texto_gemini(datos)
            uso = cast(dict[str, object], datos.get("usageMetadata", {}))
            entrada = self._entero(uso.get("promptTokenCount", 0))
            salida = self._entero(uso.get("candidatesTokenCount", 0))
        contenido = self._json(texto)
        requisitos_sugeridos = tuple(
            item for item in cast(list[object], contenido["requisitos"]) if isinstance(item, dict)
        )
        return RespuestaLLM(
            ajustes.proveedor,
            ajustes.modelo,
            requisitos_sugeridos,
            max(0, entrada),
            max(0, salida),
        )
