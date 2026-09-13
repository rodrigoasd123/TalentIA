"""Rutas HTML del piloto; solo coordinan presentacion."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from talentia.platform.security.contrasenas import FirmadorSesion, nuevo_csrf
from talentia.shared.application.errores import NoAutorizadoError, TalentIAError
from talentia.shared.domain.modelos import UsuarioActual, nuevo_id

PLANTILLAS = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter()


def _usuario(request: Request) -> UsuarioActual:
    token = request.cookies.get("talentia_session")
    if not token:
        raise NoAutorizadoError("Sesion requerida")
    datos = request.app.state.firmador.leer(token)
    return UsuarioActual(
        id=str(datos["sub"]),
        correo=str(datos["correo"]),
        roles=frozenset(str(rol) for rol in datos.get("roles", [])),
        clientes=frozenset(str(cliente) for cliente in datos.get("clientes", [])),
    )


def _csrf(request: Request) -> str:
    token = request.cookies.get("talentia_session")
    if not token:
        raise NoAutorizadoError("Sesion requerida")
    return str(request.app.state.firmador.leer(token).get("csrf", ""))


def _contexto(request: Request, usuario: UsuarioActual, **extra: object) -> dict[str, object]:
    return {
        "request": request,
        "usuario": usuario,
        "csrf": _csrf(request),
        "modo_manual": request.app.state.configuracion.modo_manual,
        **extra,
    }


@router.get("/login", response_class=HTMLResponse)
def login(request: Request) -> Response:
    if request.cookies.get("talentia_session"):
        return RedirectResponse("/", status_code=303)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "modo_manual": request.app.state.configuracion.modo_manual},
    )


@router.post("/login")
def iniciar_sesion_web(
    request: Request,
    correo: str = Form(),
    contrasena: str = Form(),
) -> Response:
    try:
        usuario = request.app.state.servicio.autenticar(correo, contrasena, nuevo_id())
    except TalentIAError:
        return PLANTILLAS.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Credenciales invalidas",
                "modo_manual": request.app.state.configuracion.modo_manual,
            },
            status_code=401,
        )
    csrf = nuevo_csrf()
    firmador: FirmadorSesion = request.app.state.firmador
    token = firmador.crear(
        {
            "sub": usuario.id,
            "correo": usuario.correo,
            "roles": sorted(usuario.roles),
            "clientes": sorted(usuario.clientes),
            "csrf": csrf,
        }
    )
    respuesta = RedirectResponse("/", status_code=303)
    respuesta.set_cookie(
        "talentia_session",
        token,
        httponly=True,
        samesite="strict",
        secure=request.app.state.configuracion.ambiente.value == "piloto",
        max_age=request.app.state.configuracion.tiempo_sesion_minutos * 60,
    )
    return respuesta


@router.post("/logout")
def cerrar_sesion_web(request: Request, csrf: str = Form()) -> RedirectResponse:
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    respuesta = RedirectResponse("/login", status_code=303)
    respuesta.delete_cookie("talentia_session")
    return respuesta


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request) -> Response:
    try:
        usuario = _usuario(request)
    except NoAutorizadoError:
        return RedirectResponse("/login", status_code=303)
    candidatos = request.app.state.servicio.buscar_candidatos(usuario, limite=5)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="inicio.html",
        context=_contexto(
            request,
            usuario,
            candidatos=[asdict(item) for item in candidatos],
        ),
    )


@router.get("/candidatos", response_class=HTMLResponse)
def candidatos(request: Request, q: str = "") -> Response:
    try:
        usuario = _usuario(request)
    except NoAutorizadoError:
        return RedirectResponse("/login", status_code=303)
    encontrados = request.app.state.servicio.buscar_candidatos(usuario, q, 100)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="candidatos.html",
        context=_contexto(
            request,
            usuario,
            candidatos=[asdict(item) for item in encontrados],
            consulta=q,
        ),
    )


@router.get("/fragmentos/candidatos", response_class=HTMLResponse)
def tabla_candidatos(request: Request, q: str = "") -> HTMLResponse:
    usuario = _usuario(request)
    encontrados = request.app.state.servicio.buscar_candidatos(usuario, q, 100)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="fragmentos/tabla_candidatos.html",
        context={"candidatos": [asdict(item) for item in encontrados]},
    )


@router.get("/modulo/{modulo}", response_class=HTMLResponse)
def modulo(request: Request, modulo: str) -> HTMLResponse:
    usuario = _usuario(request)
    modulos = {
        "clientes": "Clientes",
        "perfiles": "Perfiles de puesto",
        "postulaciones": "Postulaciones",
        "documentos": "CV y precarga",
        "evaluaciones": "Evaluaciones",
        "revisiones": "Revision humana",
        "lotes": "Lotes de importacion",
        "exclusiones": "Exclusiones",
        "excolaboradores": "Excolaboradores",
        "trabajos": "Trabajos",
        "metricas": "Metricas del piloto",
        "usuarios": "Usuarios y acceso",
    }
    titulo = modulos.get(modulo, "Modulo")
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="modulo.html",
        context=_contexto(request, usuario, titulo=titulo, modulo=modulo),
    )
