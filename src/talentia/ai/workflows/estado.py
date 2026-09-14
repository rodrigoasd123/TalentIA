"""Estado JSON del workflow AG-02/AG-03; nunca contiene el CV completo."""

from __future__ import annotations

from typing import TypedDict


class EstadoEvaluacion(TypedDict, total=False):
    version: str
    trabajo_id: str
    correlacion_id: str
    cliente_id: str
    candidato_id: str
    postulacion_id: str
    documento_id: str
    hash_documento: str
    version_perfil_id: str
    extraccion_id: str | None
    evaluacion_id: str | None
    estado_extraccion: str | None
    resultados_requisitos: list[dict[str, object]]
    puntaje_documental: str | None
    revision_requerida: bool
    error: str | None
    reintentos: int
    nodos_completados: list[str]


CLAVES_PERSISTIBLES = frozenset(EstadoEvaluacion.__annotations__)


def estado_persistible(estado: EstadoEvaluacion) -> dict[str, object]:
    """Crea una copia JSON segura y rechaza datos documentales crudos."""
    prohibidas = {"texto_original", "paginas_originales", "contenido_documento", "secreto"}
    encontradas = prohibidas.intersection(estado)
    if encontradas:
        raise ValueError(f"El checkpoint contiene claves prohibidas: {sorted(encontradas)}")
    return {clave: valor for clave, valor in estado.items() if clave in CLAVES_PERSISTIBLES}
