"""Entrypoint FastAPI unificado para API y web."""

from __future__ import annotations

import os
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from talentia import __version__
from talentia.ai.workflows.procesador_evaluacion import ProcesadorEvaluacion
from talentia.bootstrap import construir_servicio
from talentia.config import Ambiente
from talentia.modules.documents.infrastructure.extractores import extraer_documento
from talentia.platform.jobs.worker import procesar_siguiente
from talentia.platform.security.contrasenas import FirmadorSesion
from talentia.shared.application.errores import NoAutorizadoError, TalentIAError
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.web.api import router as api_router
from talentia.web.routes.admin_ia import router as admin_ia_router
from talentia.web.routes.paginas import router as paginas_router

RUTA_ESTATICOS = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def ciclo_vida(app: FastAPI) -> AsyncIterator[None]:
    configuracion, servicio, gestor_ia = construir_servicio()
    app.state.configuracion = configuracion
    app.state.servicio = servicio
    app.state.gestor_configuracion_ia = gestor_ia
    app.state.firmador = FirmadorSesion(
        configuracion.secreto_sesion, configuracion.tiempo_sesion_minutos
    )

    detener_worker = threading.Event()
    worker_hilo: threading.Thread | None = None
    if (
        configuracion.ambiente is not Ambiente.PRUEBAS
        and os.getenv("TALENTIA_WORKER_EMBEDDED", "1") == "1"
    ):
        def _bucle_worker() -> None:
            fabrica_worker = FabricaSesiones(crear_motor(configuracion.url_base_datos))
            procesador_worker = ProcesadorEvaluacion(
                fabrica_worker,
                extraer_documento,
                lease_segundos=configuracion.timeout_ia_segundos,
                gestor_ia=gestor_ia,
                mlflow_tracking_uri=configuracion.mlflow_tracking_uri,
            )
            while not detener_worker.is_set():
                try:
                    trabajo = procesar_siguiente(
                        fabrica_worker,
                        procesador_worker,
                        lease_segundos=configuracion.timeout_ia_segundos,
                    )
                    if trabajo is None:
                        detener_worker.wait(1.0)
                except Exception:
                    detener_worker.wait(2.0)

        worker_hilo = threading.Thread(
            target=_bucle_worker, daemon=True, name="TalentIA-Worker-Embebido"
        )
        worker_hilo.start()

    try:
        yield
    finally:
        detener_worker.set()
        if worker_hilo is not None:
            worker_hilo.join(timeout=2.0)


app = FastAPI(
    title="TalentIA",
    version=__version__,
    description="Piloto greenfield de seleccion asistida y gobernada",
    lifespan=ciclo_vida,
)
app.mount("/static", StaticFiles(directory=RUTA_ESTATICOS), name="static")
app.include_router(api_router)
app.include_router(admin_ia_router)
app.include_router(paginas_router)


@app.middleware("http")
async def cabeceras(
    request: Request, llamar_siguiente: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlacion_id = request.headers.get("X-Correlation-ID") or nuevo_id()
    request.state.correlacion_id = correlacion_id
    respuesta = await llamar_siguiente(request)
    respuesta.headers["X-Correlation-ID"] = correlacion_id
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:"
    )
    return respuesta


@app.exception_handler(TalentIAError)
def error_talentia(request: Request, error: TalentIAError) -> Response:
    es_api = request.url.path.startswith("/api/")
    if not es_api and isinstance(error, NoAutorizadoError):
        mensaje = str(error)
        if mensaje != "CSRF invalido":
            if request.headers.get("HX-Request") == "true":
                respuesta = Response(status_code=200, headers={"HX-Redirect": "/login"})
            else:
                respuesta = RedirectResponse("/login", status_code=303)
            respuesta.delete_cookie("talentia_session")
            return respuesta

    return JSONResponse(
        status_code=error.estado_http,
        content={
            "error": {
                "codigo": error.codigo,
                "mensaje": str(error),
                "correlacion_id": getattr(request.state, "correlacion_id", ""),
            }
        },
    )


@app.get("/health")
def salud(request: Request) -> dict[str, object]:
    return {
        "estado": "saludable",
        "version": __version__,
        "modo_manual": request.app.state.configuracion.modo_manual,
    }


def ejecutar() -> None:
    uvicorn.run("talentia.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    ejecutar()
