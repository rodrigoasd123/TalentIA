"""Configuracion administrable, cifrada y compartida del runtime de IA."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken

from talentia.config import Configuracion
from talentia.shared.application.errores import ConflictoError, EntradaInvalidaError
from talentia.shared.infrastructure.base_datos import FabricaSesiones
from talentia.shared.infrastructure.modelos_orm import ConfiguracionIAModelo

MODELOS_OPENAI_GRATUITOS = (
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "o3-mini",
    "o4-mini",
)
MODELOS_OPENAI_AVANZADOS = (
    "gpt-4o",
    "gpt-4.1",
    "gpt-5",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-5.4",
    "o1",
    "o3",
)
MODELOS_GEMINI = ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro")
MODELOS_POR_PROVEEDOR = {
    "openai": frozenset((*MODELOS_OPENAI_GRATUITOS, *MODELOS_OPENAI_AVANZADOS)),
    "gemini": frozenset(MODELOS_GEMINI),
    "local": frozenset({"deterministico-local"}),
}


@dataclass(frozen=True, slots=True)
class AjustesIAPublicos:
    proveedor: str
    modelo: str
    temperatura: float
    tokens_maximos: int
    clave_configurada: bool
    estado: str
    detalle: str
    latencia_ms: float | None
    ultima_verificacion_en: datetime | None
    ultimo_exito_en: datetime | None
    version: int
    mlflow_url: str | None

    @property
    def modo_manual(self) -> bool:
        return self.proveedor == "local"


@dataclass(frozen=True, slots=True)
class AjustesIAInternos:
    proveedor: str
    modelo: str
    temperatura: float
    tokens_maximos: int
    api_key: str | None


class GestorConfiguracionIA:
    def __init__(self, fabrica: FabricaSesiones, configuracion: Configuracion) -> None:
        self._fabrica = fabrica
        clave = hashlib.sha256(configuracion.secreto_sesion.encode("utf-8")).digest()
        self._cifrador = Fernet(base64.urlsafe_b64encode(clave))
        self._mlflow_url = self._validar_mlflow_url(configuracion.mlflow_url)
        self._bloqueo = RLock()
        self._inicializar(configuracion)

    @staticmethod
    def _validar_mlflow_url(url: str) -> str | None:
        return (
            url.rstrip("/") if url.startswith(("http://127.0.0.1:", "http://localhost:")) else None
        )

    def _cifrar(self, secreto: str) -> str:
        return self._cifrador.encrypt(secreto.encode("utf-8")).decode("ascii")

    def _descifrar(self, secreto: str | None) -> str | None:
        if not secreto:
            return None
        try:
            return self._cifrador.decrypt(secreto.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as error:
            raise EntradaInvalidaError("La credencial guardada no se puede recuperar") from error

    def _inicializar(self, configuracion: Configuracion) -> None:
        proveedor = configuracion.proveedor_ia or "local"
        if proveedor not in MODELOS_POR_PROVEEDOR:
            proveedor = "local"
        modelo = configuracion.modelo_ia
        if modelo not in MODELOS_POR_PROVEEDOR[proveedor]:
            modelo = (
                "deterministico-local"
                if proveedor == "local"
                else sorted(MODELOS_POR_PROVEEDOR[proveedor])[0]
            )
        with self._fabrica.sesion() as sesion:
            if sesion.get(ConfiguracionIAModelo, "global") is not None:
                return
            openai = os.getenv("OPENAI_API_KEY", "")
            gemini = os.getenv("GEMINI_API_KEY", "")
            sesion.add(
                ConfiguracionIAModelo(
                    id="global",
                    proveedor=proveedor,
                    modelo=modelo,
                    temperatura=Decimal("0"),
                    tokens_maximos=1024,
                    clave_openai_cifrada=self._cifrar(openai) if openai else None,
                    clave_gemini_cifrada=self._cifrar(gemini) if gemini else None,
                    estado_conexion="local" if proveedor == "local" else "pendiente",
                    detalle_conexion=(
                        "Procesamiento deterministico local"
                        if proveedor == "local"
                        else "Pendiente de verificacion"
                    ),
                )
            )

    def _modelo(self) -> ConfiguracionIAModelo:
        with self._fabrica.sesion() as sesion:
            modelo = sesion.get(ConfiguracionIAModelo, "global")
            if modelo is None:
                raise RuntimeError("Configuracion de IA no inicializada")
            sesion.expunge(modelo)
            return modelo

    def obtener_publica(self) -> AjustesIAPublicos:
        modelo = self._modelo()
        cifrada = (
            modelo.clave_openai_cifrada
            if modelo.proveedor == "openai"
            else modelo.clave_gemini_cifrada
        )
        return AjustesIAPublicos(
            proveedor=modelo.proveedor,
            modelo=modelo.modelo,
            temperatura=float(modelo.temperatura),
            tokens_maximos=modelo.tokens_maximos,
            clave_configurada=bool(cifrada) if modelo.proveedor != "local" else False,
            estado=modelo.estado_conexion,
            detalle=modelo.detalle_conexion,
            latencia_ms=float(modelo.latencia_ms) if modelo.latencia_ms is not None else None,
            ultima_verificacion_en=modelo.ultima_verificacion_en,
            ultimo_exito_en=modelo.ultimo_exito_en,
            version=modelo.version,
            mlflow_url=self._mlflow_url,
        )

    def obtener_interna(self) -> AjustesIAInternos:
        modelo = self._modelo()
        cifrada = (
            modelo.clave_openai_cifrada
            if modelo.proveedor == "openai"
            else modelo.clave_gemini_cifrada
        )
        return AjustesIAInternos(
            proveedor=modelo.proveedor,
            modelo=modelo.modelo,
            temperatura=float(modelo.temperatura),
            tokens_maximos=modelo.tokens_maximos,
            api_key=self._descifrar(cifrada) if modelo.proveedor != "local" else None,
        )

    def guardar(
        self,
        *,
        proveedor: str,
        modelo: str,
        temperatura: float,
        tokens_maximos: int,
        api_key: str,
        version: int,
    ) -> AjustesIAPublicos:
        if proveedor not in MODELOS_POR_PROVEEDOR:
            raise EntradaInvalidaError("Proveedor no permitido")
        if modelo not in MODELOS_POR_PROVEEDOR[proveedor]:
            raise EntradaInvalidaError("El modelo no pertenece al proveedor seleccionado")
        if not 0 <= temperatura <= 1:
            raise EntradaInvalidaError("La temperatura debe estar entre 0 y 1")
        if not 1 <= tokens_maximos <= 16_384:
            raise EntradaInvalidaError("Los tokens maximos deben estar entre 1 y 16384")
        if api_key and len(api_key.strip()) < 8:
            raise EntradaInvalidaError("La API Key no tiene un formato valido")
        with self._bloqueo, self._fabrica.sesion() as sesion:
            actual = sesion.get(ConfiguracionIAModelo, "global")
            if actual is None or actual.version != version:
                raise ConflictoError("La configuracion fue actualizada por otra sesion")
            if api_key.strip():
                cifrada = self._cifrar(api_key.strip())
                if proveedor == "openai":
                    actual.clave_openai_cifrada = cifrada
                elif proveedor == "gemini":
                    actual.clave_gemini_cifrada = cifrada
            actual.proveedor = proveedor
            actual.modelo = modelo
            actual.temperatura = Decimal(str(temperatura))
            actual.tokens_maximos = tokens_maximos
            actual.estado_conexion = "local" if proveedor == "local" else "pendiente"
            actual.detalle_conexion = (
                "Procesamiento deterministico local"
                if proveedor == "local"
                else "Configuracion guardada; ejecute el diagnostico"
            )
            actual.latencia_ms = None
            actual.ultima_verificacion_en = None
            actual.version += 1
        return self.obtener_publica()

    def _solicitud_diagnostico(self, ajustes: AjustesIAInternos) -> Request:
        if not ajustes.api_key:
            raise EntradaInvalidaError("No existe una API Key configurada")
        if ajustes.proveedor == "openai":
            cuerpo = {
                "model": ajustes.modelo,
                "input": "Responde solamente OK.",
                "max_output_tokens": 8,
            }
            return Request(
                "https://api.openai.com/v1/responses",
                data=json.dumps(cuerpo).encode(),
                headers={
                    "Authorization": f"Bearer {ajustes.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
        cuerpo = {
            "contents": [{"parts": [{"text": "Responde solamente OK."}]}],
            "generationConfig": {"maxOutputTokens": 8, "temperature": 0},
        }
        return Request(  # noqa: S310 - URL HTTPS fija con modelo de lista permitida
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{ajustes.modelo}:generateContent"
            ),
            data=json.dumps(cuerpo).encode(),
            headers={"x-goog-api-key": ajustes.api_key, "Content-Type": "application/json"},
            method="POST",
        )

    @staticmethod
    def _detalle_error(error: BaseException) -> str:
        if isinstance(error, HTTPError):
            return {
                400: "Solicitud o modelo no admitido",
                401: "API Key invalida",
                403: "API Key sin permisos",
                404: "Modelo no disponible",
                429: "Cuota agotada",
            }.get(error.code, f"Proveedor respondio HTTP {error.code}")
        if isinstance(error, (TimeoutError, socket.timeout)):
            return "Timeout de red"
        if isinstance(error, URLError):
            return "Error de conexion de red"
        if isinstance(error, EntradaInvalidaError):
            return str(error)
        return "Error de conexion no clasificado"

    def diagnosticar(self, timeout: float = 10) -> AjustesIAPublicos:
        ajustes = self.obtener_interna()
        ahora = datetime.now(UTC)
        if ajustes.proveedor == "local":
            self._guardar_diagnostico(
                "local", "Procesamiento deterministico local", 0, ahora, ahora
            )
            return self.obtener_publica()
        inicio = time.perf_counter()
        try:
            solicitud = self._solicitud_diagnostico(ajustes)
            with urlopen(solicitud, timeout=timeout) as respuesta:  # noqa: S310
                codigo = int(respuesta.status)
                respuesta.read(4096)
            latencia = round((time.perf_counter() - inicio) * 1000, 3)
            self._guardar_diagnostico(
                "activo",
                f"Conexion valida (HTTP {codigo}); respuesta minima recibida",
                latencia,
                ahora,
                ahora,
            )
        except Exception as error:
            latencia = round((time.perf_counter() - inicio) * 1000, 3)
            self._guardar_diagnostico("error", self._detalle_error(error), latencia, ahora, None)
        return self.obtener_publica()

    def _guardar_diagnostico(
        self,
        estado: str,
        detalle: str,
        latencia_ms: float,
        verificado_en: datetime,
        exito_en: datetime | None,
    ) -> None:
        with self._bloqueo, self._fabrica.sesion() as sesion:
            actual = cast(ConfiguracionIAModelo, sesion.get(ConfiguracionIAModelo, "global"))
            actual.estado_conexion = estado
            actual.detalle_conexion = detalle[:160]
            actual.latencia_ms = Decimal(str(latencia_ms))
            actual.ultima_verificacion_en = verificado_en
            if exito_en is not None:
                actual.ultimo_exito_en = exito_en
