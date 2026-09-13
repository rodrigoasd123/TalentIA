"""Worker durable: reserva, confirma, procesa fuera de transaccion y persiste."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from talentia.bootstrap import migrar
from talentia.config import cargar_configuracion
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    CheckpointWorkflowModelo,
    TrabajoAgenteModelo,
)

Procesador = Callable[[dict[str, object]], dict[str, object]]


def resultado_manual(carga: dict[str, object]) -> dict[str, object]:
    return {
        "estado": "revision_manual",
        "motivo": "Proveedor IA no configurado o revision humana requerida",
        "postulacion_id": carga.get("postulacion_id"),
        "es_simulacion": False,
    }


def procesar_siguiente(
    fabrica: FabricaSesiones, procesador: Procesador = resultado_manual
) -> str | None:
    ahora = datetime.now(UTC)
    sesion = fabrica.nueva()
    try:
        candidato = sesion.scalar(
            select(TrabajoAgenteModelo)
            .where(
                TrabajoAgenteModelo.estado == "pendiente",
                TrabajoAgenteModelo.disponible_en <= ahora,
            )
            .order_by(TrabajoAgenteModelo.creado_en)
            .limit(1)
        )
        if candidato is None:
            return None
        reservado = sesion.execute(
            update(TrabajoAgenteModelo)
            .where(
                TrabajoAgenteModelo.id == candidato.id,
                TrabajoAgenteModelo.estado == "pendiente",
            )
            .values(estado="reservado", reservado_en=ahora, intentos=candidato.intentos + 1)
        )
        if not isinstance(reservado, CursorResult) or reservado.rowcount != 1:
            sesion.rollback()
            return None
        sesion.add(
            CheckpointWorkflowModelo(
                id=nuevo_id(),
                trabajo_id=candidato.id,
                nodo="reservado",
                estado={"intento": candidato.intentos + 1},
                secuencia=candidato.intentos * 2 + 1,
            )
        )
        carga = dict(candidato.carga)
        trabajo_id = candidato.id
        max_intentos = candidato.max_intentos
        intento = candidato.intentos + 1
        sesion.commit()
    finally:
        sesion.close()

    try:
        resultado = procesador(carga)
    except Exception as error:
        sesion = fabrica.nueva()
        try:
            estado = "fallido" if intento >= max_intentos else "pendiente"
            demora = min(60, 2**intento)
            sesion.execute(
                update(TrabajoAgenteModelo)
                .where(TrabajoAgenteModelo.id == trabajo_id)
                .values(
                    estado=estado,
                    error=type(error).__name__,
                    disponible_en=datetime.now(UTC) + timedelta(seconds=demora),
                )
            )
            sesion.commit()
        finally:
            sesion.close()
        return trabajo_id

    sesion = fabrica.nueva()
    try:
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(TrabajoAgenteModelo.id == trabajo_id)
            .values(estado="completado", resultado=resultado, error=None)
        )
        sesion.add(
            CheckpointWorkflowModelo(
                id=nuevo_id(),
                trabajo_id=trabajo_id,
                nodo="completado",
                estado={"resultado_disponible": True},
                secuencia=intento * 2,
            )
        )
        sesion.commit()
    finally:
        sesion.close()
    return trabajo_id


def ejecutar() -> None:
    configuracion = cargar_configuracion()
    migrar(configuracion)
    fabrica = FabricaSesiones(crear_motor(configuracion.url_base_datos))
    while True:
        if procesar_siguiente(fabrica) is None:
            time.sleep(1)


if __name__ == "__main__":
    ejecutar()
