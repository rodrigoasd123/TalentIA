"""Evaluacion inmutable y revision humana obligatoria."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from talentia.modules.documents.domain.modelos import ReferenciaFuente
from talentia.shared.domain.modelos import Entidad


class Veredicto(StrEnum):
    COINCIDE = "coincide"
    NO_COINCIDE = "no_coincide"
    SIN_EVIDENCIA = "sin_evidencia"
    REVISION_MANUAL = "revision_manual"


@dataclass(frozen=True, slots=True)
class ResultadoRequisito:
    codigo_requisito: str
    veredicto: Veredicto
    puntaje: Decimal | None
    evidencia: tuple[ReferenciaFuente, ...] = ()
    explicacion: str = ""


@dataclass(slots=True)
class Evaluacion(Entidad):
    cliente_id: str = ""
    postulacion_id: str = ""
    documento_id: str = ""
    version_perfil_id: str = ""
    resultados: tuple[ResultadoRequisito, ...] = ()
    puntaje_documental: Decimal | None = None
    requiere_revision: bool = True
    modelo: str | None = None
    version_prompt: str | None = None
    simulada: bool = False


@dataclass(slots=True)
class RevisionHumana(Entidad):
    evaluacion_id: str = ""
    revisor_id: str | None = None
    estado: str = "pendiente"
    comentario: str | None = None
    correcciones: dict[str, object] = field(default_factory=dict)
