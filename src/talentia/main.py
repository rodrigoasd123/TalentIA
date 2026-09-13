"""Entrypoint FastAPI unificado para API y web."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from talentia import __version__
from talentia.bootstrap import construir_servicio
from talentia.platform.security.contrasenas import FirmadorSesion
from talentia.shared.application.errores import TalentIAError
from talentia.shared.domain.modelos import nuevo_id
from talentia.web.api import router as api_router
from talentia.web.routes.paginas import router as paginas_router

RUTA_ESTATICOS = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def ciclo_vida(app: FastAPI) -> AsyncIterator[None]:
    configuracion, servicio = construir_servicio()
    app.state.configuracion = configuracion
    app.state.servicio = servicio
    app.state.firmador = FirmadorSesion(
        configuracion.secreto_sesion, configuracion.tiempo_sesion_minutos
    )
    yield


app = FastAPI(
    title="TalentIA",
    version=__version__,
    description="Piloto greenfield de seleccion asistida y gobernada",
    lifespan=ciclo_vida,
)
app.mount("/static", StaticFiles(directory=RUTA_ESTATICOS), name="static")
app.include_router(api_router)
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
def error_talentia(request: Request, error: TalentIAError) -> JSONResponse:
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
