"""Estado serializable del workflow AG-02/AG-03; nunca contiene el CV completo."""

from __future__ import annotations

from typing import TypedDict


class EstadoEvaluacion(TypedDict, total=False):
    version: str
    trabajo_id: str
    cliente_id: str
    candidato_id: str
    postulacion_id: str
    documento_id: str
    hash_documento: str
    version_perfil_id: str
    extraccion_id: str | None
    evaluacion_id: str | None
    revision_requerida: bool
    error: str | None
    reintentos: int
    nodos_completados: list[str]
