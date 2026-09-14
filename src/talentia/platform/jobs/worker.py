"""Worker durable: reserva, confirma, procesa fuera de transaccion y persiste."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult

from talentia.ai.workflows.nodos_evaluacion import WorkflowPermanenteError
from talentia.ai.workflows.procesador_evaluacion import ProcesadorEvaluacion
from talentia.bootstrap import migrar
from talentia.config import cargar_configuracion
from talentia.modules.documents.infrastructure.extractores import extraer_documento
from talentia.platform.configuracion_ia import GestorConfiguracionIA
from talentia.platform.observabilidad.telemetria import clasificar_error, registrar_metrica
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.shared.infrastructure.modelos_orm import TrabajoAgenteModelo


def procesar_siguiente(
    fabrica: FabricaSesiones,
    procesador: ProcesadorEvaluacion | None = None,
    *,
    lease_segundos: int = 30,
) -> str | None:
    ahora = datetime.now(UTC)
    sesion = fabrica.nueva()
    inicio_proceso = time.monotonic()
    try:
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(
                TrabajoAgenteModelo.estado == "reservado",
                or_(
                    TrabajoAgenteModelo.lease_expira_en < ahora,
                    and_(
                        TrabajoAgenteModelo.lease_expira_en.is_(None),
                        TrabajoAgenteModelo.reservado_en < ahora - timedelta(minutes=15),
                    ),
                ),
            )
            .values(
                estado="pendiente",
                reservado_en=None,
                lease_token=None,
                lease_expira_en=None,
                disponible_en=ahora,
            )
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
        lease_token = nuevo_id()
        correlacion_id = candidato.correlacion_id or str(
            candidato.carga.get("correlacion_id") or nuevo_id()
        )
        reservado = sesion.execute(
            update(TrabajoAgenteModelo)
            .where(
                TrabajoAgenteModelo.id == candidato.id,
                TrabajoAgenteModelo.estado == "pendiente",
            )
            .values(
                estado="reservado",
                reservado_en=ahora,
                lease_token=lease_token,
                lease_expira_en=ahora + timedelta(seconds=lease_segundos),
                correlacion_id=correlacion_id,
                intentos=candidato.intentos + 1,
            )
        )
        if not isinstance(reservado, CursorResult) or reservado.rowcount != 1:
            sesion.rollback()
            return None
        carga = dict(candidato.carga)
        trabajo_id = candidato.id
        max_intentos = candidato.max_intentos
        intento = candidato.intentos + 1
        timeout_segundos = candidato.timeout_segundos
        sesion.commit()
    finally:
        sesion.close()

    try:
        procesador_real = procesador or ProcesadorEvaluacion(
            fabrica, extraer_documento, lease_segundos=lease_segundos
        )
        resultado = procesador_real.procesar(
            trabajo_id,
            carga,
            correlacion_id,
            lease_token,
            timeout_segundos,
        )
    except Exception as error:
        sesion = fabrica.nueva()
        try:
            permanente = isinstance(error, WorkflowPermanenteError)
            estado = "fallido" if permanente or intento >= max_intentos else "pendiente"
            demora = min(60, 2**intento)
            sesion.execute(
                update(TrabajoAgenteModelo)
                .where(
                    TrabajoAgenteModelo.id == trabajo_id,
                    TrabajoAgenteModelo.lease_token == lease_token,
                )
                .values(
                    estado=estado,
                    error=type(error).__name__,
                    disponible_en=datetime.now(UTC) + timedelta(seconds=demora),
                    reservado_en=None,
                    lease_token=None,
                    lease_expira_en=None,
                )
            )
            registrar_metrica(
                sesion,
                cliente_id=str(carga["cliente_id"]),
                nombre="trabajo.duracion_ms",
                valor=round((time.monotonic() - inicio_proceso) * 1000, 3),
                unidad="ms",
                dimensiones={
                    "trabajo_id": trabajo_id,
                    "correlacion_id": correlacion_id,
                    "estado": estado,
                    "error": clasificar_error(error),
                    "intento": intento,
                },
                clave_idempotencia=f"trabajo.duracion:{trabajo_id}:{intento}",
            )
            sesion.commit()
        finally:
            sesion.close()
        return trabajo_id

    sesion = fabrica.nueva()
    try:
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(
                TrabajoAgenteModelo.id == trabajo_id,
                TrabajoAgenteModelo.lease_token == lease_token,
            )
            .values(
                estado="completado",
                resultado=resultado,
                error=None,
                reservado_en=None,
                lease_token=None,
                lease_expira_en=None,
            )
        )
        registrar_metrica(
            sesion,
            cliente_id=str(carga["cliente_id"]),
            nombre="trabajo.duracion_ms",
            valor=round((time.monotonic() - inicio_proceso) * 1000, 3),
            unidad="ms",
            dimensiones={
                "trabajo_id": trabajo_id,
                "correlacion_id": correlacion_id,
                "estado": "completado",
                "intento": intento,
                "resultado": str(resultado.get("estado", "completado")),
            },
            clave_idempotencia=f"trabajo.duracion:{trabajo_id}:{intento}",
        )
        sesion.commit()
    finally:
        sesion.close()
    return trabajo_id


def ejecutar() -> None:
    configuracion = cargar_configuracion()
    migrar(configuracion)
    fabrica = FabricaSesiones(crear_motor(configuracion.url_base_datos))
    gestor_ia = GestorConfiguracionIA(fabrica, configuracion)
    procesador = ProcesadorEvaluacion(
        fabrica,
        extraer_documento,
        lease_segundos=configuracion.timeout_ia_segundos,
        gestor_ia=gestor_ia,
        mlflow_tracking_uri=configuracion.mlflow_tracking_uri,
    )
    while True:
        if (
            procesar_siguiente(
                fabrica,
                procesador,
                lease_segundos=configuracion.timeout_ia_segundos,
            )
            is None
        ):
            time.sleep(1)


if __name__ == "__main__":
    ejecutar()
