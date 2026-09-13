"""Documentos, extracciones y referencias a fuente original."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from talentia.shared.domain.modelos import Entidad


class EstadoExtraccion(StrEnum):
    PENDIENTE = "pendiente"
    COMPLETA = "completa"
    REVISION_MANUAL = "revision_manual"
    BLOQUEADA = "bloqueada"


@dataclass(frozen=True, slots=True)
class ReferenciaFuente:
    documento_id: str
    pagina: int | None
    inicio: int
    fin: int
    fragmento: str


@dataclass(slots=True)
class DocumentoCandidato(Entidad):
    cliente_id: str = ""
    candidato_id: str = ""
    nombre_original: str = ""
    tipo_mime: str = ""
    hash_sha256: str = ""
    ruta_almacenamiento: str = ""
    tamano_bytes: int = 0


@dataclass(slots=True)
class ExtraccionDocumento(Entidad):
    documento_id: str = ""
    estado: EstadoExtraccion = EstadoExtraccion.PENDIENTE
    texto_sanitizado: str | None = None
    campos: dict[str, object] = field(default_factory=dict)
    referencias: list[ReferenciaFuente] = field(default_factory=list)
    error: str | None = None
