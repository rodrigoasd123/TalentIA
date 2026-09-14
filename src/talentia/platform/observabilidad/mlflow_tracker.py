"""Trazas MLflow metadata-only; nunca captura contenido ni bloquea el ATS."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class TrazaWorkflowMLflow:
    tracking_uri: str | None
    trabajo_id: str
    correlacion_id: str
    proveedor: str
    modelo: str
    experimento: str = "talentia-workflows"
    _cliente: object | None = field(default=None, init=False)
    _corrida_id: str | None = field(default=None, init=False)
    _inicio: float = field(default_factory=time.perf_counter, init=False)

    def iniciar(self) -> None:
        if not self.tracking_uri:
            return
        try:
            import mlflow

            mlflow.set_tracking_uri(self.tracking_uri)
            cliente = mlflow.MlflowClient()
            experimento = cliente.get_experiment_by_name(self.experimento)
            experimento_id = (
                experimento.experiment_id
                if experimento is not None
                else cliente.create_experiment(self.experimento)
            )
            corrida = cliente.create_run(
                experimento_id,
                tags={
                    "mlflow.runName": f"workflow-{self.trabajo_id[:8]}",
                    "talentia.tipo": "evaluacion_cv",
                    "talentia.trabajo_id": self.trabajo_id,
                    "talentia.correlacion_id": self.correlacion_id,
                    "talentia.proveedor": self.proveedor,
                    "talentia.modelo": self.modelo,
                    "talentia.privacidad": "metadata-only",
                },
            )
            self._cliente = cliente
            self._corrida_id = str(corrida.info.run_id)
        except Exception:
            self._cliente = None
            self._corrida_id = None

    def registrar_nodo(
        self,
        nombre: str,
        *,
        secuencia: int,
        duracion_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        if self._cliente is None or self._corrida_id is None:
            return
        try:
            cliente = self._cliente
            corrida = cliente.create_run(  # type: ignore[attr-defined]
                cliente.get_run(self._corrida_id).info.experiment_id,  # type: ignore[attr-defined]
                tags={
                    "mlflow.runName": f"{secuencia:02d}-{nombre}",
                    "mlflow.parentRunId": self._corrida_id,
                    "talentia.tipo": "nodo_langgraph",
                    "talentia.nodo": nombre,
                    "talentia.estado": "completado",
                    "talentia.privacidad": "metadata-only",
                },
            )
            run_id = str(corrida.info.run_id)
            total = prompt_tokens + completion_tokens
            cliente.log_metric(run_id, "latencia_ms", duracion_ms)  # type: ignore[attr-defined]
            cliente.log_metric(run_id, "prompt_tokens", prompt_tokens)  # type: ignore[attr-defined]
            cliente.log_metric(run_id, "completion_tokens", completion_tokens)  # type: ignore[attr-defined]
            cliente.log_metric(run_id, "total_tokens", total)  # type: ignore[attr-defined]
            cliente.set_terminated(run_id, status="FINISHED")  # type: ignore[attr-defined]
        except Exception:
            return

    def finalizar(
        self,
        *,
        estado: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        if self._cliente is None or self._corrida_id is None:
            return
        try:
            total = prompt_tokens + completion_tokens
            duracion = (time.perf_counter() - self._inicio) * 1000
            self._cliente.log_metric(self._corrida_id, "latencia_total_ms", duracion)  # type: ignore[attr-defined]
            self._cliente.log_metric(self._corrida_id, "prompt_tokens", prompt_tokens)  # type: ignore[attr-defined]
            self._cliente.log_metric(  # type: ignore[attr-defined]
                self._corrida_id, "completion_tokens", completion_tokens
            )
            self._cliente.log_metric(self._corrida_id, "total_tokens", total)  # type: ignore[attr-defined]
            self._cliente.set_tag(self._corrida_id, "talentia.estado", estado)  # type: ignore[attr-defined]
            self._cliente.set_terminated(  # type: ignore[attr-defined]
                self._corrida_id, status="FINISHED" if estado == "completado" else "FAILED"
            )
        except Exception:
            return
