"""Tipos compartidos sin dependencias de frameworks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def nuevo_id() -> str:
    return uuid.uuid4().hex


def ahora_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Entidad:
    id: str = field(default_factory=nuevo_id)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)
    version: int = 1

    def actualizar_version(self) -> None:
        self.version += 1
        self.actualizado_en = ahora_utc()


@dataclass(frozen=True, slots=True)
class UsuarioActual:
    id: str
    correo: str
    roles: frozenset[str]
    clientes: frozenset[str]
    sesion_version: int = 1

    def tiene_permiso(self, permiso: str, permisos_por_rol: dict[str, set[str]]) -> bool:
        return any(
            permiso in permisos_por_rol.get(rol, set()) or "*" in permisos_por_rol.get(rol, set())
            for rol in self.roles
        )

    def puede_acceder_cliente(self, cliente_id: str) -> bool:
        return "administrador" in self.roles or cliente_id in self.clientes
