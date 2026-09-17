"""Perfiles, convocatorias versionadas y candidaturas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from talentia.shared.domain.modelos import Entidad


class EstadoConvocatoria(StrEnum):
    BORRADOR = "borrador"
    ABIERTA = "abierta"
    CERRADA = "cerrada"
    CANCELADA = "cancelada"


class EstadoPostulacion(StrEnum):
    NUEVA = "nueva"
    CONTACTADA = "contactada"
    CV_RECIBIDO = "cv_recibido"
    EN_EVALUACION = "en_evaluacion"
    REVISION_HUMANA = "revision_humana"
    APTA = "apta"
    FINALISTA = "finalista"
    ENTREVISTA = "entrevista"
    OFERTA = "oferta"
    CONTRATADA = "contratada"
    NO_APTA = "no_apta"
    RECHAZADA = "rechazada"
    BACKUP = "backup"
    RETIRADA = "retirada"


TRANSICIONES_POSTULACION: dict[EstadoPostulacion, frozenset[EstadoPostulacion]] = {
    EstadoPostulacion.NUEVA: frozenset({EstadoPostulacion.CONTACTADA, EstadoPostulacion.RETIRADA}),
    EstadoPostulacion.CONTACTADA: frozenset(
        {
            EstadoPostulacion.CV_RECIBIDO,
            EstadoPostulacion.RECHAZADA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.CV_RECIBIDO: frozenset(
        {EstadoPostulacion.EN_EVALUACION, EstadoPostulacion.RETIRADA}
    ),
    EstadoPostulacion.EN_EVALUACION: frozenset(
        {
            EstadoPostulacion.REVISION_HUMANA,
            EstadoPostulacion.NO_APTA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.REVISION_HUMANA: frozenset(
        {
            EstadoPostulacion.APTA,
            EstadoPostulacion.NO_APTA,
            EstadoPostulacion.RECHAZADA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.APTA: frozenset(
        {
            EstadoPostulacion.FINALISTA,
            EstadoPostulacion.BACKUP,
            EstadoPostulacion.RECHAZADA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.FINALISTA: frozenset(
        {
            EstadoPostulacion.ENTREVISTA,
            EstadoPostulacion.APTA,
            EstadoPostulacion.RECHAZADA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.ENTREVISTA: frozenset(
        {
            EstadoPostulacion.OFERTA,
            EstadoPostulacion.BACKUP,
            EstadoPostulacion.RECHAZADA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.OFERTA: frozenset(
        {
            EstadoPostulacion.CONTRATADA,
            EstadoPostulacion.BACKUP,
            EstadoPostulacion.RECHAZADA,
            EstadoPostulacion.RETIRADA,
        }
    ),
    EstadoPostulacion.CONTRATADA: frozenset(),
    EstadoPostulacion.NO_APTA: frozenset(),
    EstadoPostulacion.RECHAZADA: frozenset(),
    EstadoPostulacion.BACKUP: frozenset({EstadoPostulacion.APTA}),
    EstadoPostulacion.RETIRADA: frozenset(),
}

ESTADOS_CON_MOTIVO_OBLIGATORIO = frozenset(
    {
        EstadoPostulacion.FINALISTA,
        EstadoPostulacion.NO_APTA,
        EstadoPostulacion.RECHAZADA,
        EstadoPostulacion.RETIRADA,
    }
)


class TransicionPostulacionInvalidaError(ValueError):
    """La candidatura no admite la transición solicitada."""


def validar_transicion_postulacion(
    origen: EstadoPostulacion,
    destino: EstadoPostulacion,
    motivo: str | None = None,
) -> None:
    """Valida una transición determinística sin consultar IA ni infraestructura."""

    if destino not in TRANSICIONES_POSTULACION.get(origen, frozenset()):
        raise TransicionPostulacionInvalidaError(
            f"Transicion no permitida: {origen.value} -> {destino.value}"
        )
    es_reversion = (
        destino is EstadoPostulacion.APTA and origen is not EstadoPostulacion.REVISION_HUMANA
    )
    requiere_motivo = destino in ESTADOS_CON_MOTIVO_OBLIGATORIO or es_reversion
    if requiere_motivo and not (motivo or "").strip():
        raise TransicionPostulacionInvalidaError("La transicion requiere un motivo")


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
class Convocatoria(Entidad):
    cliente_id: str = ""
    version_perfil_id: str = ""
    codigo: str = ""
    vacantes_total: int = 1
    fecha_apertura: date | None = None
    fecha_objetivo: date | None = None
    estado: EstadoConvocatoria = EstadoConvocatoria.BORRADOR
    motivo_cierre: str | None = None
    es_compatibilidad: bool = False

    def validar(self) -> None:
        if not self.cliente_id or not self.version_perfil_id or not self.codigo.strip():
            raise ValueError("La convocatoria requiere cuenta, version de perfil y codigo")
        if self.vacantes_total < 1:
            raise ValueError("La convocatoria requiere al menos una vacante")
        if not self.es_compatibilidad and (
            self.fecha_apertura is None or self.fecha_objetivo is None
        ):
            raise ValueError("La convocatoria requiere fecha de apertura y fecha objetivo")
        if (
            self.fecha_apertura is not None
            and self.fecha_objetivo is not None
            and self.fecha_objetivo < self.fecha_apertura
        ):
            raise ValueError("La fecha objetivo no puede preceder a la apertura")
        if (
            self.estado in {EstadoConvocatoria.CERRADA, EstadoConvocatoria.CANCELADA}
            and not (self.motivo_cierre or "").strip()
        ):
            raise ValueError("El cierre o cancelacion requiere un motivo")


@dataclass(frozen=True, slots=True)
class AsignacionConvocatoria:
    convocatoria_id: str
    usuario_id: str
    asignado_por: str


@dataclass(slots=True)
class Postulacion(Entidad):
    cliente_id: str = ""
    candidato_id: str = ""
    version_perfil_id: str = ""
    convocatoria_id: str = ""
    fuente: str = "directa"
    estado: EstadoPostulacion = EstadoPostulacion.NUEVA
    clave_idempotencia: str = ""
