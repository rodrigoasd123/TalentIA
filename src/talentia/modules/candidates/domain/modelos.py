"""Candidato canonico, identidad e historial."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from talentia.shared.domain.modelos import Entidad, ahora_utc


class EstadoCandidato(StrEnum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    APTO = "apto"
    NO_APTO = "no_apto"
    RESPALDO = "respaldo"
    CONTRATADO = "contratado"
    BLACKLIST = "blacklist"


class ResultadoIdentidad(StrEnum):
    EXACTA = "exacta"
    PROBABLE = "probable"
    NINGUNA = "ninguna"
    BLOQUEADA = "bloqueada"


@dataclass(frozen=True, slots=True)
class ResolucionIdentidad:
    resultado: ResultadoIdentidad
    criterio: str
    candidato_ids: tuple[str, ...] = ()
    puntaje: Decimal | None = None


@dataclass(slots=True)
class Candidato(Entidad):
    cliente_id: str = ""
    nombres: str = ""
    apellidos: str = ""
    tipo_documento: str | None = None
    documento_normalizado: str | None = None
    correo: str | None = None
    telefono: str | None = None
    fecha_nacimiento: date | None = None
    ubicacion: str | None = None
    fuente: str | None = None
    reclutador: str | None = None
    perfil_solicitado: str | None = None
    conocimiento_tecnico: str | None = None
    disponibilidad: str | None = None
    expectativa_salarial: Decimal | None = None
    ctc_rol: Decimal | None = None
    bgc: str | None = None
    deuda_equifax: Decimal | None = None
    estado: EstadoCandidato = EstadoCandidato.PENDIENTE
    etiquetas: list[str] = field(default_factory=list)

    @property
    def nombre_completo(self) -> str:
        return " ".join(parte for parte in (self.nombres, self.apellidos) if parte).strip()

    @property
    def edad(self) -> int | None:
        if self.fecha_nacimiento is None:
            return None
        hoy = date.today()
        return (
            hoy.year
            - self.fecha_nacimiento.year
            - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        )

    @property
    def variacion_ctc_porcentaje(self) -> Decimal | None:
        if not self.expectativa_salarial or not self.ctc_rol or self.ctc_rol == 0:
            return None
        return ((self.expectativa_salarial - self.ctc_rol) / self.ctc_rol * 100).quantize(
            Decimal("0.01")
        )


@dataclass(frozen=True, slots=True)
class EventoCandidato:
    candidato_id: str
    tipo: str
    actor_id: str
    detalle: dict[str, object]
    ocurrido_en: object = field(default_factory=ahora_utc)


def normalizar_documento(valor: str | None) -> str | None:
    if not valor:
        return None
    normalizado = re.sub(r"[^A-Z0-9]", "", valor.upper())
    return normalizado or None


def normalizar_correo(valor: str | None) -> str | None:
    return valor.strip().casefold() if valor and valor.strip() else None


def ultimos_nueve_telefono(valor: str | None) -> str | None:
    digitos = re.sub(r"\D", "", valor or "")
    return digitos[-9:] if len(digitos) >= 9 else None


def tokens_nombre(valor: str) -> tuple[str, ...]:
    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", valor.casefold())
        if not unicodedata.combining(caracter)
    )
    return tuple(sorted(re.findall(r"[a-z0-9]+", sin_tildes)))
