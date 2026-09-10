"""Cifrado de secretos en reposo.

Las API keys y los tokens OAuth que el usuario introduce en el panel se guardan
en base de datos. Guardarlos en texto plano convertiría un volcado accidental de
la base de datos en una fuga de credenciales, así que se cifran con Fernet
(AES-128-CBC + HMAC-SHA256) usando una clave derivada de ``VERA_SECRET_KEY``
mediante HKDF.

La clave maestra vive únicamente en el entorno. Si se pierde, los secretos
cifrados son irrecuperables y hay que volver a introducirlos: eso es
intencionado, no un defecto.
"""

from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_SECRET_PREFIX = "enc:v1:"


def _derive_key(master: str, purpose: str) -> bytes:
    """Deriva una clave Fernet de 32 bytes para un propósito concreto.

    Usamos ``purpose`` como *info* de HKDF para que un mismo secreto maestro
    produzca claves distintas por dominio de uso. Así, comprometer el material
    de un propósito no compromete el resto.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"vera-ats-kdf-salt-v1",
        info=purpose.encode("utf-8"),
    )
    return base64.urlsafe_b64encode(hkdf.derive(master.encode("utf-8")))


@lru_cache(maxsize=8)
def _fernet(purpose: str) -> Fernet:
    master = get_settings().resolved_secret_key()
    return Fernet(_derive_key(master, purpose))


class SecretCipher:
    """Cifra y descifra cadenas cortas asociadas a un propósito."""

    def __init__(self, purpose: str = "runtime-settings") -> None:
        self._purpose = purpose

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        token = _fernet(self._purpose).encrypt(plaintext.encode("utf-8"))
        return _SECRET_PREFIX + token.decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        if not ciphertext.startswith(_SECRET_PREFIX):
            # Valor heredado sin cifrar. Lo devolvemos tal cual para no romper,
            # pero el llamante debería regrabarlo para que quede cifrado.
            return ciphertext
        raw = ciphertext[len(_SECRET_PREFIX) :].encode("ascii")
        try:
            return _fernet(self._purpose).decrypt(raw).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError(
                "No se pudo descifrar el secreto. ¿Cambió VERA_SECRET_KEY? "
                "Vuelve a introducir la credencial en el panel de configuración."
            ) from exc

    @staticmethod
    def is_encrypted(value: str) -> bool:
        return value.startswith(_SECRET_PREFIX)


class SecretDecryptionError(RuntimeError):
    """La clave maestra no corresponde con el secreto almacenado."""


def mask_secret(value: str, visible: int = 4) -> str:
    """Representación segura para mostrar en pantalla o registrar en logs.

    Nunca devuelve el valor completo. Un secreto corto se enmascara por entero.
    """
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "•" * 8
    return f"{value[:visible]}{'•' * 8}{value[-visible:]}"


def reset_cipher_cache() -> None:
    """Solo para tests: limpia las claves derivadas cacheadas."""
    _fernet.cache_clear()


__all__ = ["SecretCipher", "SecretDecryptionError", "mask_secret", "reset_cipher_cache"]
