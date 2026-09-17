"""API HTTP; traduce contratos y delega toda regla a aplicacion."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile
from fastapi.responses import Response

from talentia.modules.candidates.domain.modelos import EstadoCandidato
from talentia.platform.security.contrasenas import FirmadorSesion, nuevo_csrf
from talentia.shared.application.errores import NoAutorizadoError
from talentia.shared.application.servicio_principal import ServicioTalentIA
from talentia.shared.domain.modelos import UsuarioActual, nuevo_id
from talentia.web.schemas import (
    ActualizacionCandidato,
    ActualizacionReporteExclusion,
    AltaCandidato,
    AltaConvocatoria,
    AltaPerfil,
    AltaPostulacion,
    AltaVersionPerfil,
    AsignacionCliente,
    AsignacionReclutadorConvocatoria,
    AsignacionRol,
    CambioContrasena,
    CierreConvocatoria,
    ComprobacionExcolaborador,
    ComprobacionIdentidad,
    CorreccionFilaLote,
    Credenciales,
    MapeoLote,
    RevisionEvaluacion,
    SolicitudEvaluacion,
    SolicitudReporteExclusion,
    TransicionCandidato,
    TransicionPostulacion,
)

router = APIRouter(prefix="/api/v1")


def servicio(request: Request) -> ServicioTalentIA:
    return cast(ServicioTalentIA, request.app.state.servicio)


def firmador(request: Request) -> FirmadorSesion:
    return cast(FirmadorSesion, request.app.state.firmador)


def correlacion(x_correlation_id: str | None = Header(default=None)) -> str:
    return x_correlation_id or nuevo_id()


def usuario_actual(
    request: Request,
    firmador_actual: Annotated[FirmadorSesion, Depends(firmador)],
    authorization: str | None = Header(default=None),
) -> UsuarioActual:
    token = request.cookies.get("talentia_session")
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        raise NoAutorizadoError("Autenticacion requerida")
    datos = firmador_actual.leer(token)
    roles = cast(list[object], datos.get("roles", []))
    clientes = cast(list[object], datos.get("clientes", []))
    usuario = UsuarioActual(
        id=str(datos["sub"]),
        correo=str(datos["correo"]),
        roles=frozenset(str(rol) for rol in roles),
        clientes=frozenset(str(cliente) for cliente in clientes),
        sesion_version=int(str(datos.get("sv", 0))),
    )
    servicio(request).validar_sesion(usuario)
    return usuario


UsuarioDep = Annotated[UsuarioActual, Depends(usuario_actual)]
ServicioDep = Annotated[ServicioTalentIA, Depends(servicio)]
CorrelacionDep = Annotated[str, Depends(correlacion)]


@router.get("/access-management")
def listar_accesos(usuario: UsuarioDep, servicio_actual: ServicioDep) -> dict[str, object]:
    return servicio_actual.listar_accesos(usuario)


@router.post("/users/{usuario_id}/role-assignments")
def asignar_rol(
    usuario_id: str,
    entrada: AsignacionRol,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.asignar_rol(
        usuario, usuario_id, entrada.rol, entrada.asignar, correlacion_id
    )


@router.post("/users/{usuario_id}/client-assignments")
def asignar_cliente(
    usuario_id: str,
    entrada: AsignacionCliente,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.asignar_cliente(
        usuario, usuario_id, entrada.cliente_id, entrada.asignar, correlacion_id
    )


@router.post("/auth/login")
def iniciar_sesion(
    entrada: Credenciales,
    servicio_actual: ServicioDep,
    firmador_actual: Annotated[FirmadorSesion, Depends(firmador)],
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    usuario = servicio_actual.autenticar(entrada.correo, entrada.contrasena, correlacion_id)
    csrf = nuevo_csrf()
    token = firmador_actual.crear(
        {
            "sub": usuario.id,
            "correo": usuario.correo,
            "roles": sorted(usuario.roles),
            "clientes": sorted(usuario.clientes),
            "csrf": csrf,
            "sv": usuario.sesion_version,
        }
    )
    return {"access_token": token, "token_type": "bearer", "csrf_token": csrf}


@router.post("/auth/logout")
def cerrar_sesion(
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, bool]:
    servicio_actual.revocar_sesiones(usuario, correlacion_id)
    return {"cerrada": True}


@router.post("/auth/change-password")
def cambiar_contrasena(
    entrada: CambioContrasena,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, bool]:
    servicio_actual.cambiar_contrasena(
        usuario, entrada.contrasena_actual, entrada.contrasena_nueva, correlacion_id
    )
    return {"actualizada": True, "sesiones_revocadas": True}


@router.post("/candidates/identity-checks")
def comprobar_identidad(
    entrada: ComprobacionIdentidad,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.comprobar_identidad(usuario, entrada.model_dump(), correlacion_id)


@router.post("/candidates", status_code=201)
def registrar_candidato(
    entrada: AltaCandidato,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    datos = entrada.model_dump(exclude={"preflight_id"})
    candidato = servicio_actual.registrar_candidato(
        usuario, datos, entrada.preflight_id, correlacion_id
    )
    return asdict(candidato)


@router.get("/candidates")
def buscar_candidatos(
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    q: str = "",
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, object]:
    candidatos = servicio_actual.buscar_candidatos(usuario, q, limit, cursor)
    return {
        "items": [asdict(candidato) for candidato in candidatos],
        "next_cursor": candidatos[-1].id if len(candidatos) == limit else None,
    }


@router.get("/candidates/{candidato_id}")
def obtener_candidato(
    candidato_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return asdict(servicio_actual.obtener_candidato(usuario, candidato_id, correlacion_id))


@router.patch("/candidates/{candidato_id}")
def actualizar_candidato(
    candidato_id: str,
    entrada: ActualizacionCandidato,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return asdict(
        servicio_actual.actualizar_candidato(
            usuario,
            candidato_id,
            entrada.version,
            entrada.cambios,
            correlacion_id,
        )
    )


@router.post("/candidates/{candidato_id}/transitions")
def cambiar_estado(
    candidato_id: str,
    entrada: TransicionCandidato,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return asdict(
        servicio_actual.cambiar_estado_candidato(
            usuario,
            candidato_id,
            EstadoCandidato(entrada.destino),
            entrada.motivo,
            correlacion_id,
        )
    )


@router.get("/candidates/{candidato_id}/trace")
def traza_candidato(
    candidato_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    limit: int = 50,
    tipo: str | None = None,
    desde: datetime | None = None,
) -> dict[str, object]:
    return servicio_actual.traza_candidato(usuario, candidato_id, limit, tipo, desde)


@router.post("/candidates/{candidato_id}/resumes", status_code=201)
async def adjuntar_cv(
    candidato_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
    archivo: Annotated[UploadFile, File()],
) -> dict[str, object]:
    contenido = await archivo.read()
    return servicio_actual.adjuntar_documento(
        usuario,
        candidato_id,
        archivo.filename or "cv",
        archivo.content_type or "application/octet-stream",
        contenido,
        correlacion_id,
    )


@router.post("/documents/{documento_id}/extraction")
def procesar_documento(
    documento_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.procesar_documento(usuario, documento_id, correlacion_id)


@router.get("/documents/{documento_id}/extraction")
def obtener_extraccion_documento(
    documento_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
) -> dict[str, object]:
    return servicio_actual.obtener_extraccion_documento(usuario, documento_id)


@router.post("/job-profiles", status_code=201)
def crear_perfil(
    entrada: AltaPerfil,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.crear_perfil(usuario, entrada.model_dump(), correlacion_id)


@router.post("/job-profiles/{perfil_id}/versions", status_code=201)
def crear_version_perfil(
    perfil_id: str,
    entrada: AltaVersionPerfil,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.crear_version_perfil(
        usuario, perfil_id, entrada.model_dump(), correlacion_id
    )


@router.post("/campaigns", status_code=201)
def crear_convocatoria(
    entrada: AltaConvocatoria,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.crear_convocatoria(usuario, entrada.model_dump(), correlacion_id)


@router.get("/campaigns")
def listar_convocatorias(
    cliente_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    limit: int = 100,
    cursor: str | None = None,
) -> list[dict[str, object]]:
    return servicio_actual.listar_convocatorias(usuario, cliente_id, limit, cursor)


@router.get("/campaigns/{convocatoria_id}")
def obtener_convocatoria(
    convocatoria_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
) -> dict[str, object]:
    return servicio_actual.obtener_convocatoria(usuario, convocatoria_id)


@router.post("/campaigns/{convocatoria_id}/recruiters")
def asignar_reclutador_convocatoria(
    convocatoria_id: str,
    entrada: AsignacionReclutadorConvocatoria,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.asignar_reclutador_convocatoria(
        usuario, convocatoria_id, entrada.usuario_id, entrada.asignar, correlacion_id
    )


@router.get("/campaigns/{convocatoria_id}/close-preview")
def vista_previa_cierre_convocatoria(
    convocatoria_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
) -> dict[str, object]:
    return servicio_actual.vista_previa_cierre_convocatoria(usuario, convocatoria_id)


@router.post("/campaigns/{convocatoria_id}/close")
def cerrar_convocatoria(
    convocatoria_id: str,
    entrada: CierreConvocatoria,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.cerrar_convocatoria(
        usuario, convocatoria_id, entrada.version, entrada.motivo, correlacion_id
    )


@router.post("/applications", status_code=201)
def crear_postulacion(
    entrada: AltaPostulacion,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.crear_postulacion(usuario, entrada.model_dump(), correlacion_id)


@router.post("/applications/{postulacion_id}/transitions")
def transicionar_postulacion(
    postulacion_id: str,
    entrada: TransicionPostulacion,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.transicionar_postulacion(
        usuario, postulacion_id, entrada.model_dump(), correlacion_id
    )


@router.post("/applications/{postulacion_id}/evaluation-jobs", status_code=202)
def solicitar_evaluacion(
    postulacion_id: str,
    entrada: SolicitudEvaluacion,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    datos = entrada.model_dump()
    datos["postulacion_id"] = postulacion_id
    return servicio_actual.solicitar_evaluacion(usuario, datos, correlacion_id)


@router.get("/jobs/{trabajo_id}")
def obtener_trabajo(
    trabajo_id: str, usuario: UsuarioDep, servicio_actual: ServicioDep
) -> dict[str, object]:
    return servicio_actual.obtener_trabajo(usuario, trabajo_id)


@router.get("/evaluations/{evaluacion_id}")
def obtener_evaluacion(
    evaluacion_id: str, usuario: UsuarioDep, servicio_actual: ServicioDep
) -> dict[str, object]:
    return servicio_actual.obtener_evaluacion(usuario, evaluacion_id)


@router.post("/evaluations/{evaluacion_id}/reviews")
def registrar_revision(
    evaluacion_id: str,
    entrada: RevisionEvaluacion,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.registrar_revision(
        usuario, evaluacion_id, entrada.model_dump(), correlacion_id
    )


@router.get("/metrics/pilot")
def metricas_piloto(
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    cliente_id: str | None = None,
) -> dict[str, object]:
    return servicio_actual.obtener_metricas(usuario, desde, hasta, cliente_id)


@router.post("/import-batches", status_code=201)
async def preparar_lote(
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
    cliente_id: Annotated[str, Form()],
    tipo: Annotated[str, Form()],
    clave_idempotencia: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File()],
) -> dict[str, object]:
    return servicio_actual.preparar_lote(
        usuario,
        cliente_id,
        tipo,
        archivo.filename or "lote.csv",
        await archivo.read(),
        clave_idempotencia,
        correlacion_id,
    )


@router.get("/import-batches/{lote_id}")
def obtener_lote(
    lote_id: str, usuario: UsuarioDep, servicio_actual: ServicioDep
) -> dict[str, object]:
    return servicio_actual.obtener_lote(usuario, lote_id)


@router.patch("/import-batches/{lote_id}/mapping")
def aplicar_mapeo_lote(
    lote_id: str,
    entrada: MapeoLote,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.aplicar_mapeo_lote(usuario, lote_id, entrada.columnas, correlacion_id)


@router.patch("/import-batches/{lote_id}/rows/{numero}")
def corregir_fila_lote(
    lote_id: str,
    numero: int,
    entrada: CorreccionFilaLote,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.corregir_fila_lote(
        usuario, lote_id, numero, entrada.datos, correlacion_id
    )


@router.post("/import-batches/{lote_id}/confirm")
def confirmar_lote(
    lote_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.confirmar_lote(usuario, lote_id, correlacion_id)


@router.post("/import-batches/{lote_id}/cancel")
def cancelar_lote(
    lote_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.cancelar_lote(usuario, lote_id, correlacion_id)


@router.post("/former-employees/imports", status_code=201)
async def importar_excolaboradores(
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
    cliente_id: Annotated[str, Form()],
    clave_idempotencia: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File()],
) -> dict[str, object]:
    return servicio_actual.preparar_lote(
        usuario,
        cliente_id,
        "excolaboradores",
        archivo.filename or "excolaboradores.csv",
        await archivo.read(),
        clave_idempotencia,
        correlacion_id,
    )


@router.post("/exclusion-reports", status_code=201)
def crear_reporte_exclusion(
    entrada: SolicitudReporteExclusion,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.crear_reporte_exclusion(
        usuario, entrada.cliente_id, entrada.filtros, correlacion_id
    )


@router.post("/former-employees/checks")
def comprobar_excolaborador(
    entrada: ComprobacionExcolaborador,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.comprobar_excolaborador(
        usuario, entrada.cliente_id, entrada.documento, correlacion_id
    )


@router.get("/exclusion-reports/{reporte_id}")
def obtener_reporte_exclusion(
    reporte_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.obtener_reporte_exclusion(usuario, reporte_id, correlacion_id)


@router.patch("/exclusion-reports/{reporte_id}")
def actualizar_reporte_exclusion(
    reporte_id: str,
    entrada: ActualizacionReporteExclusion,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> dict[str, object]:
    return servicio_actual.actualizar_reporte_exclusion(
        usuario, reporte_id, entrada.filtros, correlacion_id
    )


@router.get("/exclusion-reports/{reporte_id}/download")
def descargar_reporte_exclusion(
    reporte_id: str,
    usuario: UsuarioDep,
    servicio_actual: ServicioDep,
    correlacion_id: CorrelacionDep,
) -> Response:
    return Response(
        servicio_actual.descargar_reporte_exclusion(usuario, reporte_id, correlacion_id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="exclusiones.csv"'},
    )
