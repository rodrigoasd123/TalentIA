"""Emisión y verificación de tokens JWT.

Dos tipos de token con propósitos distintos:

* **Acceso**: vida corta (15 minutos), lleva rol y permisos, y se envía en cada
  petición. Al ser corto, un token robado caduca pronto.
* **Refresco**: vida larga (7 días), rotativo y de un solo uso. Sirve únicamente
  para obtener un token de acceso nuevo.

La rotación con detección de reutilización es la parte interesante. Cada refresco
pertenece a una *familia*. Al usarse se invalida y se emite otro de la misma
familia. Si alguien intenta usar un refresco ya consumido, solo caben dos
explicaciones: un error del cliente o un token robado. Ante la duda se asume lo
peor y **se invalida la familia entera**, obligando a iniciar sesión de nuevo.

El registro de tokens consumidos vive en memoria, lo cual basta para el
laboratorio. En producción debe ir a Redis: con varias réplicas, una lista en
memoria por proceso no detecta nada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.domain.enums import ROLE_PERMISSIONS, Role

logger = get_logger(__name__)

ACCESS = "access"
REFRESH = "refresh"


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


@dataclass(slots=True)
class TokenClaims:
    """Contenido verificado de un token."""

    subject: str
    email: str
    role: Role
    permissions: frozenset[str]
    token_type: str
    jti: str
    family: str
    expires_at: datetime

    def has(self, permission: str) -> bool:
        return permission in self.permissions


class RefreshTokenRegistry:
    """Seguimiento de refrescos consumidos y familias revocadas.

    Implementación en memoria. Cambiarla por Redis es sustituir esta clase; el
    resto del módulo no se entera.
    """

    def __init__(self) -> None:
        self._used: set[str] = set()
        self._revoked_families: set[str] = set()
        self._lock = Lock()

    def mark_used(self, jti: str) -> None:
        with self._lock:
            self._used.add(jti)

    def is_used(self, jti: str) -> bool:
        with self._lock:
            return jti in self._used

    def revoke_family(self, family: str) -> None:
        with self._lock:
            self._revoked_families.add(family)

    def is_family_revoked(self, family: str) -> bool:
        with self._lock:
            return family in self._revoked_families

    def clear(self) -> None:
        with self._lock:
            self._used.clear()
            self._revoked_families.clear()


TOKEN_REGISTRY = RefreshTokenRegistry()


class TokenService:
    def __init__(self, registry: RefreshTokenRegistry | None = None) -> None:
        self.registry = registry or TOKEN_REGISTRY

    # ── Emisión ──────────────────────────────────────────────────────────────

    def issue_pair(
        self, *, user_id: str, email: str, role: Role, family: str | None = None
    ) -> TokenPair:
        settings = get_settings()
        family_id = family or uuid.uuid4().hex
        access = self._encode(
            user_id=user_id, email=email, role=role, token_type=ACCESS,
            family=family_id, minutes=settings.access_token_minutes,
        )
        refresh = self._encode(
            user_id=user_id, email=email, role=role, token_type=REFRESH,
            family=family_id, minutes=settings.refresh_token_days * 24 * 60,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_minutes * 60,
        )

    def _encode(
        self, *, user_id: str, email: str, role: Role, token_type: str,
        family: str, minutes: int,
    ) -> str:
        settings = get_settings()
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "role": role.value,
            # Los permisos viajan en el token de acceso para no consultar la
            # base de datos en cada petición. La contrapartida es que un cambio
            # de rol tarda como mucho 15 minutos en surtir efecto, que es un
            # compromiso aceptable a cambio de no acoplar la autorización a la
            # disponibilidad de la base de datos.
            "perms": sorted(p.value for p in ROLE_PERMISSIONS[role]) if token_type == ACCESS else [],
            "type": token_type,
            "jti": uuid.uuid4().hex,
            "fam": family,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=minutes)).timestamp()),
            "iss": "vera-ats",
        }
        return jwt.encode(payload, settings.resolved_jwt_secret(), algorithm=settings.jwt_algorithm)

    # ── Verificación ─────────────────────────────────────────────────────────

    def decode(self, token: str, *, expected_type: str = ACCESS) -> TokenClaims:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.resolved_jwt_secret(),
                # Se fija el algoritmo explícitamente. Aceptar el declarado en la
                # cabecera permitiría el ataque clásico de firmar con "none".
                algorithms=[settings.jwt_algorithm],
                issuer="vera-ats",
                options={"require": ["exp", "sub", "type", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("El token ha expirado") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Token inválido") from exc

        if payload.get("type") != expected_type:
            raise AuthenticationError(
                f"Se esperaba un token de tipo «{expected_type}»"
            )

        family = payload.get("fam", "")
        if self.registry.is_family_revoked(family):
            raise AuthenticationError("La sesión fue revocada")

        return TokenClaims(
            subject=payload["sub"],
            email=payload.get("email", ""),
            role=Role(payload.get("role", Role.RECRUITER.value)),
            permissions=frozenset(payload.get("perms", [])),
            token_type=payload["type"],
            jti=payload["jti"],
            family=family,
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )

    # ── Rotación ─────────────────────────────────────────────────────────────

    def rotate(self, refresh_token: str) -> TokenPair:
        """Canjea un refresco por un par nuevo, detectando reutilización."""
        claims = self.decode(refresh_token, expected_type=REFRESH)

        if self.registry.is_used(claims.jti):
            # Un refresco consumido que vuelve a aparecer es señal de robo. Se
            # invalida toda la familia: es preferible obligar a iniciar sesión de
            # nuevo que mantener viva una sesión posiblemente comprometida.
            self.registry.revoke_family(claims.family)
            logger.security(
                "Reutilización de token de refresco: familia revocada",
                user_id=claims.subject,
                family=claims.family,
            )
            raise AuthenticationError(
                "Token de refresco ya utilizado. La sesión se ha revocado por seguridad."
            )

        self.registry.mark_used(claims.jti)
        return self.issue_pair(
            user_id=claims.subject,
            email=claims.email,
            role=claims.role,
            family=claims.family,
        )

    def revoke_session(self, refresh_token: str) -> None:
        """Cierre de sesión: invalida la familia completa."""
        try:
            claims = self.decode(refresh_token, expected_type=REFRESH)
        except AuthenticationError:
            return  # Un token ya inválido no necesita revocarse.
        self.registry.mark_used(claims.jti)
        self.registry.revoke_family(claims.family)


__all__ = [
    "ACCESS", "REFRESH", "TOKEN_REGISTRY", "RefreshTokenRegistry", "TokenClaims",
    "TokenPair", "TokenService",
]
