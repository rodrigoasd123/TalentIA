"""Dependencias de FastAPI: sesión, unidad de trabajo, autenticación y RBAC.

La autorización se declara por endpoint mediante ``requires(Permission.X)``. Un
endpoint que no declara permiso es un endpoint sin protección, así que el arranque
de la aplicación comprueba que todas las rutas de negocio declaran el suyo: es
preferible no arrancar a servir un endpoint desprotegido sin que nadie lo note.

El modo de laboratorio merece una nota. Cuando ``VERA_ENVIRONMENT`` es
``development`` y no llega cabecera de autorización, se asume un usuario
RECRUITER para que la interfaz funcione sin login. **Esa puerta se cierra sola en
cualquier otro entorno** y hay un test que lo verifica; sin esa garantía, sería
exactamente el tipo de atajo que acaba llegando a producción.
"""

from __future__ import annotations

from typing import Annotated, Iterator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.application.services.audit_service import Actor
from app.application.unit_of_work import UnitOfWork
from app.core.config import Environment, get_settings
from app.core.exceptions import AuthenticationError, PermissionDenied
from app.core.logging import get_logger, set_actor_id
from app.domain.enums import ROLE_PERMISSIONS, Permission, Role
from app.infrastructure.database.session import get_session
from app.infrastructure.security.tokens import TokenClaims, TokenService

logger = get_logger(__name__)

SessionDep = Annotated[Session, Depends(get_session)]


def get_uow(session: SessionDep) -> Iterator[UnitOfWork]:
    """Unidad de trabajo ligada a la sesión de la petición.

    La confirmación la hace ``get_session`` al cerrar el contexto, de modo que
    toda la petición es una única transacción.
    """
    yield UnitOfWork(session)


UowDep = Annotated[UnitOfWork, Depends(get_uow)]


class CurrentUser:
    """Identidad autenticada de la petición en curso."""

    def __init__(
        self,
        user_id: str,
        email: str,
        role: Role,
        permissions: frozenset[Permission],
        *,
        is_lab_session: bool = False,
        ip: str = "",
        user_agent: str = "",
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role
        self.permissions = permissions
        self.is_lab_session = is_lab_session
        self.ip = ip
        self.user_agent = user_agent

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        if not self.has(permission):
            raise PermissionDenied(
                f"El rol «{self.role.value}» no tiene el permiso "
                f"{permission.value} necesario para esta operación"
            )

    def as_actor(self) -> Actor:
        return Actor.user(self.user_id, ip=self.ip, user_agent=self.user_agent)


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Resuelve la identidad a partir del token de acceso."""
    settings = get_settings()
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")[:300]

    if not authorization:
        if settings.environment is Environment.DEVELOPMENT:
            # Sesión de laboratorio. Se marca como tal para que la auditoría
            # distinga estas acciones de las de un usuario real autenticado.
            set_actor_id("lab-recruiter")
            return CurrentUser(
                user_id="lab-recruiter",
                email="recruiter@vera-lab.test",
                role=Role.RECRUITER,
                permissions=ROLE_PERMISSIONS[Role.RECRUITER],
                is_lab_session=True,
                ip=ip,
                user_agent=user_agent,
            )
        raise AuthenticationError("Falta la cabecera de autorización")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Formato de autorización inválido; se espera «Bearer <token>»")

    claims: TokenClaims = TokenService().decode(token)
    set_actor_id(claims.subject)
    return CurrentUser(
        user_id=claims.subject,
        email=claims.email,
        role=claims.role,
        permissions=frozenset(Permission(p) for p in claims.permissions),
        ip=ip,
        user_agent=user_agent,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def requires(*permissions: Permission):  # noqa: ANN201
    """Declara los permisos que exige un endpoint.

    Se usan como dependencia:

        @router.post("/x", dependencies=[Depends(requires(Permission.JOB_WRITE))])
    """

    def _check(user: CurrentUserDep) -> CurrentUser:
        for permission in permissions:
            user.require(permission)
        return user

    return _check


def requires_settings_write(user: CurrentUserDep) -> CurrentUser:
    """Permite configurar el laboratorio local; fuera de él exige rol admin."""
    if not user.is_lab_session:
        user.require(Permission.SETTINGS_WRITE)
    return user


def audit_actor(user: CurrentUserDep) -> Actor:
    return user.as_actor()


ActorDep = Annotated[Actor, Depends(audit_actor)]


__all__ = [
    "ActorDep", "CurrentUser", "CurrentUserDep", "SessionDep", "UowDep",
    "audit_actor", "get_current_user", "get_uow", "requires", "requires_settings_write",
]
