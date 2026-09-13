"""Worker durable: reserva, confirma, procesa fuera de transaccion y persiste."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from talentia.bootstrap import migrar
from talentia.config import cargar_configuracion
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    CheckpointWorkflowModelo,
    EvaluacionModelo,
    EvaluacionRequisitoModelo,
    RevisionHumanaModelo,
    TrabajoAgenteModelo,
)

Procesador = Callable[[dict[str, object]], dict[str, object]]


def _decimal_opcional(valor: object) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _persistir_evaluacion(
    sesion: Session,
    trabajo_id: str,
    carga: dict[str, object],
    resultado: dict[str, object],
) -> dict[str, object]:
    requeridos = ("cliente_id", "postulacion_id", "documento_id", "version_perfil_id")
    if any(not carga.get(campo) for campo in requeridos):
        raise ValueError("Carga de evaluacion incompleta")
    evaluacion = sesion.get(EvaluacionModelo, trabajo_id)
    if evaluacion is None:
        evaluacion = EvaluacionModelo(
            id=trabajo_id,
            cliente_id=str(carga["cliente_id"]),
            postulacion_id=str(carga["postulacion_id"]),
            documento_id=str(carga["documento_id"]),
            version_perfil_id=str(carga["version_perfil_id"]),
            puntaje_documental=_decimal_opcional(resultado.get("puntaje_documental")),
            requiere_revision=bool(resultado.get("requiere_revision", True)),
            modelo=str(resultado["modelo"]) if resultado.get("modelo") else None,
            version_prompt=(
                str(resultado["version_prompt"]) if resultado.get("version_prompt") else None
            ),
            simulada=bool(resultado.get("simulada", False)),
        )
        sesion.add(evaluacion)
        sesion.flush()
        requisitos = resultado.get("requisitos", [])
        if isinstance(requisitos, list):
            for requisito in requisitos:
                if not isinstance(requisito, dict):
                    continue
                evidencia = requisito.get("evidencia", [])
                sesion.add(
                    EvaluacionRequisitoModelo(
                        id=nuevo_id(),
                        evaluacion_id=evaluacion.id,
                        codigo_requisito=str(requisito.get("codigo_requisito", "sin_codigo")),
                        veredicto=str(requisito.get("veredicto", "revision_manual")),
                        puntaje=_decimal_opcional(requisito.get("puntaje")),
                        evidencia=evidencia if isinstance(evidencia, list) else [],
                        explicacion=str(requisito.get("explicacion", "")),
                    )
                )
        if evaluacion.requiere_revision:
            sesion.add(
                RevisionHumanaModelo(
                    id=nuevo_id(),
                    evaluacion_id=evaluacion.id,
                    estado="pendiente",
                    comentario=None,
                )
            )
        sesion.flush()
    revision_id = sesion.scalar(
        select(RevisionHumanaModelo.id).where(
            RevisionHumanaModelo.evaluacion_id == evaluacion.id,
            RevisionHumanaModelo.estado == "pendiente",
        )
    )
    return {"evaluacion_id": evaluacion.id, "revision_id": revision_id}


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
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(
                TrabajoAgenteModelo.estado == "reservado",
                TrabajoAgenteModelo.reservado_en < ahora - timedelta(minutes=15),
            )
            .values(estado="pendiente", reservado_en=None, disponible_en=ahora)
        )
        sesion.commit()
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
        tipo_trabajo = candidato.tipo
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
        if tipo_trabajo == "evaluacion":
            resultado = {**resultado, **_persistir_evaluacion(sesion, trabajo_id, carga, resultado)}
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
