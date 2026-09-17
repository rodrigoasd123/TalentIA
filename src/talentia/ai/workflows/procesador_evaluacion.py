"""Procesador durable que reanuda el grafo desde checkpoints de SQLite."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from talentia.ai.workflows.estado import EstadoEvaluacion, estado_persistible
from talentia.ai.workflows.evaluation_graph import NODOS, construir_grafo
from talentia.ai.workflows.nodos_evaluacion import ContextoNodosEvaluacion, ExtractorDocumento
from talentia.platform.cliente_llm import ClienteLLM
from talentia.platform.configuracion_ia import GestorConfiguracionIA
from talentia.platform.observabilidad.mlflow_tracker import TrazaWorkflowMLflow
from talentia.platform.observabilidad.telemetria import registrar_metrica
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import FabricaSesiones
from talentia.shared.infrastructure.modelos_orm import (
    CheckpointWorkflowModelo,
    RevisionHumanaModelo,
    TrabajoAgenteModelo,
)


class WorkflowTimeoutError(TimeoutError):
    pass


class WorkflowLeaseError(RuntimeError):
    pass


class WorkflowInterrupcionError(RuntimeError):
    """Usada por pruebas para simular el cierre abrupto del proceso."""


class ProcesadorEvaluacion:
    def __init__(
        self,
        fabrica: FabricaSesiones,
        extractor: ExtractorDocumento,
        *,
        lease_segundos: int = 30,
        fallar_despues_de: str | None = None,
        gestor_ia: GestorConfiguracionIA | None = None,
        mlflow_tracking_uri: str | None = None,
    ) -> None:
        self._fabrica = fabrica
        self._contexto = ContextoNodosEvaluacion(
            fabrica,
            extractor,
            ClienteLLM(
                gestor_ia,
                timeout=max(1.0, min(15.0, lease_segundos / 4)),
            )
            if gestor_ia is not None
            else None,
        )
        self._lease_segundos = lease_segundos
        self._fallar_despues_de = fallar_despues_de
        self._gestor_ia = gestor_ia
        self._mlflow_tracking_uri = mlflow_tracking_uri

    def _estado_inicial(
        self,
        trabajo_id: str,
        carga: dict[str, object],
        correlacion_id: str,
    ) -> EstadoEvaluacion:
        with self._fabrica.sesion() as sesion:
            checkpoint = sesion.scalar(
                select(CheckpointWorkflowModelo)
                .where(
                    CheckpointWorkflowModelo.trabajo_id == trabajo_id,
                    CheckpointWorkflowModelo.nodo.in_(NODOS),
                )
                .order_by(CheckpointWorkflowModelo.secuencia.desc())
                .limit(1)
            )
            if checkpoint is not None:
                return cast(EstadoEvaluacion, dict(checkpoint.estado))
        return EstadoEvaluacion(
            version="1",
            trabajo_id=trabajo_id,
            correlacion_id=correlacion_id,
            cliente_id=str(carga["cliente_id"]),
            candidato_id=str(carga.get("candidato_id", "")),
            postulacion_id=str(carga["postulacion_id"]),
            documento_id=str(carga["documento_id"]),
            hash_documento=str(carga.get("hash_documento", "")),
            version_perfil_id=str(carga["version_perfil_id"]),
            extraccion_id=None,
            evaluacion_id=None,
            estado_extraccion=None,
            resultados_requisitos=[],
            puntaje_documental=None,
            revision_requerida=False,
            error=None,
            reintentos=0,
            nodos_completados=[],
        )

    def procesar(
        self,
        trabajo_id: str,
        carga: dict[str, object],
        correlacion_id: str,
        lease_token: str,
        timeout_segundos: int,
    ) -> dict[str, object]:
        inicio = time.monotonic()
        estado = self._estado_inicial(trabajo_id, carga, correlacion_id)
        estado["reintentos"] = int(estado.get("reintentos", 0)) + 1
        ajustes = self._gestor_ia.obtener_interna() if self._gestor_ia else None
        estado["proveedor_ia"] = ajustes.proveedor if ajustes else "local"
        estado["modelo_ia"] = ajustes.modelo if ajustes else "deterministico-local"
        estado.setdefault("prompt_tokens", 0)
        estado.setdefault("completion_tokens", 0)
        traza_mlflow = TrazaWorkflowMLflow(
            self._mlflow_tracking_uri,
            trabajo_id,
            correlacion_id,
            estado["proveedor_ia"],
            estado["modelo_ia"],
        )
        traza_mlflow.iniciar()
        ultimo_nodo = inicio
        tokens_entrada_previos = int(estado.get("prompt_tokens", 0))
        tokens_salida_previos = int(estado.get("completion_tokens", 0))

        def guardar_checkpoint(nombre: str, actual: EstadoEvaluacion) -> None:
            nonlocal ultimo_nodo, tokens_entrada_previos, tokens_salida_previos
            if time.monotonic() - inicio > timeout_segundos:
                raise WorkflowTimeoutError("timeout_workflow")
            datos = estado_persistible(actual)
            with self._fabrica.sesion() as sesion:
                existente = sesion.scalar(
                    select(CheckpointWorkflowModelo).where(
                        CheckpointWorkflowModelo.trabajo_id == trabajo_id,
                        CheckpointWorkflowModelo.nodo == nombre,
                    )
                )
                if existente is None:
                    sesion.add(
                        CheckpointWorkflowModelo(
                            id=nuevo_id(),
                            trabajo_id=trabajo_id,
                            nodo=nombre,
                            estado=datos,
                            secuencia=100 + NODOS.index(nombre),
                        )
                    )
                    duracion_nodo = round((time.monotonic() - ultimo_nodo) * 1000, 3)
                    ultimo_nodo = time.monotonic()
                    registrar_metrica(
                        sesion,
                        cliente_id=str(actual["cliente_id"]),
                        nombre="workflow.nodo.duracion_ms",
                        valor=duracion_nodo,
                        unidad="ms",
                        dimensiones={
                            "trabajo_id": trabajo_id,
                            "correlacion_id": correlacion_id,
                            "nodo": nombre,
                            "estado": "completado",
                            "error": actual.get("error"),
                        },
                        clave_idempotencia=f"workflow.nodo:{trabajo_id}:{nombre}",
                    )
                    traza_mlflow.registrar_nodo(
                        nombre,
                        secuencia=NODOS.index(nombre) + 1,
                        duracion_ms=duracion_nodo,
                        prompt_tokens=max(
                            0, int(actual.get("prompt_tokens", 0)) - tokens_entrada_previos
                        ),
                        completion_tokens=max(
                            0,
                            int(actual.get("completion_tokens", 0)) - tokens_salida_previos,
                        ),
                    )
                    tokens_entrada_previos = int(actual.get("prompt_tokens", 0))
                    tokens_salida_previos = int(actual.get("completion_tokens", 0))
                renovado = sesion.execute(
                    update(TrabajoAgenteModelo)
                    .where(
                        TrabajoAgenteModelo.id == trabajo_id,
                        TrabajoAgenteModelo.estado == "reservado",
                        TrabajoAgenteModelo.lease_token == lease_token,
                    )
                    .values(
                        lease_expira_en=datetime.now(UTC) + timedelta(seconds=self._lease_segundos)
                    )
                )
                if not isinstance(renovado, CursorResult) or renovado.rowcount != 1:
                    raise WorkflowLeaseError("lease_workflow_perdido")

        def despues_de_nodo(nombre: str, _actual: EstadoEvaluacion) -> None:
            if nombre == self._fallar_despues_de:
                raise WorkflowInterrupcionError(f"interrupcion_despues_de_{nombre}")

        grafo = construir_grafo(self._contexto, guardar_checkpoint, despues_de_nodo)
        try:
            final = cast(EstadoEvaluacion, grafo.invoke(estado))
        except Exception:
            traza_mlflow.finalizar(
                estado="fallido",
                prompt_tokens=int(estado.get("prompt_tokens", 0)),
                completion_tokens=int(estado.get("completion_tokens", 0)),
            )
            raise
        traza_mlflow.finalizar(
            estado="completado",
            prompt_tokens=int(final.get("prompt_tokens", 0)),
            completion_tokens=int(final.get("completion_tokens", 0)),
        )
        evaluacion_id = final.get("evaluacion_id")
        revision_id: str | None = None
        if evaluacion_id:
            with self._fabrica.sesion() as sesion:
                revision_id = sesion.scalar(
                    select(RevisionHumanaModelo.id).where(
                        RevisionHumanaModelo.evaluacion_id == evaluacion_id,
                        RevisionHumanaModelo.estado == "pendiente",
                    )
                )
        return {
            "estado": "revision_requerida" if final.get("revision_requerida") else "completado",
            "evaluacion_id": evaluacion_id,
            "revision_id": revision_id,
            "error": final.get("error"),
            "correlacion_id": final["correlacion_id"],
            "es_simulacion": False,
        }
