"""Rutas HTML del piloto; solo coordinan presentacion."""

from __future__ import annotations

import contextlib
import csv
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from talentia.ai.agents.cruce_candidatos import construir_reporte_cruce
from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL
from talentia.modules.recruitment.application.extractor_convocatoria import (
    extraer_bases_convocatoria,
)
from talentia.platform.security.contrasenas import FirmadorSesion, nuevo_csrf
from talentia.shared.application.errores import (
    EntradaInvalidaError,
    NoAutorizadoError,
    NoEncontradoError,
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
        try:
            _usuario(request)
            return RedirectResponse("/", status_code=303)
        except NoAutorizadoError:
            pass
    respuesta = PLANTILLAS.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "modo_manual": request.app.state.configuracion.modo_manual},
    )
    if request.cookies.get("talentia_session"):
        respuesta.delete_cookie("talentia_session")
    return respuesta


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
    usuario = _usuario(request)
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
    usuario = _usuario(request)
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
    return _respuesta_formulario(
        request,
        usuario,
        "nuevo_candidato.html",
        "candidatos",
    )


def _pagina_importar_cvs(
    request: Request,
    usuario: UsuarioActual,
    *,
    resultados: list[dict[str, object]] | None = None,
    reporte_cruce: dict[str, object] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    return _respuesta_formulario(
        request,
        usuario,
        "importar_cvs.html",
        "importar_cvs",
        resultados=resultados or [],
        reporte_cruce=reporte_cruce,
        error=error,
        status_code=status_code,
    )


@router.get("/candidatos/importar-cvs", response_class=HTMLResponse)
def importar_cvs(request: Request) -> Response:
    return _pagina_importar_cvs(request, _usuario(request))


@router.post("/candidatos/importar-cvs", response_class=HTMLResponse)
async def importar_cvs_web(
    request: Request,
    archivos: Annotated[list[UploadFile], File()],
    csrf: str = Form(),
    cliente_id: str = Form(),
    fuente: str = Form(""),
    reclutador: str = Form(""),
    version_perfil_id: str = Form(""),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    if not archivos or len(archivos) > 50:
        return _pagina_importar_cvs(
            request,
            usuario,
            error="Seleccione entre 1 y 50 CV",
            status_code=422,
        )

    tipos = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    resultados: list[dict[str, object]] = []
    for archivo in archivos:
        nombre = archivo.filename or "cv"
        tipo_mime = tipos.get(Path(nombre).suffix.casefold(), archivo.content_type or "")
        try:
            resultado = request.app.state.servicio.registrar_candidato_desde_cv(
                usuario,
                cliente_id,
                nombre,
                tipo_mime,
                await archivo.read(),
                fuente,
                reclutador,
                request.state.correlacion_id,
                version_perfil_id=version_perfil_id.strip() or None,
            )
            resultados.append(resultado)
        except (TalentIAError, ValueError) as error:
            resultados.append(
                {
                    "archivo": nombre,
                    "estado": "requiere_revision",
                    "error": str(error),
                    "alertas": [],
                }
            )
    return _pagina_importar_cvs(
        request,
        usuario,
        resultados=resultados,
        reporte_cruce=construir_reporte_cruce(resultados),
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
        "confirmar_posible_duplicado": entrada.get("confirmar_posible_duplicado") == "si",
    }
    identidad = {
        "cliente_id": cliente_id,
        "documento": datos["documento"],
        "correo": datos["correo"],
        "telefono": datos["telefono"],
        "nombre_completo": f"{datos['nombres']} {datos['apellidos']}",
    }
    evidencia_identidad: list[dict[str, object]] = []
    try:
        preflight = request.app.state.servicio.comprobar_identidad(usuario, identidad, nuevo_id())
        evidencia_identidad = list(cast(list[dict[str, object]], preflight.get("evidencia", [])))
        if preflight["resultado"] == "exacta":
            raise TalentIAError("Existe una identidad exacta; no se creara un duplicado")
        if preflight["resultado"] == "probable" and not datos["confirmar_posible_duplicado"]:
            raise TalentIAError(
                "Existe una coincidencia probable; revise y marque la confirmacion humana"
            )
        candidato = request.app.state.servicio.registrar_candidato(
            usuario, datos, str(preflight["preflight_id"]), nuevo_id()
        )
    except (TalentIAError, ValueError) as error:
        opciones = request.app.state.servicio.obtener_opciones_formulario(usuario, "candidatos")
        return PLANTILLAS.TemplateResponse(
            request=request,
            name="nuevo_candidato.html",
            context=_contexto(
                request,
                usuario,
                error=str(error),
                datos=entrada,
                evidencia_identidad=evidencia_identidad,
                opciones=opciones,
            ),
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
    alertas = [
        evento["detalle"]
        for evento in traza["eventos"]
        if evento["tipo"] == "candidato.alerta_lista_control"
    ]
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_candidato.html",
        context=_contexto(
            request,
            usuario,
            candidato=ficha,
            eventos=traza["eventos"],
            alertas=alertas,
            mensaje=mensaje,
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
    mapa_clientes = {
        c["id"]: c.get("nombre") or c.get("codigo") or c["id"] for c in accesos.get("clientes", [])
    }
    for u in accesos.get("usuarios", []):
        u["clientes_nombres"] = [mapa_clientes.get(cid, cid) for cid in u.get("clientes", [])]
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


@router.post("/perfiles/analizar-convocatoria-previa")
async def analizar_convocatoria_previa_ajax(
    request: Request,
    archivo: Annotated[UploadFile, File()],
    csrf: str = Form(""),
) -> Response:
    _usuario(request)
    if csrf and csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    contenido = await archivo.read()
    if not contenido:
        return JSONResponse({"exito": False, "error": "Archivo vacío"}, status_code=400)
    try:
        gestor_ia = getattr(request.app.state, "gestor_ia", None)
        resultado = extraer_bases_convocatoria(
            contenido,
            archivo.content_type or "",
            nombre_archivo=archivo.filename or "",
            gestor_ia=gestor_ia,
        )
        return JSONResponse(
            {
                "exito": True,
                "titulo": resultado.titulo,
                "codigo": resultado.codigo,
                "ctc": resultado.ctc or "",
                "total_requisitos": len(resultado.requisitos),
                "resumen": resultado.resumen,
            }
        )
    except Exception as exc:
        return JSONResponse({"exito": False, "error": str(exc)}, status_code=422)


@router.get("/perfiles/nuevo", response_class=HTMLResponse)
def nuevo_perfil(request: Request) -> Response:
    usuario = _usuario(request)
    return _respuesta_formulario(request, usuario, "nuevo_perfil.html", "perfiles")


@router.post("/perfiles/nuevo", response_class=HTMLResponse)
async def crear_perfil_web(
    request: Request,
    csrf: str = Form(),
    cliente_id: str = Form(),
    codigo: str = Form(""),
    titulo: str = Form(""),
    archivo_convocatoria: Annotated[UploadFile | None, File()] = None,
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")

    resultado_convocatoria = None
    if archivo_convocatoria and archivo_convocatoria.filename:
        contenido = await archivo_convocatoria.read()
        if contenido:
            with contextlib.suppress(Exception):
                gestor_ia = getattr(request.app.state, "gestor_ia", None)
                resultado_convocatoria = extraer_bases_convocatoria(
                    contenido,
                    archivo_convocatoria.content_type or "",
                    nombre_archivo=archivo_convocatoria.filename or "",
                    gestor_ia=gestor_ia,
                )
                if not titulo.strip() and resultado_convocatoria.titulo:
                    titulo = resultado_convocatoria.titulo
                if not codigo.strip() and resultado_convocatoria.codigo:
                    codigo = resultado_convocatoria.codigo

    if not codigo.strip() or not titulo.strip():
        datos = {"cliente_id": cliente_id, "codigo": codigo, "titulo": titulo}
        return _respuesta_formulario(
            request,
            usuario,
            "nuevo_perfil.html",
            "perfiles",
            error="Debe indicar el código y título del rol, o adjuntar un archivo de convocatoria.",
            datos=datos,
            status_code=422,
        )

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

    # Si se cargo la convocatoria y se extrajeron requisitos:
    # Creamos y publicamos la versión 1 automáticamente y vamos directo a la vacante
    if resultado_convocatoria and resultado_convocatoria.requisitos:
        with contextlib.suppress(Exception):
            reqs = _requisitos_desde_texto(resultado_convocatoria.requisitos_texto)
            request.app.state.servicio.crear_version_perfil(
                usuario,
                perfil["id"],
                {
                    "requisitos": reqs,
                    "ctc": resultado_convocatoria.ctc,
                    "publicado": True,
                },
                request.state.correlacion_id,
            )
            return RedirectResponse(f"/perfiles/{perfil['id']}", status_code=303)
    with contextlib.suppress(Exception):
        cod_clean = "".join(c for c in codigo if c.isalnum() or c == "-")[:8].upper() or "ROL"
        req_base = [
            {
                "codigo": f"REQ-{cod_clean}-01",
                "descripcion": f"Competencias y experiencia técnica requeridas para {titulo}",
                "obligatorio": True,
                "peso": "1.0",
            }
        ]
        request.app.state.servicio.crear_version_perfil(
            usuario,
            perfil["id"],
            {
                "requisitos": req_base,
                "publicado": True,
            },
            request.state.correlacion_id,
        )

    return RedirectResponse(f"/perfiles/{perfil['id']}", status_code=303)


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
async def crear_version_perfil_web(
    request: Request,
    perfil_id: str,
    csrf: str = Form(),
    requisitos_texto: str = Form(""),
    ctc: str = Form(""),
    publicado: str = Form(""),
    archivo_convocatoria: Annotated[UploadFile | None, File()] = None,
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")

    # Si el usuario adjunto un archivo de convocatoria directamente en el formulario
    if archivo_convocatoria and archivo_convocatoria.filename:
        contenido = await archivo_convocatoria.read()
        if contenido:
            try:
                gestor_ia = getattr(request.app.state, "gestor_ia", None)
                res = extraer_bases_convocatoria(
                    contenido,
                    archivo_convocatoria.content_type or "",
                    nombre_archivo=archivo_convocatoria.filename or "",
                    gestor_ia=gestor_ia,
                )
                if not requisitos_texto.strip():
                    requisitos_texto = res.requisitos_texto
                if not ctc.strip() and res.ctc:
                    ctc = res.ctc
                if not publicado:
                    publicado = "si"
            except Exception as e:
                perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)
                return _respuesta_formulario(
                    request,
                    usuario,
                    "nueva_version_perfil.html",
                    "perfiles",
                    error=f"No se pudo extraer la convocatoria: {e}",
                    datos={
                        "requisitos_texto": requisitos_texto,
                        "ctc": ctc,
                        "publicado": publicado,
                    },
                    status_code=422,
                    perfil=perfil,
                )

    if not requisitos_texto.strip():
        perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_version_perfil.html",
            "perfiles",
            error=(
                "Selecciona un archivo de convocatoria (Word o PDF) "
                "o escribe los requisitos del puesto."
            ),
            datos={"requisitos_texto": "", "ctc": ctc, "publicado": publicado},
            status_code=422,
            perfil=perfil,
        )

    datos_formulario = {
        "requisitos_texto": requisitos_texto,
        "ctc": ctc,
        "publicado": publicado,
    }
    try:
        perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)
        _ = request.app.state.servicio.crear_version_perfil(
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
    return RedirectResponse(f"/perfiles/{perfil['id']}", status_code=303)


@router.post("/perfiles/{perfil_id}/versiones/analizar-convocatoria")
async def analizar_convocatoria_version_ajax(
    request: Request,
    perfil_id: str,
    archivo: Annotated[UploadFile, File()],
    csrf: str = Form(""),
) -> Response:
    usuario = _usuario(request)
    if csrf and csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    _ = request.app.state.servicio.obtener_perfil(usuario, perfil_id)

    contenido = await archivo.read()
    if not contenido:
        return JSONResponse(
            {"exito": False, "error": "El archivo está vacío o no es legible"}, status_code=400
        )

    try:
        gestor_ia = getattr(request.app.state, "gestor_ia", None)
        resultado = extraer_bases_convocatoria(
            contenido,
            archivo.content_type or "",
            nombre_archivo=archivo.filename or "",
            gestor_ia=gestor_ia,
        )
        return JSONResponse(
            {
                "exito": True,
                "titulo": resultado.titulo,
                "codigo": resultado.codigo,
                "ctc": resultado.ctc or "",
                "requisitos_texto": resultado.requisitos_texto,
                "total_obligatorios": resultado.total_obligatorios,
                "total_deseables": resultado.total_deseables,
                "resumen": resultado.resumen,
            }
        )
    except Exception as exc:
        return JSONResponse(
            {"exito": False, "error": f"No se pudo procesar la convocatoria: {exc}"},
            status_code=422,
        )


@router.post("/perfiles/{perfil_id}/versiones/cargar-convocatoria", response_class=HTMLResponse)
async def cargar_convocatoria_version_web(
    request: Request,
    perfil_id: str,
    archivo: Annotated[UploadFile, File()],
    csrf: str = Form(),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    perfil = request.app.state.servicio.obtener_perfil(usuario, perfil_id)

    contenido = await archivo.read()
    if not contenido:
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_version_perfil.html",
            "perfiles",
            error="Seleccione un archivo de convocatoria valido (PDF o DOCX)",
            status_code=422,
            perfil=perfil,
        )

    try:
        gestor_ia = getattr(request.app.state, "gestor_ia", None)
        resultado = extraer_bases_convocatoria(
            contenido,
            archivo.content_type or "",
            nombre_archivo=archivo.filename or "",
            gestor_ia=gestor_ia,
        )
        datos_formulario = {
            "requisitos_texto": resultado.requisitos_texto,
            "ctc": resultado.ctc or "",
            "publicado": "si",
        }
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_version_perfil.html",
            "perfiles",
            datos=datos_formulario,
            perfil=perfil,
            mensaje_exito=resultado.resumen,
        )
    except Exception as exc:
        return _respuesta_formulario(
            request,
            usuario,
            "nueva_version_perfil.html",
            "perfiles",
            error=f"No se pudo extraer la convocatoria: {exc}",
            status_code=422,
            perfil=perfil,
        )


@router.get("/perfiles/{perfil_id}", response_class=HTMLResponse)
def detalle_perfil_web(
    request: Request,
    perfil_id: str,
    mensaje: str = "",
    filtro_completitud: str = "todos",
) -> Response:
    usuario = _usuario(request)
    correlacion_id = getattr(request.state, "correlacion_id", nuevo_id())
    detalle = request.app.state.servicio.obtener_detalle_perfil(usuario, perfil_id, correlacion_id)

    postulantes = detalle["postulantes"]
    if filtro_completitud == "completos":
        postulantes = [p for p in postulantes if p["completitud"]["completo"]]
    elif filtro_completitud == "incompletos":
        postulantes = [p for p in postulantes if not p["completitud"]["completo"]]
    elif filtro_completitud == "alertas":
        postulantes = [p for p in postulantes if p["alertas"]]

    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_perfil.html",
        context=_contexto(
            request,
            usuario,
            perfil=detalle["perfil"],
            versiones=detalle["versiones"],
            version_activa=detalle["version_activa"],
            postulantes=postulantes,
            metricas=detalle["metricas"],
            filtro_completitud=filtro_completitud,
            mensaje=mensaje,
            resultados=None,
        ),
    )


@router.post("/perfiles/{perfil_id}/importar-cvs", response_class=HTMLResponse)
async def importar_cvs_perfil_web(
    request: Request,
    perfil_id: str,
    archivos: Annotated[list[UploadFile], File()],
    csrf: str = Form(),
    fuente: str = Form(""),
    reclutador: str = Form(""),
) -> Response:
    usuario = _usuario(request)
    if csrf != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")
    correlacion_id = getattr(request.state, "correlacion_id", nuevo_id())
    detalle = request.app.state.servicio.obtener_detalle_perfil(usuario, perfil_id, correlacion_id)
    version_activa = detalle["version_activa"]
    if not version_activa:
        raise EntradaInvalidaError("El perfil no cuenta con una versión publicada")

    if not archivos or len(archivos) > 50:
        return PLANTILLAS.TemplateResponse(
            request=request,
            name="detalle_perfil.html",
            context=_contexto(
                request,
                usuario,
                perfil=detalle["perfil"],
                versiones=detalle["versiones"],
                version_activa=version_activa,
                postulantes=detalle["postulantes"],
                metricas=detalle["metricas"],
                error="Seleccione entre 1 y 50 archivos de currículum",
                status_code=422,
            ),
            status_code=422,
        )

    tipos = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    cliente_id = str(detalle["perfil"]["cliente_id"])
    version_id = str(version_activa["id"])

    resultados: list[dict[str, object]] = []
    for archivo in archivos:
        nombre = archivo.filename or "cv"
        tipo_mime = tipos.get(Path(nombre).suffix.casefold(), archivo.content_type or "")
        try:
            resultado = request.app.state.servicio.registrar_candidato_desde_cv(
                usuario,
                cliente_id,
                nombre,
                tipo_mime,
                await archivo.read(),
                fuente,
                reclutador,
                correlacion_id,
                version_perfil_id=version_id,
            )
            resultados.append(resultado)
        except (TalentIAError, ValueError) as error:
            resultados.append(
                {
                    "archivo": nombre,
                    "estado": "requiere_revision",
                    "error": str(error),
                    "alertas": [],
                }
            )

    detalle_actualizado = request.app.state.servicio.obtener_detalle_perfil(
        usuario, perfil_id, correlacion_id
    )
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="detalle_perfil.html",
        context=_contexto(
            request,
            usuario,
            perfil=detalle_actualizado["perfil"],
            versiones=detalle_actualizado["versiones"],
            version_activa=detalle_actualizado["version_activa"],
            postulantes=detalle_actualizado["postulantes"],
            metricas=detalle_actualizado["metricas"],
            resultados=resultados,
            reporte_cruce=construir_reporte_cruce(resultados),
            mensaje="cvs_procesados",
        ),
    )


@router.post(
    "/perfiles/{perfil_id}/candidatos/{candidato_id}/completar-rrhh", response_class=HTMLResponse
)
async def completar_rrhh_candidato_web(  # noqa: C901
    request: Request,
    perfil_id: str,
    candidato_id: str,
) -> Response:
    usuario = _usuario(request)
    formulario = await request.form()
    entrada = {clave: str(valor) for clave, valor in formulario.items()}
    if entrada.get("csrf") != _csrf(request):
        raise NoAutorizadoError("CSRF invalido")

    version = int(entrada.get("version", 1))
    cambios: dict[str, object] = {}

    for campo in [
        "reclutador",
        "fecha_nacimiento",
        "ctc_rol",
        "expectativa_salarial",
        "disponibilidad",
    ]:
        if campo in entrada and entrada[campo].strip() != "":
            cambios[campo] = entrada[campo].strip()
        elif campo in entrada and entrada[campo].strip() == "":
            cambios[campo] = None

    etiquetas_raw = [x.strip() for x in entrada.get("etiquetas", "").split(",") if x.strip()]
    if entrada.get("bgc_validado") in {"si", "true", "on", "1"}:
        if "bgc-validado" not in etiquetas_raw:
            etiquetas_raw.append("bgc-validado")
    if entrada.get("titulo_verificado") in {"si", "true", "on", "1"}:
        if "titulo-validado" not in etiquetas_raw:
            etiquetas_raw.append("titulo-validado")
    if entrada.get("verificado_rrhh") in {"si", "true", "on", "1"}:
        if "verificado-rrhh" not in etiquetas_raw:
            etiquetas_raw.append("verificado-rrhh")

    if etiquetas_raw or "etiquetas" in entrada:
        cambios["etiquetas"] = etiquetas_raw

    correlacion_id = getattr(request.state, "correlacion_id", nuevo_id())
    request.app.state.servicio.actualizar_candidato(
        usuario, candidato_id, version, cambios, correlacion_id
    )
    return RedirectResponse(f"/perfiles/{perfil_id}?mensaje=candidato_completado", status_code=303)


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
    opciones = request.app.state.servicio.obtener_opciones_formulario(usuario, "lotes")
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="nuevo_lote.html",
        context=_contexto(
            request,
            usuario,
            error=error,
            resultado_excolaborador=resultado_excolaborador,
            clave_idempotencia=nuevo_id(),
            opciones=opciones,
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
    usuario = _usuario(request)
    opciones = request.app.state.servicio.obtener_opciones_formulario(usuario, "exclusiones")
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="nueva_exclusion.html",
        context=_contexto(request, usuario, error=None, opciones=opciones),
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


# ---------------------------------------------------------------------------
# Rutas dedicadas: Ex-TCS y Exclusiones con datos enriquecidos
# ---------------------------------------------------------------------------

_CSV_EXCOLAB = (
    Path(__file__).resolve().parents[4]
    / "descargas_talento/03_Excolaboradores_TCS/excolaboradores_tcs_simulados.csv"
)
_CSV_VETADOS = (
    Path(__file__).resolve().parents[4]
    / "descargas_talento/04_Vetados_y_Exclusiones_TCS/vetados_excluidos_tcs_simulados.csv"
)
_CSV_REPORTE_AG05 = (
    Path(__file__).resolve().parents[4]
    / "descargas_talento/04_Vetados_y_Exclusiones_TCS/reporte_exclusiones_oficial_tcs.csv"
)


def _leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@router.get("/modulo/excolaboradores", response_class=HTMLResponse)
def modulo_excolaboradores(request: Request) -> Response:
    usuario = _usuario(request)
    excolaboradores = _leer_csv(_CSV_EXCOLAB)
    elegible_val = "SI"
    total_elegibles = sum(
        1 for ex in excolaboradores if str(ex.get("elegible_reingreso", "")).upper() == elegible_val
    )
    total_no_elegibles = len(excolaboradores) - total_elegibles
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="excolaboradores.html",
        context=_contexto(
            request,
            usuario,
            excolaboradores=excolaboradores,
            total_elegibles=total_elegibles,
            total_no_elegibles=total_no_elegibles,
        ),
    )


@router.get("/modulo/exclusiones", response_class=HTMLResponse)
def modulo_exclusiones(request: Request) -> Response:
    usuario = _usuario(request)
    vetados = _leer_csv(_CSV_VETADOS)
    total_permanentes = sum(1 for v in vetados if v.get("estado_restriccion") == "Permanente")
    _tipos_eticos = {"Ético", "Ética", "BGC", "Integridad", "Inhabilitaci"}
    total_eticas = sum(
        1 for v in vetados if any(t in str(v.get("tipo_restriccion", "")) for t in _tipos_eticos)
    )
    total_carencias = sum(1 for v in vetados if "Carencia" in str(v.get("tipo_restriccion", "")))
    return PLANTILLAS.TemplateResponse(
        request=request,
        name="exclusiones.html",
        context=_contexto(
            request,
            usuario,
            vetados=vetados,
            total_permanentes=total_permanentes,
            total_eticas=total_eticas,
            total_carencias=total_carencias,
        ),
    )


@router.get("/descargas/excolaboradores.csv")
def descargar_excolaboradores(request: Request) -> Response:
    _usuario(request)
    if not _CSV_EXCOLAB.exists():
        raise NoEncontradoError("Archivo CSV de excolaboradores no encontrado")
    return FileResponse(
        path=str(_CSV_EXCOLAB),
        media_type="text/csv; charset=utf-8",
        filename="excolaboradores_tcs_simulados.csv",
    )


@router.get("/descargas/vetados.csv")
def descargar_vetados(request: Request) -> Response:
    _usuario(request)
    if not _CSV_VETADOS.exists():
        raise NoEncontradoError("Archivo CSV de vetados no encontrado")
    return FileResponse(
        path=str(_CSV_VETADOS),
        media_type="text/csv; charset=utf-8",
        filename="vetados_excluidos_tcs_simulados.csv",
    )


@router.get("/descargas/reporte_exclusiones_ag05.csv")
def descargar_reporte_ag05(request: Request) -> Response:
    _usuario(request)
    if not _CSV_REPORTE_AG05.exists():
        raise NoEncontradoError("Archivo CSV de reporte AG-05 no encontrado")
    return FileResponse(
        path=str(_CSV_REPORTE_AG05),
        media_type="text/csv; charset=utf-8",
        filename="reporte_exclusiones_oficial_tcs.csv",
    )


@router.get("/descargas/convocatorias-demo.zip")
def descargar_convocatorias_demo(request: Request) -> Response:
    _usuario(request)
    ruta_zip = Path("descargas_talento/06_Convocatorias_Demo.zip")
    if not ruta_zip.exists():
        raise NoEncontradoError("Archivo ZIP de convocatorias no encontrado")
    return FileResponse(
        path=str(ruta_zip),
        media_type="application/zip",
        filename="convocatorias_tcs_demo.zip",
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
