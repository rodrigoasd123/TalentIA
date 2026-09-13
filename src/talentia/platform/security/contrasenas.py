"""Hash de contrasenas y tokens firmados usando la biblioteca estandar."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast

from talentia.shared.application.errores import NoAutorizadoError


def hash_contrasena(contrasena: str, sal: bytes | None = None) -> str:
    if len(contrasena) < 14:
        raise ValueError("La contrasena debe tener al menos 14 caracteres")
    sal_real = sal or secrets.token_bytes(16)
    derivada = hashlib.scrypt(contrasena.encode(), salt=sal_real, n=2**14, r=8, p=1, dklen=32)
    sal_codificada = base64.urlsafe_b64encode(sal_real).decode()
    derivada_codificada = base64.urlsafe_b64encode(derivada).decode()
    return f"scrypt${sal_codificada}${derivada_codificada}"


def verificar_contrasena(contrasena: str, almacenada: str) -> bool:
    try:
        algoritmo, sal_texto, _ = almacenada.split("$", 2)
        if algoritmo != "scrypt":
            return False
        candidata = hash_contrasena(contrasena, base64.urlsafe_b64decode(sal_texto))
        return hmac.compare_digest(candidata, almacenada)
    except (ValueError, TypeError):
        return False


class FirmadorSesion:
    def __init__(self, secreto: str, minutos: int = 30) -> None:
        self._secreto = secreto.encode()
        self._minutos = minutos

    def crear(self, datos: dict[str, object]) -> str:
        carga = dict(datos)
        carga["exp"] = int((datetime.now(UTC) + timedelta(minutes=self._minutos)).timestamp())
        cuerpo = base64.urlsafe_b64encode(
            json.dumps(carga, separators=(",", ":"), sort_keys=True).encode()
        ).rstrip(b"=")
        firma = hmac.new(self._secreto, cuerpo, hashlib.sha256).digest()
        return f"{cuerpo.decode()}.{base64.urlsafe_b64encode(firma).rstrip(b'=').decode()}"

    def leer(self, token: str) -> dict[str, object]:
        try:
            cuerpo_texto, firma_texto = token.split(".", 1)
            cuerpo = cuerpo_texto.encode()
            firma = base64.urlsafe_b64decode(firma_texto + "=" * (-len(firma_texto) % 4))
            esperada = hmac.new(self._secreto, cuerpo, hashlib.sha256).digest()
            if not hmac.compare_digest(firma, esperada):
                raise NoAutorizadoError("Sesion invalida")
            datos = cast(
                dict[str, object],
                json.loads(base64.urlsafe_b64decode(cuerpo_texto + "=" * (-len(cuerpo_texto) % 4))),
            )
            expiracion = datos["exp"]
            if not isinstance(expiracion, int | str):
                raise NoAutorizadoError("Sesion invalida")
            if int(expiracion) < int(datetime.now(UTC).timestamp()):
                raise NoAutorizadoError("Sesion vencida")
            return datos
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise NoAutorizadoError("Sesion invalida") from exc


def nuevo_csrf() -> str:
    return secrets.token_urlsafe(24)
