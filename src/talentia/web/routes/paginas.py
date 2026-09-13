"""Rutas HTML del piloto; solo coordinan presentacion."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL
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


def _puede(usuario: UsuarioActual, permiso: str) -> bool:
    return usuario.tiene_permiso(permiso, PERMISOS_POR_ROL)


def _respuesta_evaluacion(
    request: Request,
    usuario: UsuarioActual,
    evaluacion_id: str,
    *,
    error: str | None = None,
    datos_formulario: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    evaluacion = request.app.state.servicio.obtener_evaluacion(usuario, evaluacion_id)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_evaluacion.html",
        context=_contexto(
            request,
            usuario,
            evaluacion=evaluacion,
            puede_revisar=_puede(usuario, "revisiones:resolver"),
            error=error,
            datos_formulario=datos_formulario or {},
        ),
        status_code=status_code,
    )


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


@router.get("/candidatos/nuevo", response_class=HTMLResponse)
def nuevo_candidato(request: Request) -> Response:
    usuario = _usuario(request)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="nuevo_candidato.html",
        context=_contexto(request, usuario, error=None, datos={}),
    )


@router.post("/candidatos/nuevo", response_class=HTMLResponse)
async def crear_candidato_web(request: Request) -> Response:
    usuario = _usuario(request)
    formulario = await request.form()
    entrada = {clave: str(valor) for clave, valor in formulario.items()}
    if entrada.get("csrf") != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    cliente_id = entrada.get("cliente_id", "")
    datos: dict[str, object] = {
        "cliente_id": cliente_id,
        "nombres": entrada.get("nombres", ""),
        "apellidos": entrada.get("apellidos", ""),
        "tipo_documento": entrada.get("tipo_documento") or None,
        "documento": entrada.get("documento") or None,
        "correo": entrada.get("correo") or None,
        "telefono": entrada.get("telefono") or None,
        "fecha_nacimiento": date.fromisoformat(entrada["fecha_nacimiento"])
        if entrada.get("fecha_nacimiento")
        else None,
        "ubicacion": entrada.get("ubicacion") or None,
        "fuente": entrada.get("fuente") or None,
        "reclutador": entrada.get("reclutador") or None,
        "perfil_solicitado": entrada.get("perfil_solicitado") or None,
        "conocimiento_tecnico": entrada.get("conocimiento_tecnico") or None,
        "disponibilidad": entrada.get("disponibilidad") or None,
        "expectativa_salarial": Decimal(entrada["expectativa_salarial"])
        if entrada.get("expectativa_salarial")
        else None,
        "ctc_rol": Decimal(entrada["ctc_rol"]) if entrada.get("ctc_rol") else None,
        "etiquetas": [
            item.strip() for item in entrada.get("etiquetas", "").split(",") if item.strip()
        ],
    }
    identidad = {
        "cliente_id": cliente_id,
        "documento": datos["documento"],
        "correo": datos["correo"],
        "telefono": datos["telefono"],
        "nombre_completo": f"{datos['nombres']} {datos['apellidos']}",
    }
    try:
        preflight = request.app.state.servicio.comprobar_identidad(usuario, identidad, nuevo_id())
        if preflight["resultado"] != "ninguna":
            raise TalentIAError("Existe una coincidencia; revise la identidad antes de continuar")
        candidato = request.app.state.servicio.registrar_candidato(
            usuario, datos, str(preflight["preflight_id"]), nuevo_id()
        )
    except (TalentIAError, ValueError) as error:
        return PLANTILLAS.TemplateResponse(
            request=request,
            name="nuevo_candidato.html",
            context=_contexto(request, usuario, error=str(error), datos=entrada),
            status_code=422,
        )
    return RedirectResponse(f"/candidatos/{candidato.id}", status_code=303)


@router.get("/candidatos/{candidato_id}", response_class=HTMLResponse)
def detalle_candidato(request: Request, candidato_id: str) -> Response:
    usuario = _usuario(request)
    candidato = request.app.state.servicio.obtener_candidato(usuario, candidato_id, nuevo_id())
    traza = request.app.state.servicio.traza_candidato(usuario, candidato_id)
    ficha = asdict(candidato)
    ficha["edad"] = candidato.edad
    ficha["variacion_ctc_porcentaje"] = candidato.variacion_ctc_porcentaje
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_candidato.html",
        context=_contexto(request, usuario, candidato=ficha, eventos=traza["eventos"]),
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


@router.get("/modulo/usuarios", response_class=HTMLResponse)
def usuarios(request: Request) -> Response:
    usuario = _usuario(request)
    accesos = request.app.state.servicio.listar_accesos(usuario)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="usuarios.html",
        context=_contexto(request, usuario, accesos=accesos),
    )


@router.post("/modulo/usuarios/rol")
def cambiar_rol_web(
    request: Request,
    csrf: str = Form(),
    usuario_id: str = Form(),
    rol: str = Form(),
    accion: str = Form(),
) -> RedirectResponse:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    request.app.state.servicio.asignar_rol(
        usuario, usuario_id, rol, accion == "asignar", nuevo_id()
    )
    return RedirectResponse("/modulo/usuarios", status_code=303)


@router.post("/modulo/usuarios/cliente")
def cambiar_cliente_web(
    request: Request,
    csrf: str = Form(),
    usuario_id: str = Form(),
    cliente_id: str = Form(),
    accion: str = Form(),
) -> RedirectResponse:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    request.app.state.servicio.asignar_cliente(
        usuario, usuario_id, cliente_id, accion == "asignar", nuevo_id()
    )
    return RedirectResponse("/modulo/usuarios", status_code=303)


@router.get("/evaluaciones/{evaluacion_id}", response_class=HTMLResponse)
def detalle_evaluacion(request: Request, evaluacion_id: str) -> Response:
    usuario = _usuario(request)
    return _respuesta_evaluacion(request, usuario, evaluacion_id)


@router.post("/evaluaciones/{evaluacion_id}/revision", response_class=HTMLResponse)
def resolver_evaluacion_web(
    request: Request,
    evaluacion_id: str,
    csrf: str = Form(),
    decision: str = Form(),
    comentario: str = Form(),
    campo_correccion: str = Form(""),
    valor_anterior: str = Form(""),
    valor_nuevo: str = Form(""),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    formulario = {
        "decision": decision,
        "comentario": comentario,
        "campo_correccion": campo_correccion,
        "valor_anterior": valor_anterior,
        "valor_nuevo": valor_nuevo,
    }
    correcciones: list[dict[str, object]] = []
    if campo_correccion.strip() or valor_nuevo.strip():
        correcciones.append(
            {
                "campo": campo_correccion.strip(),
                "valor_anterior": valor_anterior.strip() or None,
                "valor_nuevo": valor_nuevo.strip(),
            }
        )
    try:
        request.app.state.servicio.registrar_revision(
            usuario,
            evaluacion_id,
            {
                "decision": decision,
                "comentario": comentario,
                "correcciones": correcciones,
            },
            request.state.correlacion_id,
        )
    except TalentIAError as error:
        return _respuesta_evaluacion(
            request,
            usuario,
            evaluacion_id,
            error=str(error),
            datos_formulario=formulario,
            status_code=error.estado_http,
        )
    return RedirectResponse(f"/evaluaciones/{evaluacion_id}?resuelta=1", status_code=303)


@router.get("/trabajos/{trabajo_id}", response_class=HTMLResponse)
def detalle_trabajo(request: Request, trabajo_id: str) -> Response:
    usuario = _usuario(request)
    trabajo = request.app.state.servicio.obtener_trabajo(usuario, trabajo_id)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_trabajo.html",
        context=_contexto(request, usuario, trabajo=trabajo),
    )


@router.get("/fragmentos/trabajos/{trabajo_id}", response_class=HTMLResponse)
def estado_trabajo(request: Request, trabajo_id: str) -> Response:
    usuario = _usuario(request)
    trabajo = request.app.state.servicio.obtener_trabajo(usuario, trabajo_id)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="fragmentos/estado_trabajo.html",
        context={"trabajo": trabajo},
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
    panel = request.app.state.servicio.obtener_panel_operativo(usuario, modulo)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="modulo.html",
        context=_contexto(
            request,
            usuario,
            titulo=titulo,
            modulo=modulo,
            columnas=panel["columnas"],
            filas=panel["filas"],
        ),
    )
