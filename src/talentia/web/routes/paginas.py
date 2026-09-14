"""Rutas HTML del piloto; solo coordinan presentacion."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL
from talentia.platform.security.contrasenas import FirmadorSesion, nuevo_csrf
from talentia.shared.application.errores import (
    EntradaInvalidaError,
    NoAutorizadoError,
    TalentIAError,
)
from talentia.shared.domain.modelos import UsuarioActual, nuevo_id

PLANTILLAS = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter()


def _usuario(request: Request) -> UsuarioActual:
    token = request.cookies.get("talentia_session")
    if not token:
        raise NoAutorizadoError("Sesion requerida")
    datos = request.app.state.firmador.leer(token)
    usuario = UsuarioActual(
        id=str(datos["sub"]),
        correo=str(datos["correo"]),
        roles=frozenset(str(rol) for rol in datos.get("roles", [])),
        clientes=frozenset(str(cliente) for cliente in datos.get("clientes", [])),
        sesion_version=int(datos.get("sv", 0)),
    )
    request.app.state.servicio.validar_sesion(usuario)
    return usuario


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


def _requisitos_desde_texto(texto: str) -> list[dict[str, object]]:
    requisitos: list[dict[str, object]] = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip():
            continue
        partes = [parte.strip() for parte in linea.split("|")]
        if len(partes) < 2 or len(partes) > 4:
            raise EntradaInvalidaError(
                f"Linea {numero}: use CODIGO | descripcion | obligatorio/opcional | peso"
            )
        tipo = partes[2].casefold() if len(partes) >= 3 else "obligatorio"
        if tipo not in {"obligatorio", "opcional"}:
            raise EntradaInvalidaError(f"Linea {numero}: indique obligatorio u opcional")
        requisitos.append(
            {
                "codigo": partes[0],
                "descripcion": partes[1],
                "obligatorio": tipo == "obligatorio",
                "peso": partes[3] if len(partes) == 4 else "1",
            }
        )
    return requisitos


def _respuesta_formulario(
    request: Request,
    usuario: UsuarioActual,
    plantilla: str,
    formulario: str,
    *,
    error: str | None = None,
    datos: dict[str, str] | None = None,
    status_code: int = 200,
    **extra: object,
) -> Response:
    opciones = request.app.state.servicio.obtener_opciones_formulario(usuario, formulario)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name=plantilla,
        context=_contexto(
            request,
            usuario,
            opciones=opciones,
            error=error,
            datos=datos or {},
            **extra,
        ),
        status_code=status_code,
    )


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
            "sv": usuario.sesion_version,
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
    usuario = _usuario(request)
    request.app.state.servicio.revocar_sesiones(
        usuario, getattr(request.state, "correlacion_id", nuevo_id())
    )
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
def detalle_candidato(request: Request, candidato_id: str, mensaje: str = "") -> Response:
    usuario = _usuario(request)
    candidato = request.app.state.servicio.obtener_candidato(usuario, candidato_id, nuevo_id())
    traza = request.app.state.servicio.traza_candidato(usuario, candidato_id)
    ficha = asdict(candidato)
    ficha["edad"] = candidato.edad
    ficha["variacion_ctc_porcentaje"] = candidato.variacion_ctc_porcentaje
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_candidato.html",
        context=_contexto(
            request, usuario, candidato=ficha, eventos=traza["eventos"], mensaje=mensaje
        ),
    )


@router.post("/candidatos/{candidato_id}/editar", response_class=HTMLResponse)
async def editar_candidato_web(request: Request, candidato_id: str) -> Response:
    usuario = _usuario(request)
    formulario = await request.form()
    entrada = {clave: str(valor) for clave, valor in formulario.items()}
    if entrada.get("csrf") != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")

    version = int(entrada.get("version", 1))

    cambios: dict[str, object] = {}
    for campo in [
        "nombres",
        "apellidos",
        "correo",
        "telefono",
        "ubicacion",
        "fuente",
        "reclutador",
        "perfil_solicitado",
        "conocimiento_tecnico",
        "disponibilidad",
        "expectativa_salarial",
        "ctc_rol",
    ]:
        if campo in entrada and entrada[campo] != "":
            if campo in {"expectativa_salarial", "ctc_rol"}:
                cambios[campo] = Decimal(entrada[campo])
            else:
                cambios[campo] = entrada[campo]
        elif campo in entrada and entrada[campo] == "":
            cambios[campo] = None

    if "etiquetas" in entrada:
        cambios["etiquetas"] = [
            item.strip() for item in entrada["etiquetas"].split(",") if item.strip()
        ]

    try:
        request.app.state.servicio.actualizar_candidato(
            usuario, candidato_id, version, cambios, request.state.correlacion_id
        )
        return RedirectResponse(f"/candidatos/{candidato_id}?mensaje=actualizado", status_code=303)
    except (TalentIAError, ValueError) as error:
        candidato = request.app.state.servicio.obtener_candidato(usuario, candidato_id, nuevo_id())
        traza = request.app.state.servicio.traza_candidato(usuario, candidato_id)
        ficha = asdict(candidato)
        ficha["edad"] = candidato.edad
        ficha["variacion_ctc_porcentaje"] = candidato.variacion_ctc_porcentaje
        return PLANTILLAS.TemplateResponse(
            request=request,
            name="detalle_candidato.html",
            context=_contexto(
                request, usuario, candidato=ficha, eventos=traza["eventos"], error=str(error)
            ),
            status_code=422,
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


@router.get("/perfiles/nuevo", response_class=HTMLResponse)
def nuevo_perfil(request: Request) -> Response:
    usuario = _usuario(request)
    return _respuesta_formulario(request, usuario, "nuevo_perfil.html", "perfiles")


@router.post("/perfiles/nuevo", response_class=HTMLResponse)
def crear_perfil_web(
    request: Request,
    csrf: str = Form(),
    cliente_id: str = Form(),
    codigo: str = Form(),
    titulo: str = Form(),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    datos = {"cliente_id": cliente_id, "codigo": codigo, "titulo": titulo}
    try:
        perfil = request.app.state.servicio.crear_perfil(
            usuario, datos, request.state.correlacion_id
        )
    except TalentIAError as error:
        return _respuesta_formulario(
            request,
            usuario,
            "nuevo_perfil.html",
            "perfiles",
            error=str(error),
            datos=datos,
            status_code=error.estado_http,
        )
    return RedirectResponse(f"/perfiles/{perfil['id']}/versiones/nueva", status_code=303)


@router.get("/perfiles/{perfil_id}/versiones/nueva", response_class=HTMLResponse)
def nueva_version_perfil(request: Request, perfil_id: str) -> Response:
    usuario = _usuario(request)
    perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)
    return _respuesta_formulario(
        request,
        usuario,
        "nueva_version_perfil.html",
        "perfiles",
        perfil=perfil,
    )


@router.post("/perfiles/{perfil_id}/versiones/nueva", response_class=HTMLResponse)
def crear_version_perfil_web(
    request: Request,
    perfil_id: str,
    csrf: str = Form(),
    requisitos_texto: str = Form(),
    ctc: str = Form(""),
    publicado: str = Form(""),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    datos_formulario = {
        "requisitos_texto": requisitos_texto,
        "ctc": ctc,
        "publicado": publicado,
    }
    try:
        perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)
        version = request.app.state.servicio.crear_version_perfil(
            usuario,
            perfil_id,
            {
                "requisitos": _requisitos_desde_texto(requisitos_texto),
                "ctc": ctc.strip() or None,
                "publicado": publicado == "si",
            },
            request.state.correlacion_id,
        )
    except TalentIAError as error:
        perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_version_perfil.html",
            "perfiles",
            error=str(error),
            datos=datos_formulario,
            status_code=error.estado_http,
            perfil=perfil,
        )
    return RedirectResponse(
        f"/modulo/perfiles?version={version['numero']}&perfil={perfil['id']}", status_code=303
    )


@router.get("/postulaciones/nueva", response_class=HTMLResponse)
def nueva_postulacion(request: Request) -> Response:
    usuario = _usuario(request)
    return _respuesta_formulario(request, usuario, "nueva_postulacion.html", "postulaciones")


@router.post("/postulaciones/nueva", response_class=HTMLResponse)
def crear_postulacion_web(
    request: Request,
    csrf: str = Form(),
    cliente_id: str = Form(),
    candidato_id: str = Form(),
    version_perfil_id: str = Form(),
    fuente: str = Form("directa"),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    datos = {
        "cliente_id": cliente_id,
        "candidato_id": candidato_id,
        "version_perfil_id": version_perfil_id,
        "fuente": fuente,
    }
    try:
        postulacion = request.app.state.servicio.crear_postulacion(
            usuario, datos, request.state.correlacion_id
        )
    except TalentIAError as error:
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_postulacion.html",
            "postulaciones",
            error=str(error),
            datos=datos,
            status_code=error.estado_http,
        )
    return RedirectResponse(
        f"/modulo/postulaciones?postulacion={postulacion['id']}", status_code=303
    )


@router.get("/evaluaciones/nueva", response_class=HTMLResponse)
def nueva_evaluacion(request: Request) -> Response:
    usuario = _usuario(request)
    return _respuesta_formulario(
        request,
        usuario,
        "nueva_evaluacion.html",
        "evaluaciones",
        clave_idempotencia=nuevo_id(),
    )


@router.post("/evaluaciones/nueva", response_class=HTMLResponse)
async def crear_evaluacion_web(
    request: Request,
    archivo: Annotated[UploadFile, File()],
    csrf: str = Form(),
    postulacion_id: str = Form(),
    clave_idempotencia: str = Form(),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    datos = {
        "postulacion_id": postulacion_id,
        "clave_idempotencia": clave_idempotencia,
    }
    try:
        postulacion = request.app.state.servicio.obtener_postulacion(usuario, postulacion_id)
        contenido = await archivo.read()
        documento = request.app.state.servicio.adjuntar_documento(
            usuario,
            str(postulacion["candidato_id"]),
            archivo.filename or "cv",
            archivo.content_type or "application/octet-stream",
            contenido,
            request.state.correlacion_id,
        )
        trabajo = request.app.state.servicio.solicitar_evaluacion(
            usuario,
            {
                "cliente_id": postulacion["cliente_id"],
                "postulacion_id": postulacion_id,
                "documento_id": documento["id"],
                "version_perfil_id": postulacion["version_perfil_id"],
                "clave_idempotencia": clave_idempotencia,
            },
            request.state.correlacion_id,
        )
    except TalentIAError as error:
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_evaluacion.html",
            "evaluaciones",
            error=str(error),
            datos=datos,
            status_code=error.estado_http,
            clave_idempotencia=clave_idempotencia,
        )
    return RedirectResponse(f"/trabajos/{trabajo['id']}", status_code=303)


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


def _pagina_nuevo_lote(
    request: Request,
    usuario: UsuarioActual,
    *,
    error: str | None = None,
    resultado_excolaborador: dict[str, object] | None = None,
) -> Response:
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="nuevo_lote.html",
        context=_contexto(
            request,
            usuario,
            error=error,
            resultado_excolaborador=resultado_excolaborador,
            clave_idempotencia=nuevo_id(),
        ),
    )


@router.get("/lotes/nuevo", response_class=HTMLResponse)
def nuevo_lote(request: Request) -> Response:
    return _pagina_nuevo_lote(request, _usuario(request))


@router.post("/lotes/nuevo", response_class=HTMLResponse)
async def crear_lote_web(
    request: Request,
    archivo: Annotated[UploadFile, File()],
    csrf: str = Form(),
    cliente_id: str = Form(),
    tipo: str = Form(),
    clave_idempotencia: str = Form(),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    try:
        lote = request.app.state.servicio.preparar_lote(
            usuario,
            cliente_id,
            tipo,
            archivo.filename or "lote.csv",
            await archivo.read(),
            clave_idempotencia,
            request.state.correlacion_id,
        )
    except TalentIAError as error:
        return _pagina_nuevo_lote(request, usuario, error=str(error))
    return RedirectResponse(f"/lotes/{lote['id']}", status_code=303)


@router.get("/lotes/{lote_id}", response_class=HTMLResponse)
def detalle_lote(request: Request, lote_id: str) -> Response:
    usuario = _usuario(request)
    return _pagina_detalle_lote(request, usuario, lote_id)


def _pagina_detalle_lote(
    request: Request,
    usuario: UsuarioActual,
    lote_id: str,
    *,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    lote = request.app.state.servicio.obtener_lote(usuario, lote_id)
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_lote.html",
        context=_contexto(request, usuario, lote=lote, error=error),
        status_code=status_code,
    )


@router.post("/lotes/{lote_id}/mapeo", response_class=HTMLResponse)
def mapear_lote_web(
    request: Request,
    lote_id: str,
    csrf: str = Form(),
    origen: str = Form(),
    destino: str = Form(),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    try:
        request.app.state.servicio.aplicar_mapeo_lote(
            usuario, lote_id, {origen: destino}, request.state.correlacion_id
        )
    except TalentIAError as error:
        return _pagina_detalle_lote(
            request, usuario, lote_id, error=str(error), status_code=error.estado_http
        )
    return RedirectResponse(f"/lotes/{lote_id}", status_code=303)


@router.post("/lotes/{lote_id}/filas/{numero}", response_class=HTMLResponse)
async def corregir_fila_lote_web(request: Request, lote_id: str, numero: int) -> Response:
    usuario = _usuario(request)
    formulario = await request.form()
    if str(formulario.get("csrf", "")) != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    datos = {
        clave: str(valor)
        for clave, valor in formulario.items()
        if clave != "csrf" and str(valor).strip()
    }
    try:
        request.app.state.servicio.corregir_fila_lote(
            usuario, lote_id, numero, datos, request.state.correlacion_id
        )
    except TalentIAError as error:
        return _pagina_detalle_lote(
            request, usuario, lote_id, error=str(error), status_code=error.estado_http
        )
    return RedirectResponse(f"/lotes/{lote_id}", status_code=303)


@router.post("/lotes/{lote_id}/confirmar")
def confirmar_lote_web(request: Request, lote_id: str, csrf: str = Form()) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    try:
        request.app.state.servicio.confirmar_lote(usuario, lote_id, request.state.correlacion_id)
    except TalentIAError as error:
        return _pagina_detalle_lote(
            request, usuario, lote_id, error=str(error), status_code=error.estado_http
        )
    return RedirectResponse(f"/lotes/{lote_id}", status_code=303)


@router.post("/lotes/{lote_id}/cancelar")
def cancelar_lote_web(request: Request, lote_id: str, csrf: str = Form()) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    try:
        request.app.state.servicio.cancelar_lote(usuario, lote_id, request.state.correlacion_id)
    except TalentIAError as error:
        return _pagina_detalle_lote(
            request, usuario, lote_id, error=str(error), status_code=error.estado_http
        )
    return RedirectResponse(f"/lotes/{lote_id}", status_code=303)


@router.post("/excolaboradores/comprobar", response_class=HTMLResponse)
def comprobar_excolaborador_web(
    request: Request,
    csrf: str = Form(),
    cliente_id: str = Form(),
    documento: str = Form(),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    resultado = request.app.state.servicio.comprobar_excolaborador(
        usuario, cliente_id, documento, request.state.correlacion_id
    )
    return _pagina_nuevo_lote(request, usuario, resultado_excolaborador=resultado)


@router.get("/exclusiones/nueva", response_class=HTMLResponse)
def nueva_exclusion(request: Request) -> Response:
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="nueva_exclusion.html",
        context=_contexto(request, _usuario(request), error=None),
    )


@router.post("/exclusiones/nueva", response_class=HTMLResponse)
def crear_exclusion_web(
    request: Request,
    csrf: str = Form(),
    cliente_id: str = Form(),
    estado: str = Form(""),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    reporte = request.app.state.servicio.crear_reporte_exclusion(
        usuario,
        cliente_id,
        {"estado": estado} if estado else {},
        request.state.correlacion_id,
    )
    return RedirectResponse(f"/exclusiones/{reporte['id']}", status_code=303)


@router.get("/exclusiones/{reporte_id}", response_class=HTMLResponse)
def detalle_exclusion(request: Request, reporte_id: str) -> Response:
    usuario = _usuario(request)
    reporte = request.app.state.servicio.obtener_reporte_exclusion(
        usuario, reporte_id, request.state.correlacion_id
    )
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_exclusion.html",
        context=_contexto(request, usuario, reporte=reporte),
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
