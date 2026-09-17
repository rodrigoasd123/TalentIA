"""Casos de uso de convocatorias y selección bajo control humano."""

from __future__ import annotations

from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL
from talentia.modules.recruitment.domain.modelos import (
    Convocatoria,
    EstadoConvocatoria,
)
from talentia.shared.application.errores import (
    EntradaInvalidaError,
    NoEncontradoError,
    ProhibidoError,
)
from talentia.shared.application.puertos import FabricaUnidadTrabajo
from talentia.shared.domain.modelos import UsuarioActual, nuevo_id


def _exigir_permiso(usuario: UsuarioActual, permiso: str) -> None:
    if not usuario.tiene_permiso(permiso, PERMISOS_POR_ROL):
        raise ProhibidoError(f"Falta el permiso {permiso}")


def _exigir_cliente(usuario: UsuarioActual, cliente_id: str) -> None:
    if not usuario.puede_acceder_cliente(cliente_id):
        raise NoEncontradoError("Recurso no encontrado")


class ServicioConvocatorias:
    def __init__(self, fabrica: FabricaUnidadTrabajo) -> None:
        self._fabrica = fabrica

    def crear(
        self, usuario: UsuarioActual, datos: dict[str, object], correlacion_id: str
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "convocatorias:escribir")
        cliente_id = str(datos.get("cliente_id", ""))
        _exigir_cliente(usuario, cliente_id)
        version_id = str(datos.get("version_perfil_id", ""))
        codigo = str(datos.get("codigo", "")).strip()
        try:
            estado = EstadoConvocatoria(str(datos.get("estado", "borrador")))
            vacantes = int(str(datos.get("vacantes_total", 0)))
        except (ValueError, TypeError) as exc:
            raise EntradaInvalidaError("Estado o cantidad de vacantes invalido") from exc
        convocatoria = Convocatoria(
            cliente_id=cliente_id,
            version_perfil_id=version_id,
            codigo=codigo,
            vacantes_total=vacantes,
            fecha_apertura=datos.get("fecha_apertura"),  # type: ignore[arg-type]
            fecha_objetivo=datos.get("fecha_objetivo"),  # type: ignore[arg-type]
            estado=estado,
            motivo_cierre=(str(datos["motivo_cierre"]) if datos.get("motivo_cierre") else None),
        )
        try:
            convocatoria.validar()
        except ValueError as exc:
            raise EntradaInvalidaError(str(exc)) from exc
        with self._fabrica() as unidad:
            version = unidad.datos.obtener_version_perfil(version_id)
            if version is None or str(version["cliente_id"]) != cliente_id:
                raise NoEncontradoError("Version de perfil no encontrada")
            if not bool(version["publicado"]):
                raise EntradaInvalidaError("La convocatoria requiere una version publicada")
            resultado = unidad.datos.crear_convocatoria(
                {
                    "cliente_id": cliente_id,
                    "version_perfil_id": version_id,
                    "codigo": codigo,
                    "vacantes_total": vacantes,
                    "fecha_apertura": convocatoria.fecha_apertura,
                    "fecha_objetivo": convocatoria.fecha_objetivo,
                    "estado": estado.value,
                    "motivo_cierre": convocatoria.motivo_cierre,
                    "es_compatibilidad": False,
                }
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="convocatoria.creada",
                recurso_tipo="convocatoria",
                recurso_id=str(resultado["id"]),
                detalle={"codigo": codigo, "vacantes_total": vacantes, "estado": estado.value},
                correlacion_id=correlacion_id or nuevo_id(),
            )
            return resultado

    def obtener(self, usuario: UsuarioActual, convocatoria_id: str) -> dict[str, object]:
        _exigir_permiso(usuario, "convocatorias:leer")
        with self._fabrica() as unidad:
            convocatoria = unidad.datos.obtener_convocatoria(convocatoria_id)
            if convocatoria is None:
                raise NoEncontradoError("Convocatoria no encontrada")
            _exigir_cliente(usuario, str(convocatoria["cliente_id"]))
            convocatoria["resumen"] = unidad.datos.vista_previa_cierre(convocatoria_id)
            convocatoria["candidaturas"] = unidad.datos.listar_postulaciones_convocatoria(
                convocatoria_id
            )
            usuarios = unidad.datos.listar_accesos().get("usuarios", [])
            convocatoria["reclutadores_disponibles"] = (
                [
                    {
                        "id": item["id"],
                        "nombre": item["nombre"],
                        "correo": item["correo"],
                    }
                    for item in usuarios
                    if isinstance(item, dict)
                    and bool(item.get("activo", True))
                    and "reclutador" in item.get("roles", [])
                    and str(convocatoria["cliente_id"]) in item.get("clientes", [])
                ]
                if isinstance(usuarios, list)
                else []
            )
            return convocatoria

    def listar(
        self,
        usuario: UsuarioActual,
        cliente_id: str,
        limite: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, object]]:
        _exigir_permiso(usuario, "convocatorias:leer")
        _exigir_cliente(usuario, cliente_id)
        with self._fabrica() as unidad:
            return unidad.datos.listar_convocatorias(
                frozenset({cliente_id}), cliente_id, min(max(limite, 1), 100), cursor
            )

    def asignar_reclutador(
        self,
        usuario: UsuarioActual,
        convocatoria_id: str,
        reclutador_id: str,
        asignar: bool,
        correlacion_id: str,
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "convocatorias:asignar")
        with self._fabrica() as unidad:
            convocatoria = unidad.datos.obtener_convocatoria(convocatoria_id)
            if convocatoria is None:
                raise NoEncontradoError("Convocatoria no encontrada")
            cliente_id = str(convocatoria["cliente_id"])
            _exigir_cliente(usuario, cliente_id)
            resultado = unidad.datos.asignar_reclutador_convocatoria(
                convocatoria_id, reclutador_id, usuario.id, asignar
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="convocatoria.reclutador_asignado",
                recurso_tipo="convocatoria",
                recurso_id=convocatoria_id,
                detalle={"usuario_id": reclutador_id, "asignado": asignar},
                correlacion_id=correlacion_id,
            )
            return resultado

    def transicionar(
        self,
        usuario: UsuarioActual,
        postulacion_id: str,
        datos: dict[str, object],
        correlacion_id: str,
    ) -> dict[str, object]:
        destino = str(datos.get("destino", ""))
        permiso = (
            "postulaciones:seleccionar"
            if destino in {"finalista", "backup"}
            else "postulaciones:transicionar"
        )
        _exigir_permiso(usuario, permiso)
        try:
            version = int(str(datos.get("version", 0)))
        except (ValueError, TypeError) as exc:
            raise EntradaInvalidaError("Version esperada invalida") from exc
        motivo = str(datos["motivo"]).strip() if datos.get("motivo") else None
        with self._fabrica() as unidad:
            postulacion = unidad.datos.obtener_postulacion(postulacion_id)
            if postulacion is None:
                raise NoEncontradoError("Postulacion no encontrada")
            cliente_id = str(postulacion["cliente_id"])
            _exigir_cliente(usuario, cliente_id)
            resultado = unidad.datos.transicionar_postulacion(
                postulacion_id, destino, motivo, version
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="postulacion.estado_cambiado",
                recurso_tipo="postulacion",
                recurso_id=postulacion_id,
                detalle={
                    "convocatoria_id": resultado["convocatoria_id"],
                    "estado_anterior": resultado["estado_anterior"],
                    "estado_nuevo": resultado["estado"],
                    "motivo": motivo,
                },
                correlacion_id=correlacion_id,
            )
            return resultado

    def vista_previa_cierre(
        self, usuario: UsuarioActual, convocatoria_id: str
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "postulaciones:seleccionar")
        with self._fabrica() as unidad:
            convocatoria = unidad.datos.obtener_convocatoria(convocatoria_id)
            if convocatoria is None:
                raise NoEncontradoError("Convocatoria no encontrada")
            _exigir_cliente(usuario, str(convocatoria["cliente_id"]))
            return unidad.datos.vista_previa_cierre(convocatoria_id)

    def cerrar(
        self,
        usuario: UsuarioActual,
        convocatoria_id: str,
        version: int,
        motivo: str,
        correlacion_id: str,
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "postulaciones:seleccionar")
        with self._fabrica() as unidad:
            convocatoria = unidad.datos.obtener_convocatoria(convocatoria_id)
            if convocatoria is None:
                raise NoEncontradoError("Convocatoria no encontrada")
            cliente_id = str(convocatoria["cliente_id"])
            _exigir_cliente(usuario, cliente_id)
            resultado = unidad.datos.cerrar_convocatoria(convocatoria_id, version, motivo.strip())
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="convocatoria.cerrada",
                recurso_tipo="convocatoria",
                recurso_id=convocatoria_id,
                detalle={
                    "motivo": motivo.strip(),
                    "backups_generados": resultado["backups_generados"],
                },
                correlacion_id=correlacion_id,
            )
            return resultado
