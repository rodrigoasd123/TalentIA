"""Persistencia minima de telemetria sin texto documental ni PII."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.modelos_orm import EventoMetricaPilotoModelo

CLAVES_PERMITIDAS = {
    "correlacion_id",
    "trabajo_id",
    "evaluacion_id",
    "revision_id",
    "nodo",
    "estado",
    "error",
    "intento",
    "resultado",
}
PATRON_PII = re.compile(r"(?:[\w.+-]+@[\w.-]+|\b\d{8,}\b|bearer\s+\S+)", re.IGNORECASE)


def sanitizar_dimensiones(dimensiones: dict[str, object]) -> dict[str, object]:
    salida: dict[str, object] = {}
    for clave, valor in dimensiones.items():
        if clave not in CLAVES_PERMITIDAS or valor is None:
            continue
        if not isinstance(valor, str | int | float | bool):
            continue
        texto = str(valor)[:120]
        salida[clave] = "dato_sensible_omitido" if PATRON_PII.search(texto) else valor
    return salida


def clasificar_error(error: BaseException) -> str:
    return type(error).__name__[:80]


def registrar_metrica(
    sesion: Session,
    *,
    cliente_id: str,
    nombre: str,
    valor: int | float | Decimal,
    unidad: str,
    dimensiones: dict[str, object],
    clave_idempotencia: str | None = None,
) -> None:
    identificador = (
        hashlib.sha256(clave_idempotencia.encode()).hexdigest()[:32]
        if clave_idempotencia
        else nuevo_id()
    )
    if sesion.get(EventoMetricaPilotoModelo, identificador) is not None:
        return
    sesion.add(
        EventoMetricaPilotoModelo(
            id=identificador,
            cliente_id=cliente_id,
            nombre=nombre[:80],
            valor=Decimal(str(valor)),
            unidad=unidad[:30],
            dimensiones=sanitizar_dimensiones(dimensiones),
        )
    )
