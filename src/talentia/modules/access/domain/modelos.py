"""Identidad, roles y permisos del piloto."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from talentia.shared.domain.modelos import Entidad


class Rol(StrEnum):
    ADMINISTRADOR = "administrador"
    RECLUTADOR = "reclutador"
    GESTOR_CONTRATACION = "gestor_contratacion"
    ENTREVISTADOR = "entrevistador"
    AUDITOR = "auditor"
    IMPORTADOR = "importador"


PERMISOS_POR_ROL: dict[str, set[str]] = {
    Rol.ADMINISTRADOR: {"*"},
    Rol.RECLUTADOR: {
        "candidatos:leer",
        "candidatos:escribir",
        "postulaciones:escribir",
        "documentos:escribir",
        "evaluaciones:solicitar",
    },
    Rol.GESTOR_CONTRATACION: {
        "candidatos:leer",
        "perfiles:escribir",
        "revisiones:resolver",
        "reportes:leer",
    },
    Rol.ENTREVISTADOR: {"candidatos:leer", "revisiones:resolver"},
    Rol.AUDITOR: {"auditoria:leer", "reportes:leer"},
    Rol.IMPORTADOR: {"lotes:escribir", "excolaboradores:escribir"},
}


@dataclass(slots=True)
class Usuario(Entidad):
    correo: str = ""
    nombre: str = ""
    hash_contrasena: str = ""
    activo: bool = True
    roles: set[Rol] = field(default_factory=set)
    clientes: set[str] = field(default_factory=set)


@dataclass(slots=True)
class Cliente(Entidad):
    codigo: str = ""
    nombre: str = ""
    activo: bool = True
