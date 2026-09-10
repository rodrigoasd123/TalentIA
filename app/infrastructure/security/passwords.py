"""Hashing de contraseñas con Argon2id.

Argon2id ganó la competición de hashing de contraseñas y es la recomendación
actual: resiste tanto ataques con GPU como con hardware dedicado, porque su coste
es de memoria y no solo de cómputo. Bcrypt sigue siendo aceptable; SHA-256 a secas
no lo es, por rápido.

Dos detalles que importan más de lo que parecen:

* **``needs_rehash``** permite subir los parámetros de coste con el tiempo sin
  invalidar las contraseñas existentes: se rehashea al siguiente inicio de sesión
  correcto, de forma transparente.
* **``dummy_verify``** hace que comprobar un usuario inexistente cueste lo mismo
  que comprobar uno real. Sin eso, medir el tiempo de respuesta permite enumerar
  qué correos están registrados.
"""

from __future__ import annotations

import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.logging import get_logger

logger = get_logger(__name__)

#: Parámetros de coste. Son un compromiso entre seguridad y latencia de login;
#: conviene revisarlos si el hardware del despliegue cambia sustancialmente.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

#: Hash de referencia para igualar tiempos ante usuarios inexistentes.
_DUMMY_HASH = _hasher.hash("contraseña-de-referencia-para-igualar-tiempos")

MIN_PASSWORD_LENGTH = 12

#: Contraseñas triviales que se rechazan de entrada. La lista es corta a
#: propósito: no sustituye a una comprobación contra filtraciones conocidas, solo
#: evita lo más evidente.
_WEAK_PASSWORDS = frozenset(
    {
        "password", "contraseña", "12345678", "123456789", "1234567890",
        "qwertyuiop", "administrador", "administrator", "bienvenido",
        "welcome123", "password123", "contraseña123", "iloveyou",
    }
)


class PasswordPolicyError(ValueError):
    """La contraseña no cumple la política mínima."""


def validate_password(password: str) -> None:
    """Comprueba la política. Lanza con un mensaje accionable si no se cumple."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
        )
    if password.lower() in _WEAK_PASSWORDS:
        raise PasswordPolicyError("Esa contraseña es demasiado común")
    variedad = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if variedad < 3:
        raise PasswordPolicyError(
            "La contraseña debe combinar al menos tres de estos grupos: "
            "minúsculas, mayúsculas, dígitos y símbolos"
        )


def hash_password(password: str, *, validate: bool = True) -> str:
    if validate:
        validate_password(password)
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una contraseña en tiempo aproximadamente constante.

    Un hash ausente o corrupto también consume el tiempo de una verificación
    real, para no revelar por latencia el estado de la cuenta.
    """
    if not password_hash:
        _dummy_verify()
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHashError):
        logger.warning("Hash de contraseña con formato inválido")
        return False


def _dummy_verify() -> None:
    try:
        _hasher.verify(_DUMMY_HASH, "cualquier-cosa")
    except (VerifyMismatchError, VerificationError):
        pass


def dummy_verify() -> None:
    """Consume el tiempo de una verificación sin comprobar nada.

    Se llama cuando el usuario no existe, para que el tiempo de respuesta no
    delate qué correos están registrados.
    """
    _dummy_verify()


def needs_rehash(password_hash: str) -> bool:
    """¿Se hasheó con parámetros de coste ya superados?"""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def generate_password(length: int = 16) -> str:
    """Genera una contraseña aleatoria que cumple la política.

    Se usa al sembrar usuarios de laboratorio y para restablecimientos.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%&*-_=+"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            validate_password(candidate)
        except PasswordPolicyError:
            continue
        return candidate


__all__ = [
    "MIN_PASSWORD_LENGTH", "PasswordPolicyError", "dummy_verify",
    "generate_password", "hash_password", "needs_rehash", "validate_password",
    "verify_password",
]
