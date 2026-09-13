"""Casos de uso coordinados del monolito modular."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Protocol, cast

from talentia.ai.agents.exclusiones import EntradaExclusion, clasificar_exclusiones, generar_csv
from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL
from talentia.modules.candidates.domain.modelos import (
    Candidato,
    EstadoCandidato,
    ResolucionIdentidad,
    ResultadoIdentidad,
    normalizar_correo,
    normalizar_documento,
    tokens_nombre,
    ultimos_nueve_telefono,
)
from talentia.platform.security.contrasenas import verificar_contrasena
from talentia.shared.application.errores import (
    ConflictoError,
    DecisionNegocioPendienteError,
    EntradaInvalidaError,
    NoAutorizadoError,
    NoEncontradoError,
    ProhibidoError,
)
from talentia.shared.application.puertos import FabricaUnidadTrabajo
from talentia.shared.domain.modelos import UsuarioActual, nuevo_id


class AlmacenDocumentos(Protocol):
    def guardar(self, nombre: str, contenido: bytes) -> str: ...


class LectorLotes(Protocol):
    def __call__(
        self, nombre: str, contenido: bytes, maximo: int = 5000
    ) -> list[dict[str, object]]: ...


def _exigir_permiso(usuario: UsuarioActual, permiso: str) -> None:
    if not usuario.tiene_permiso(permiso, PERMISOS_POR_ROL):
        raise ProhibidoError(f"Falta el permiso {permiso}")


def _exigir_cliente(usuario: UsuarioActual, cliente_id: str) -> None:
    if not usuario.puede_acceder_cliente(cliente_id):
        raise ProhibidoError("El recurso pertenece a otro cliente")


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _huella_preflight(datos: dict[str, object]) -> str:
    partes = [
        _texto(datos.get("cliente_id")),
        normalizar_documento(_texto(datos.get("documento"))) or "",
        normalizar_correo(_texto(datos.get("correo"))) or "",
        ultimos_nueve_telefono(_texto(datos.get("telefono"))) or "",
        "|".join(tokens_nombre(_texto(datos.get("nombre_completo")))),
    ]
    return hashlib.sha256("\x1f".join(partes).encode()).hexdigest()


class ServicioTalentIA:
    def __init__(
        self,
        fabrica_unidad: FabricaUnidadTrabajo,
        almacen_documentos: AlmacenDocumentos | None = None,
        lector_lotes: LectorLotes | None = None,
        maximo_documento_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._fabrica = fabrica_unidad
        self._almacen = almacen_documentos
        self._lector_lotes = lector_lotes
        self._maximo_documento_bytes = maximo_documento_bytes

    def autenticar(self, correo: str, contrasena: str, correlacion_id: str) -> UsuarioActual:
        with self._fabrica() as unidad:
            datos = unidad.datos.buscar_usuario(correo)
            valido = bool(
                datos
                and datos.get("activo")
                and verificar_contrasena(contrasena, str(datos["hash_contrasena"]))
            )
            unidad.datos.registrar_evento(
                cliente_id=None,
                actor_id=str(datos["id"]) if datos else None,
                accion="autenticacion.exitosa" if valido else "autenticacion.fallida",
                recurso_tipo="sesion",
                recurso_id=None,
                detalle={"correo_hash": hashlib.sha256(correo.casefold().encode()).hexdigest()},
                correlacion_id=correlacion_id,
            )
            if not valido or datos is None:
                raise NoAutorizadoError("Credenciales invalidas")
            return UsuarioActual(
                id=str(datos["id"]),
                correo=str(datos["correo"]),
                roles=frozenset(str(rol) for rol in cast(list[object], datos["roles"])),
                clientes=frozenset(
                    str(cliente) for cliente in cast(list[object], datos["clientes"])
                ),
            )

    def comprobar_identidad(
        self, usuario: UsuarioActual, datos: dict[str, object], correlacion_id: str
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "candidatos:escribir")
        cliente_id = _texto(datos.get("cliente_id"))
        _exigir_cliente(usuario, cliente_id)
        documento = normalizar_documento(_texto(datos.get("documento")))
        correo = normalizar_correo(_texto(datos.get("correo")))
        telefono = ultimos_nueve_telefono(_texto(datos.get("telefono")))
        nombre = tokens_nombre(_texto(datos.get("nombre_completo")))
        if not any((documento, correo, telefono, nombre)):
            raise EntradaInvalidaError("Se requiere al menos un dato de identidad")
        with self._fabrica() as unidad:
            coincidencias = unidad.datos.buscar_identidad(
                cliente_id, documento, correo, telefono, nombre
            )
            exactas = [
                item
                for item in coincidencias
                if item["criterio"] in {"documento", "correo", "telefono"}
            ]
            if exactas:
                resolucion = ResolucionIdentidad(
                    ResultadoIdentidad.EXACTA,
                    str(exactas[0]["criterio"]),
                    tuple(str(item["id"]) for item in exactas),
                )
            elif coincidencias:
                resolucion = ResolucionIdentidad(
                    ResultadoIdentidad.BLOQUEADA,
                    "nombre: BIZ-004 pendiente",
                    tuple(str(item["id"]) for item in coincidencias),
                )
            else:
                resolucion = ResolucionIdentidad(ResultadoIdentidad.NINGUNA, "sin_coincidencias")
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="identidad.comprobada",
                recurso_tipo="identidad",
                recurso_id=None,
                detalle={
                    "resultado": resolucion.resultado.value,
                    "criterio": resolucion.criterio,
                    "coincidencias": len(resolucion.candidato_ids),
                },
                correlacion_id=correlacion_id,
            )
        return {**asdict(resolucion), "preflight_id": _huella_preflight(datos)}

    def registrar_candidato(
        self,
        usuario: UsuarioActual,
        datos: dict[str, object],
        preflight_id: str,
        correlacion_id: str,
    ) -> Candidato:
        _exigir_permiso(usuario, "candidatos:escribir")
        cliente_id = _texto(datos.get("cliente_id"))
        _exigir_cliente(usuario, cliente_id)
        identidad = {
            "cliente_id": cliente_id,
            "documento": datos.get("documento"),
            "correo": datos.get("correo"),
            "telefono": datos.get("telefono"),
            "nombre_completo": f"{datos.get('nombres', '')} {datos.get('apellidos', '')}",
        }
        if preflight_id != _huella_preflight(identidad):
            raise EntradaInvalidaError("Debe repetir la comprobacion de identidad")
        if datos.get("bgc") is not None or datos.get("deuda_equifax") is not None:
            raise DecisionNegocioPendienteError("BIZ-010 impide almacenar BGC o Equifax")
        with self._fabrica() as unidad:
            coincidencias = unidad.datos.buscar_identidad(
                cliente_id,
                normalizar_documento(_texto(datos.get("documento"))),
                normalizar_correo(_texto(datos.get("correo"))),
                ultimos_nueve_telefono(_texto(datos.get("telefono"))),
                tokens_nombre(str(identidad["nombre_completo"])),
            )
            if coincidencias:
                raise ConflictoError("La identidad coincide con una persona existente")
            candidato = Candidato(
                cliente_id=cliente_id,
                nombres=_texto(datos.get("nombres")),
                apellidos=_texto(datos.get("apellidos")),
                tipo_documento=str(datos["tipo_documento"])
                if datos.get("tipo_documento")
                else None,
                documento_normalizado=normalizar_documento(_texto(datos.get("documento"))),
                correo=normalizar_correo(_texto(datos.get("correo"))),
                telefono=_texto(datos.get("telefono")) or None,
                fecha_nacimiento=cast(date, datos.get("fecha_nacimiento"))
                if isinstance(datos.get("fecha_nacimiento"), date)
                else None,
                ubicacion=_texto(datos.get("ubicacion")) or None,
                fuente=_texto(datos.get("fuente")) or None,
                reclutador=_texto(datos.get("reclutador")) or None,
                perfil_solicitado=_texto(datos.get("perfil_solicitado")) or None,
                conocimiento_tecnico=_texto(datos.get("conocimiento_tecnico")) or None,
                disponibilidad=_texto(datos.get("disponibilidad")) or None,
                expectativa_salarial=Decimal(str(datos["expectativa_salarial"]))
                if datos.get("expectativa_salarial") is not None
                else None,
                ctc_rol=Decimal(str(datos["ctc_rol"]))
                if datos.get("ctc_rol") is not None
                else None,
                etiquetas=list(cast(list[str], datos.get("etiquetas", []))),
            )
            unidad.datos.agregar_candidato(candidato)
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="candidato.registrado",
                recurso_tipo="candidato",
                recurso_id=candidato.id,
                detalle={"campos": sorted(datos), "version": candidato.version},
                correlacion_id=correlacion_id,
            )
            return candidato

    def buscar_candidatos(
        self,
        usuario: UsuarioActual,
        texto: str = "",
        limite: int = 50,
        cursor: str | None = None,
    ) -> list[Candidato]:
        _exigir_permiso(usuario, "candidatos:leer")
        with self._fabrica() as unidad:
            return unidad.datos.buscar_candidatos(
                usuario.clientes if "administrador" not in usuario.roles else frozenset(),
                texto,
                min(max(limite, 1), 100),
                cursor,
            )

    def obtener_candidato(
        self, usuario: UsuarioActual, candidato_id: str, correlacion_id: str
    ) -> Candidato:
        _exigir_permiso(usuario, "candidatos:leer")
        with self._fabrica() as unidad:
            candidato = unidad.datos.obtener_candidato(candidato_id)
            if not candidato:
                raise NoEncontradoError("Candidato no encontrado")
            _exigir_cliente(usuario, candidato.cliente_id)
            unidad.datos.registrar_evento(
                cliente_id=candidato.cliente_id,
                actor_id=usuario.id,
                accion="candidato.consultado_completo",
                recurso_tipo="candidato",
                recurso_id=candidato.id,
                detalle={},
                correlacion_id=correlacion_id,
            )
            return candidato

    def actualizar_candidato(
        self,
        usuario: UsuarioActual,
        candidato_id: str,
        version: int,
        cambios: dict[str, object],
        correlacion_id: str,
    ) -> Candidato:
        _exigir_permiso(usuario, "candidatos:escribir")
        prohibidos = {
            "id",
            "cliente_id",
            "edad",
            "variacion_ctc_porcentaje",
            "bgc",
            "deuda_equifax",
        }
        if prohibidos.intersection(cambios):
            raise EntradaInvalidaError(
                "Se intentaron modificar campos derivados, sensibles o inmutables"
            )
        with self._fabrica() as unidad:
            candidato = unidad.datos.obtener_candidato(candidato_id)
            if not candidato:
                raise NoEncontradoError("Candidato no encontrado")
            _exigir_cliente(usuario, candidato.cliente_id)
            for campo, valor in cambios.items():
                if not hasattr(candidato, campo):
                    raise EntradaInvalidaError(f"Campo desconocido: {campo}")
                if campo in {"expectativa_salarial", "ctc_rol"} and valor is not None:
                    valor = Decimal(str(valor))
                setattr(candidato, campo, valor)
            actualizado = unidad.datos.actualizar_candidato(candidato, version, set(cambios))
            unidad.datos.registrar_evento(
                cliente_id=candidato.cliente_id,
                actor_id=usuario.id,
                accion="candidato.actualizado",
                recurso_tipo="candidato",
                recurso_id=candidato.id,
                detalle={
                    "campos": sorted(cambios),
                    "version_anterior": actualizado.version - 1,
                    "version_solicitada": version,
                },
                correlacion_id=correlacion_id,
            )
            return actualizado

    def cambiar_estado_candidato(
        self,
        usuario: UsuarioActual,
        candidato_id: str,
        destino: EstadoCandidato,
        motivo: str | None,
        correlacion_id: str,
    ) -> Candidato:
        if destino in {EstadoCandidato.NO_APTO, EstadoCandidato.BLACKLIST}:
            raise DecisionNegocioPendienteError("BIZ-001/002/003 impide esta transicion")
        candidato = self.obtener_candidato(usuario, candidato_id, correlacion_id)
        if candidato.estado in {EstadoCandidato.NO_APTO, EstadoCandidato.BLACKLIST}:
            raise DecisionNegocioPendienteError("BIZ-002/003 impide reabrir este estado")
        return self.actualizar_candidato(
            usuario,
            candidato_id,
            candidato.version,
            {"estado": destino},
            correlacion_id,
        )

    def traza_candidato(
        self, usuario: UsuarioActual, candidato_id: str, limite: int = 50
    ) -> dict[str, object]:
        candidato = self.obtener_candidato(usuario, candidato_id, nuevo_id())
        with self._fabrica() as unidad:
            eventos = unidad.datos.traza_candidato(candidato_id, min(limite, 100))
        resumen = (
            f"{candidato.nombre_completo}: estado {candidato.estado.value}; {len(eventos)} eventos"
        )
        return {"resumen": resumen, "eventos": eventos}

    def crear_perfil(
        self, usuario: UsuarioActual, datos: dict[str, object], correlacion_id: str
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "perfiles:escribir")
        cliente_id = str(datos["cliente_id"])
        _exigir_cliente(usuario, cliente_id)
        with self._fabrica() as unidad:
            perfil = unidad.datos.crear_perfil(
                {
                    "cliente_id": cliente_id,
                    "codigo": str(datos["codigo"]),
                    "titulo": str(datos["titulo"]),
                    "activo": True,
                }
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="perfil.creado",
                recurso_tipo="perfil",
                recurso_id=str(perfil["id"]),
                detalle={"codigo": perfil["codigo"]},
                correlacion_id=correlacion_id,
            )
            return perfil

    def crear_version_perfil(
        self, usuario: UsuarioActual, perfil_id: str, datos: dict[str, object]
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "perfiles:escribir")
        with self._fabrica() as unidad:
            return unidad.datos.crear_version_perfil(
                {
                    "perfil_id": perfil_id,
                    "requisitos": list(cast(list[dict[str, object]], datos.get("requisitos", []))),
                    "ctc": Decimal(str(datos["ctc"])) if datos.get("ctc") else None,
                    "publicado": bool(datos.get("publicado", False)),
                }
            )

    def crear_postulacion(
        self, usuario: UsuarioActual, datos: dict[str, object], correlacion_id: str
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "postulaciones:escribir")
        cliente_id = str(datos["cliente_id"])
        _exigir_cliente(usuario, cliente_id)
        candidato = self.obtener_candidato(usuario, str(datos["candidato_id"]), correlacion_id)
        if candidato.cliente_id != cliente_id:
            raise ProhibidoError("Candidato y postulacion pertenecen a clientes distintos")
        clave = hashlib.sha256(
            f"{cliente_id}:{datos['candidato_id']}:{datos['version_perfil_id']}".encode()
        ).hexdigest()[:40]
        with self._fabrica() as unidad:
            postulacion = unidad.datos.crear_postulacion(
                {
                    "cliente_id": cliente_id,
                    "candidato_id": str(datos["candidato_id"]),
                    "version_perfil_id": str(datos["version_perfil_id"]),
                    "fuente": str(datos.get("fuente", "directa")),
                    "estado": "nueva",
                    "clave_idempotencia": clave,
                }
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="postulacion.creada",
                recurso_tipo="postulacion",
                recurso_id=str(postulacion["id"]),
                detalle={"fuente": datos.get("fuente", "directa")},
                correlacion_id=correlacion_id,
            )
            return postulacion

    def adjuntar_documento(
        self,
        usuario: UsuarioActual,
        candidato_id: str,
        nombre: str,
        tipo_mime: str,
        contenido: bytes,
        correlacion_id: str,
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "documentos:escribir")
        candidato = self.obtener_candidato(usuario, candidato_id, correlacion_id)
        if not contenido or len(contenido) > self._maximo_documento_bytes:
            raise EntradaInvalidaError("Tamano de documento invalido")
        firmas = {
            "application/pdf": contenido.startswith(b"%PDF"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
                contenido.startswith(b"PK")
            ),
        }
        if tipo_mime not in firmas or not firmas[tipo_mime]:
            raise EntradaInvalidaError("Tipo o firma de archivo no permitida")
        if self._almacen is None:
            raise EntradaInvalidaError("Almacen de documentos no configurado")
        huella = hashlib.sha256(contenido).hexdigest()
        nombre_seguro = re.sub(r"[^A-Za-z0-9._-]", "_", nombre)
        ruta = self._almacen.guardar(f"{nuevo_id()}-{nombre_seguro}", contenido)
        with self._fabrica() as unidad:
            documento = unidad.datos.guardar_documento(
                {
                    "cliente_id": candidato.cliente_id,
                    "candidato_id": candidato.id,
                    "nombre_original": nombre,
                    "tipo_mime": tipo_mime,
                    "hash_sha256": huella,
                    "ruta_almacenamiento": ruta,
                    "tamano_bytes": len(contenido),
                }
            )
            unidad.datos.registrar_evento(
                cliente_id=candidato.cliente_id,
                actor_id=usuario.id,
                accion="documento.adjuntado",
                recurso_tipo="documento",
                recurso_id=str(documento["id"]),
                detalle={"tipo_mime": tipo_mime, "tamano": len(contenido)},
                correlacion_id=correlacion_id,
            )
            return documento

    def solicitar_evaluacion(
        self, usuario: UsuarioActual, datos: dict[str, object]
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "evaluaciones:solicitar")
        cliente_id = str(datos["cliente_id"])
        _exigir_cliente(usuario, cliente_id)
        clave = str(datos.get("clave_idempotencia") or nuevo_id())
        with self._fabrica() as unidad:
            return unidad.datos.crear_trabajo(
                {
                    "cliente_id": cliente_id,
                    "tipo": "evaluacion",
                    "estado": "pendiente",
                    "carga": dict(datos),
                    "resultado": None,
                    "error": None,
                    "intentos": 0,
                    "max_intentos": 3,
                    "clave_idempotencia": clave,
                }
            )

    def obtener_trabajo(self, usuario: UsuarioActual, trabajo_id: str) -> dict[str, object]:
        with self._fabrica() as unidad:
            trabajo = unidad.datos.obtener_trabajo(trabajo_id)
            if not trabajo:
                raise NoEncontradoError("Trabajo no encontrado")
            _exigir_cliente(usuario, str(trabajo["cliente_id"]))
            return trabajo

    def obtener_metricas(self, usuario: UsuarioActual) -> dict[str, object]:
        _exigir_permiso(usuario, "reportes:leer")
        with self._fabrica() as unidad:
            return unidad.datos.metricas(
                usuario.clientes if "administrador" not in usuario.roles else frozenset()
            )

    def preparar_lote(
        self,
        usuario: UsuarioActual,
        cliente_id: str,
        tipo: str,
        nombre: str,
        contenido: bytes,
        clave_idempotencia: str,
        correlacion_id: str,
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "lotes:escribir")
        _exigir_cliente(usuario, cliente_id)
        if self._lector_lotes is None:
            raise EntradaInvalidaError("Lector de lotes no configurado")
        filas = self._lector_lotes(nombre, contenido)
        huella = hashlib.sha256(contenido).hexdigest()
        with self._fabrica() as unidad:
            lote = unidad.datos.crear_lote(
                {
                    "cliente_id": cliente_id,
                    "tipo": tipo,
                    "hash_archivo": huella,
                    "estado": "staging",
                    "clave_idempotencia": clave_idempotencia,
                },
                filas,
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="lote.preparado",
                recurso_tipo="lote",
                recurso_id=str(lote["id"]),
                detalle={"tipo": tipo, "filas": len(filas)},
                correlacion_id=correlacion_id,
            )
            return lote

    def obtener_lote(self, usuario: UsuarioActual, lote_id: str) -> dict[str, object]:
        _exigir_permiso(usuario, "lotes:escribir")
        with self._fabrica() as unidad:
            lote = unidad.datos.obtener_lote(lote_id)
            if not lote:
                raise NoEncontradoError("Lote no encontrado")
            _exigir_cliente(usuario, str(lote["cliente_id"]))
            return lote

    def confirmar_lote(
        self, usuario: UsuarioActual, lote_id: str, correlacion_id: str
    ) -> dict[str, object]:
        lote = self.obtener_lote(usuario, lote_id)
        with self._fabrica() as unidad:
            resultado = unidad.datos.confirmar_lote(lote_id)
            unidad.datos.registrar_evento(
                cliente_id=str(lote["cliente_id"]),
                actor_id=usuario.id,
                accion="lote.confirmado",
                recurso_tipo="lote",
                recurso_id=lote_id,
                detalle={"tipo": lote["tipo"]},
                correlacion_id=correlacion_id,
            )
            return resultado

    def crear_reporte_exclusion(
        self,
        usuario: UsuarioActual,
        cliente_id: str,
        filtros: dict[str, object],
        correlacion_id: str,
    ) -> dict[str, object]:
        _exigir_permiso(usuario, "reportes:leer")
        _exigir_cliente(usuario, cliente_id)
        with self._fabrica() as unidad:
            registros = unidad.datos.candidatos_para_exclusion(cliente_id)
            entradas = clasificar_exclusiones(registros)
            _contenido, huella = generar_csv(entradas)
            reporte = unidad.datos.guardar_reporte_exclusion(
                cliente_id,
                filtros,
                [
                    {
                        "documento": entrada.documento,
                        "motivo_generico": entrada.motivo_generico,
                    }
                    for entrada in entradas
                ],
                huella,
            )
            unidad.datos.registrar_evento(
                cliente_id=cliente_id,
                actor_id=usuario.id,
                accion="exclusion.exportada",
                recurso_tipo="reporte_exclusion",
                recurso_id=str(reporte["id"]),
                detalle={"total": len(entradas), "hash": huella},
                correlacion_id=correlacion_id,
            )
            return reporte

    def descargar_reporte_exclusion(self, usuario: UsuarioActual, reporte_id: str) -> bytes:
        _exigir_permiso(usuario, "reportes:leer")
        with self._fabrica() as unidad:
            reporte = unidad.datos.obtener_reporte_exclusion(reporte_id)
            if not reporte:
                raise NoEncontradoError("Reporte no encontrado")
            _exigir_cliente(usuario, str(reporte["cliente_id"]))
            entradas_crudas = cast(list[dict[str, str]], reporte["entradas"])
            entradas = tuple(
                EntradaExclusion("", item["documento"], item["motivo_generico"])
                for item in entradas_crudas
            )
            contenido, huella = generar_csv(entradas)
            if huella != reporte["hash_contenido"]:
                raise ConflictoError("El reporte no supera la verificacion de integridad")
            return contenido
