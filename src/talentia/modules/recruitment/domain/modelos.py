"""Perfiles versionados y postulaciones."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from talentia.shared.domain.modelos import Entidad


class EstadoPostulacion(StrEnum):
    NUEVA = "nueva"
    CV_RECIBIDO = "cv_recibido"
    EN_EVALUACION = "en_evaluacion"
    REVISION_HUMANA = "revision_humana"
    ENTREVISTA = "entrevista"
    OFERTA = "oferta"
    CONTRATADA = "contratada"
    NO_APTA = "no_apta"
    RETIRADA = "retirada"


@dataclass(frozen=True, slots=True)
class RequisitoPerfil:
    codigo: str
    descripcion: str
    obligatorio: bool
    peso: Decimal


@dataclass(slots=True)
class PerfilPuesto(Entidad):
    cliente_id: str = ""
    codigo: str = ""
    titulo: str = ""
    activo: bool = True


@dataclass(slots=True)
class VersionPerfil(Entidad):
    perfil_id: str = ""
    numero: int = 1
    requisitos: tuple[RequisitoPerfil, ...] = ()
    ctc: Decimal | None = None
    publicado: bool = False


@dataclass(slots=True)
class Postulacion(Entidad):
    cliente_id: str = ""
    candidato_id: str = ""
    version_perfil_id: str = ""
    fuente: str = "directa"
    estado: EstadoPostulacion = EstadoPostulacion.NUEVA
    clave_idempotencia: str = ""
