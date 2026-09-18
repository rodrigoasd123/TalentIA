"""Panel administrativo de configuracion y diagnostico de IA."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, cast

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from talentia.modules.access.domain.modelos import Rol
from talentia.platform.configuracion_ia import (
    MODELOS_GEMINI,
    MODELOS_OPENAI_AVANZADOS,
    MODELOS_OPENAI_GENAILAB,
    MODELOS_OPENAI_GRATUITOS,
    GestorConfiguracionIA,
)
from talentia.shared.application.errores import ProhibidoError, TalentIAError
from talentia.shared.domain.modelos import UsuarioActual
from talentia.web.routes.paginas import PLANTILLAS, _contexto, _csrf, _usuario

router = APIRouter()


def _administrador(request: Request) -> UsuarioActual:
    usuario = _usuario(request)
    if Rol.ADMINISTRADOR.value not in usuario.roles:
        raise ProhibidoError("Solo administracion puede gestionar la configuracion de IA")
    return usuario


def _gestor(request: Request) -> GestorConfiguracionIA:
    return cast(GestorConfiguracionIA, request.app.state.gestor_configuracion_ia)


def _contexto_panel(
    request: Request,
    usuario: UsuarioActual,
    *,
    error: str | None = None,
    guardado: bool = False,
) -> dict[str, object]:
    return _contexto(
        request,
        usuario,
        ajustes_ia=asdict(_gestor(request).obtener_publica()),
        modelos_openai_genailab=MODELOS_OPENAI_GENAILAB,
        modelos_openai_gratuitos=MODELOS_OPENAI_GRATUITOS,
        modelos_openai_avanzados=MODELOS_OPENAI_AVANZADOS,
        modelos_gemini=MODELOS_GEMINI,
        error=error,
        guardado=guardado,
    )


@router.get("/admin/configuracion-ia", response_class=HTMLResponse)
def configuracion_ia(request: Request, guardado: bool = False) -> Response:
    usuario = _administrador(request)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="configuracion_ia.html",
        context=_contexto_panel(request, usuario, guardado=guardado),
    )


@router.post("/admin/configuracion-ia")
def guardar_configuracion_ia(
    request: Request,
    csrf: Annotated[str, Form()],
    proveedor: Annotated[str, Form()],
    modelo: Annotated[str, Form()],
    temperatura: Annotated[float, Form()],
    tokens_maximos: Annotated[int, Form()],
    version: Annotated[int, Form()],
    api_key: Annotated[str, Form()] = "",
) -> Response:
    usuario = _administrador(request)
    if csrf != _csrf(request):
        raise ProhibidoError("CSRF invalido")
    try:
        _gestor(request).guardar(
            proveedor=proveedor,
            modelo=modelo,
            temperatura=temperatura,
            tokens_maximos=tokens_maximos,
            api_key=api_key,
            version=version,
        )
    except TalentIAError as error:
        return PLANTILLAS.TemplateResponse(
            request=request,
            name="configuracion_ia.html",
            context=_contexto_panel(request, usuario, error=str(error)),
            status_code=error.estado_http,
        )
    return RedirectResponse("/admin/configuracion-ia?guardado=true", status_code=303)


@router.post("/admin/configuracion-ia/diagnostico", response_class=HTMLResponse)
def diagnosticar_configuracion_ia(request: Request, csrf: Annotated[str, Form()]) -> Response:
    _administrador(request)
    if csrf != _csrf(request):
        raise ProhibidoError("CSRF invalido")
    ajustes = asdict(_gestor(request).diagnosticar())
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="fragmentos/estado_ia.html",
        context={"request": request, "ajustes_ia": ajustes},
    )
