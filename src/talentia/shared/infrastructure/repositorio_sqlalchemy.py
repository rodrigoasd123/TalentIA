"""Adaptador SQLAlchemy para los puertos de aplicacion."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, true, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from talentia.modules.candidates.domain.modelos import (
    Candidato,
    EstadoCandidato,
    normalizar_correo,
    normalizar_documento,
    tokens_nombre,
    ultimos_nueve_telefono,
)
from talentia.modules.recruitment.domain.modelos import (
    EstadoPostulacion,
    TransicionPostulacionInvalidaError,
    validar_transicion_postulacion,
)
from talentia.platform.observabilidad.telemetria import registrar_metrica as persistir_metrica
from talentia.shared.application.errores import ConflictoError, EntradaInvalidaError
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.modelos_orm import (
    AsignacionReclutadorConvocatoriaModelo,
    AsignacionUsuarioClienteModelo,
    CandidatoModelo,
    ClienteModelo,
    ConvocatoriaModelo,
    CorreccionCampoModelo,
    DocumentoCandidatoModelo,
    EntradaExclusionModelo,
    EvaluacionModelo,
    EvaluacionRequisitoModelo,
    EventoAuditoriaModelo,
    EventoCandidatoModelo,
    EventoMetricaPilotoModelo,
    ExcolaboradorModelo,
    ExtraccionDocumentoModelo,
    FilaImportacionModelo,
    LoteExcolaboradoresModelo,
    LoteImportacionModelo,
    PerfilPuestoModelo,
    PostulacionModelo,
    ReporteExclusionModelo,
    RevisionHumanaModelo,
    RolModelo,
    SugerenciaCampoModelo,
    TrabajoAgenteModelo,
    UsuarioModelo,
    UsuarioRolModelo,
    VersionPerfilPuestoModelo,
)


def _candidato_desde_modelo(modelo: CandidatoModelo) -> Candidato:
    return Candidato(
        id=modelo.id,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
        version=modelo.version,
        cliente_id=modelo.cliente_id,
        nombres=modelo.nombres,
        apellidos=modelo.apellidos,
        tipo_documento=modelo.tipo_documento,
        documento_normalizado=modelo.documento_normalizado,
        correo=modelo.correo,
        telefono=modelo.telefono,
        fecha_nacimiento=modelo.fecha_nacimiento,
        ubicacion=modelo.ubicacion,
        fuente=modelo.fuente,
        reclutador=modelo.reclutador,
        perfil_solicitado=modelo.perfil_solicitado,
        conocimiento_tecnico=modelo.conocimiento_tecnico,
        disponibilidad=modelo.disponibilidad,
        expectativa_salarial=modelo.expectativa_salarial,
        ctc_rol=modelo.ctc_rol,
        estado=EstadoCandidato(modelo.estado),
        etiquetas=list(modelo.etiquetas or []),
    )


def _filtro_clientes(columna: Any, clientes: frozenset[str]) -> Any:
    return columna.in_(clientes) if clientes else true()


def _criterio_identidad(
    fila: Any,
    documento: str | None,
    correo: str | None,
    telefono: str | None,
    tokens: tuple[str, ...],
) -> str:
    nombre_tokens = tokens_nombre(f"{fila['nombres']} {fila['apellidos']}")
    if documento and fila["documento_normalizado"] == documento:
        return "documento"
    if correo and fila["correo"] == correo:
        return "correo"
    if telefono and ultimos_nueve_telefono(fila["telefono"]) == telefono:
        return "telefono"
    return "nombre" if tokens and nombre_tokens == tokens else ""


def _candidato_a_modelo(candidato: Candidato) -> CandidatoModelo:
    return CandidatoModelo(
        id=candidato.id,
        cliente_id=candidato.cliente_id,
        nombres=candidato.nombres,
        apellidos=candidato.apellidos,
        tipo_documento=candidato.tipo_documento,
        documento_normalizado=candidato.documento_normalizado,
        correo=candidato.correo,
        telefono=candidato.telefono,
        fecha_nacimiento=candidato.fecha_nacimiento,
        ubicacion=candidato.ubicacion,
        fuente=candidato.fuente,
        reclutador=candidato.reclutador,
        perfil_solicitado=candidato.perfil_solicitado,
        conocimiento_tecnico=candidato.conocimiento_tecnico,
        disponibilidad=candidato.disponibilidad,
        expectativa_salarial=candidato.expectativa_salarial,
        ctc_rol=candidato.ctc_rol,
        estado=candidato.estado.value,
        etiquetas=candidato.etiquetas,
        version=candidato.version,
        creado_en=candidato.creado_en,
        actualizado_en=candidato.actualizado_en,
    )


def _percentil(valores: list[float], percentil: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    indice = max(0, math.ceil(percentil * len(ordenados)) - 1)
    return ordenados[indice]


class RepositorioSqlalchemy:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def buscar_usuario(self, correo: str) -> dict[str, object] | None:
        usuario = self.sesion.scalar(
            select(UsuarioModelo).where(UsuarioModelo.correo == correo.strip().casefold())
        )
        if usuario is None:
            return None
        roles = self.sesion.scalars(
            select(RolModelo.codigo)
            .join(UsuarioRolModelo, UsuarioRolModelo.rol_id == RolModelo.id)
            .where(UsuarioRolModelo.usuario_id == usuario.id)
        ).all()
        clientes = self.sesion.scalars(
            select(AsignacionUsuarioClienteModelo.cliente_id).where(
                AsignacionUsuarioClienteModelo.usuario_id == usuario.id
            )
        ).all()
        return {
            "id": usuario.id,
            "correo": usuario.correo,
            "nombre": usuario.nombre,
            "hash_contrasena": usuario.hash_contrasena,
            "activo": usuario.activo,
            "intentos_fallidos": usuario.intentos_fallidos,
            "bloqueado_hasta": usuario.bloqueado_hasta,
            "contrasena_cambiada_en": usuario.contrasena_cambiada_en,
            "sesion_version": usuario.sesion_version,
            "roles": list(roles),
            "clientes": list(clientes),
        }

    def registrar_intento_autenticacion(
        self, usuario_id: str, exitoso: bool, maximos_intentos: int, minutos_bloqueo: int
    ) -> dict[str, object]:
        usuario = self.sesion.get(UsuarioModelo, usuario_id)
        if usuario is None:
            return {"bloqueado": False, "intentos_fallidos": 0}
        if exitoso:
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = None
        else:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= maximos_intentos:
                usuario.bloqueado_hasta = datetime.now(UTC) + timedelta(minutes=minutos_bloqueo)
        self.sesion.flush()
        return {
            "bloqueado": usuario.bloqueado_hasta is not None,
            "intentos_fallidos": usuario.intentos_fallidos,
        }

    def sesion_valida(self, usuario_id: str, sesion_version: int) -> bool:
        usuario = self.sesion.get(UsuarioModelo, usuario_id)
        return bool(usuario and usuario.activo and usuario.sesion_version == sesion_version)

    def revocar_sesiones(self, usuario_id: str) -> int:
        usuario = self.sesion.get(UsuarioModelo, usuario_id)
        if usuario is None:
            raise EntradaInvalidaError("Usuario inexistente")
        usuario.sesion_version += 1
        self.sesion.flush()
        return usuario.sesion_version

    def actualizar_contrasena(self, usuario_id: str, hash_nuevo: str) -> int:
        usuario = self.sesion.get(UsuarioModelo, usuario_id)
        if usuario is None:
            raise EntradaInvalidaError("Usuario inexistente")
        usuario.hash_contrasena = hash_nuevo
        usuario.contrasena_cambiada_en = datetime.now(UTC)
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        usuario.sesion_version += 1
        self.sesion.flush()
        return usuario.sesion_version

    def listar_accesos(self) -> dict[str, object]:
        usuarios = []
        for usuario in self.sesion.scalars(select(UsuarioModelo).order_by(UsuarioModelo.correo)):
            datos = self.buscar_usuario(usuario.correo)
            if datos:
                datos.pop("hash_contrasena", None)
                usuarios.append(datos)
        return {
            "usuarios": usuarios,
            "roles": [
                rol.codigo
                for rol in self.sesion.scalars(select(RolModelo).order_by(RolModelo.codigo))
            ],
            "clientes": [
                {"id": cliente.id, "codigo": cliente.codigo, "nombre": cliente.nombre}
                for cliente in self.sesion.scalars(
                    select(ClienteModelo).order_by(ClienteModelo.nombre)
                )
            ],
        }

    def asignar_rol(self, usuario_id: str, rol: str, asignar: bool) -> dict[str, object]:
        usuario = self.sesion.get(UsuarioModelo, usuario_id)
        rol_modelo = self.sesion.scalar(select(RolModelo).where(RolModelo.codigo == rol))
        if usuario is None or rol_modelo is None:
            raise EntradaInvalidaError("Usuario o rol inexistente")
        clave = {"usuario_id": usuario_id, "rol_id": rol_modelo.id}
        existente = self.sesion.get(UsuarioRolModelo, (usuario_id, rol_modelo.id))
        if asignar and existente is None:
            self.sesion.add(UsuarioRolModelo(**clave))
            usuario.sesion_version += 1
        elif not asignar and existente is not None:
            self.sesion.execute(delete(UsuarioRolModelo).filter_by(**clave))
            usuario.sesion_version += 1
        self.sesion.flush()
        return {"usuario_id": usuario_id, "rol": rol, "asignado": asignar}

    def asignar_cliente(self, usuario_id: str, cliente_id: str, asignar: bool) -> dict[str, object]:
        if (
            self.sesion.get(UsuarioModelo, usuario_id) is None
            or self.sesion.get(ClienteModelo, cliente_id) is None
        ):
            raise EntradaInvalidaError("Usuario o cliente inexistente")
        clave = {"usuario_id": usuario_id, "cliente_id": cliente_id}
        existente = self.sesion.get(AsignacionUsuarioClienteModelo, (usuario_id, cliente_id))
        if asignar and existente is None:
            self.sesion.add(AsignacionUsuarioClienteModelo(**clave))
            usuario = self.sesion.get(UsuarioModelo, usuario_id)
            assert usuario is not None
            usuario.sesion_version += 1
        elif not asignar and existente is not None:
            self.sesion.execute(delete(AsignacionUsuarioClienteModelo).filter_by(**clave))
            usuario = self.sesion.get(UsuarioModelo, usuario_id)
            assert usuario is not None
            usuario.sesion_version += 1
        self.sesion.flush()
        return {"usuario_id": usuario_id, "cliente_id": cliente_id, "asignado": asignar}

    def buscar_identidad(
        self,
        cliente_id: str,
        documento: str | None,
        correo: str | None,
        telefono: str | None,
        tokens: tuple[str, ...],
    ) -> list[dict[str, object]]:
        condiciones = []
        if documento:
            condiciones.append(CandidatoModelo.documento_normalizado == documento)
        if correo:
            condiciones.append(CandidatoModelo.correo == correo)
        if telefono:
            condiciones.append(CandidatoModelo.telefono.endswith(telefono))
        sentencia = (
            select(
                CandidatoModelo.id.label("candidato_id"),
                CandidatoModelo.nombres,
                CandidatoModelo.apellidos,
                CandidatoModelo.documento_normalizado,
                CandidatoModelo.correo,
                CandidatoModelo.telefono,
                CandidatoModelo.estado.label("candidato_estado"),
                CandidatoModelo.creado_en.label("candidato_creado_en"),
                PostulacionModelo.id.label("postulacion_id"),
                PostulacionModelo.convocatoria_id,
                PostulacionModelo.estado.label("postulacion_estado"),
                PostulacionModelo.creado_en.label("postulacion_creado_en"),
                ConvocatoriaModelo.codigo.label("convocatoria_codigo"),
                UsuarioModelo.nombre.label("reclutador_nombre"),
                UsuarioModelo.correo.label("reclutador_correo"),
            )
            .outerjoin(
                PostulacionModelo,
                and_(
                    PostulacionModelo.candidato_id == CandidatoModelo.id,
                    PostulacionModelo.cliente_id == cliente_id,
                ),
            )
            .outerjoin(
                ConvocatoriaModelo,
                ConvocatoriaModelo.id == PostulacionModelo.convocatoria_id,
            )
            .outerjoin(UsuarioModelo, UsuarioModelo.id == PostulacionModelo.reclutador_id)
            .where(CandidatoModelo.cliente_id == cliente_id)
            .order_by(CandidatoModelo.id, PostulacionModelo.creado_en.desc())
        )
        if condiciones and not tokens:
            sentencia = sentencia.where(or_(*condiciones))
        encontrados_por_id: dict[str, dict[str, object]] = {}
        for fila in self.sesion.execute(sentencia).mappings():
            candidato_id = str(fila["candidato_id"])
            criterio = _criterio_identidad(fila, documento, correo, telefono, tokens)
            if not criterio:
                continue
            encontrado = encontrados_por_id.setdefault(
                candidato_id,
                {
                    "id": candidato_id,
                    "criterio": criterio,
                    "identidad_enmascarada": " ".join(
                        f"{str(parte)[:1]}***" for parte in (fila["nombres"], fila["apellidos"])
                    ),
                    "estado": fila["candidato_estado"],
                    "reclutador": "sin_asignar",
                    "fecha": fila["candidato_creado_en"].isoformat(),
                    "antecedentes": [],
                },
            )
            if fila["postulacion_id"] is None:
                continue
            reclutador = str(
                fila["reclutador_nombre"] or fila["reclutador_correo"] or "sin_asignar"
            )
            antecedentes = encontrados_por_id[candidato_id]["antecedentes"]
            assert isinstance(antecedentes, list)
            antecedentes.append(
                {
                    "convocatoria_id": fila["convocatoria_id"],
                    "proceso": fila["convocatoria_codigo"],
                    "estado": fila["postulacion_estado"],
                    "fecha": fila["postulacion_creado_en"].isoformat(),
                    "reclutador": reclutador,
                }
            )
            if encontrado["reclutador"] == "sin_asignar":
                encontrado["reclutador"] = reclutador
        return list(encontrados_por_id.values())

    def agregar_candidato(self, candidato: Candidato) -> Candidato:
        self.sesion.add(_candidato_a_modelo(candidato))
        try:
            self.sesion.flush()
        except IntegrityError as exc:
            raise ConflictoError("La identidad ya existe en el alcance configurado") from exc
        return candidato

    def obtener_candidato(self, candidato_id: str) -> Candidato | None:
        modelo = self.sesion.get(CandidatoModelo, candidato_id)
        return _candidato_desde_modelo(modelo) if modelo else None

    def buscar_candidatos(
        self, clientes: frozenset[str], texto: str, limite: int, cursor: str | None
    ) -> list[Candidato]:
        sentencia = select(CandidatoModelo).order_by(CandidatoModelo.id).limit(limite)
        if clientes:
            sentencia = sentencia.where(CandidatoModelo.cliente_id.in_(clientes))
        if cursor:
            sentencia = sentencia.where(CandidatoModelo.id > cursor)
        if texto:
            patron = f"%{texto.strip()}%"
            sentencia = sentencia.where(
                or_(
                    CandidatoModelo.nombres.ilike(patron),
                    CandidatoModelo.apellidos.ilike(patron),
                    CandidatoModelo.correo.ilike(patron),
                    CandidatoModelo.documento_normalizado.ilike(patron),
                )
            )
        return [_candidato_desde_modelo(modelo) for modelo in self.sesion.scalars(sentencia)]

    def actualizar_candidato(
        self, candidato: Candidato, version_esperada: int, campos: set[str]
    ) -> Candidato:
        modelo_actual = self.sesion.get(CandidatoModelo, candidato.id)
        if modelo_actual is None:
            raise ConflictoError("Candidato no encontrado")
        version_base = modelo_actual.version
        if version_base != version_esperada:
            eventos = self.sesion.scalars(
                select(EventoAuditoriaModelo).where(
                    EventoAuditoriaModelo.recurso_tipo == "candidato",
                    EventoAuditoriaModelo.recurso_id == candidato.id,
                    EventoAuditoriaModelo.accion == "candidato.actualizado",
                )
            )
            modificados: set[str] = set()
            for evento in eventos:
                detalle = evento.detalle or {}
                anterior = detalle.get("version_anterior")
                if isinstance(anterior, int) and anterior >= version_esperada:
                    campos_evento = detalle.get("campos", [])
                    if isinstance(campos_evento, list):
                        modificados.update(str(campo) for campo in campos_evento)
            solapados = campos & modificados
            if solapados:
                raise ConflictoError("Conflicto en campos: " + ", ".join(sorted(solapados)))
        valores = {campo: getattr(candidato, campo) for campo in campos}
        if "estado" in valores:
            valores["estado"] = candidato.estado.value
        valores.update(
            version=version_base + 1,
            actualizado_en=datetime.now(UTC),
        )
        resultado = self.sesion.execute(
            update(CandidatoModelo)
            .where(
                CandidatoModelo.id == candidato.id,
                CandidatoModelo.version == version_base,
            )
            .values(**valores)
        )
        if not isinstance(resultado, CursorResult) or resultado.rowcount != 1:
            raise ConflictoError("El candidato fue modificado por otra persona")
        self.sesion.flush()
        actualizado = self.obtener_candidato(candidato.id)
        if actualizado is None:
            raise ConflictoError("No se pudo recuperar el candidato actualizado")
        return actualizado

    def registrar_evento(
        self,
        *,
        cliente_id: str | None,
        actor_id: str | None,
        accion: str,
        recurso_tipo: str,
        recurso_id: str | None,
        detalle: dict[str, object],
        correlacion_id: str,
    ) -> str:
        anterior = (
            self.sesion.scalar(
                select(EventoAuditoriaModelo.hash_evento)
                .order_by(EventoAuditoriaModelo.ocurrido_en.desc())
                .limit(1)
            )
            or ""
        )
        evento_id = nuevo_id()
        contenido = json.dumps(
            {
                "id": evento_id,
                "cliente_id": cliente_id,
                "actor_id": actor_id,
                "accion": accion,
                "recurso_tipo": recurso_tipo,
                "recurso_id": recurso_id,
                "detalle": detalle,
                "hash_anterior": anterior,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        huella = hashlib.sha256(contenido.encode()).hexdigest()
        self.sesion.add(
            EventoAuditoriaModelo(
                id=evento_id,
                cliente_id=cliente_id,
                actor_id=actor_id,
                accion=accion,
                recurso_tipo=recurso_tipo,
                recurso_id=recurso_id,
                detalle=detalle,
                hash_anterior=anterior,
                hash_evento=huella,
                correlacion_id=correlacion_id,
            )
        )
        if recurso_tipo == "candidato" and recurso_id:
            self.sesion.add(
                EventoCandidatoModelo(
                    id=nuevo_id(),
                    candidato_id=recurso_id,
                    tipo=accion,
                    actor_id=actor_id or "sistema",
                    detalle=detalle,
                )
            )
        self.sesion.flush()
        return evento_id

    def traza_candidato(
        self,
        candidato_id: str,
        limite: int,
        tipo: str | None = None,
        desde: datetime | None = None,
    ) -> list[dict[str, object]]:
        postulaciones = list(
            self.sesion.scalars(
                select(PostulacionModelo.id).where(PostulacionModelo.candidato_id == candidato_id)
            )
        )
        documentos = list(
            self.sesion.scalars(
                select(DocumentoCandidatoModelo.id).where(
                    DocumentoCandidatoModelo.candidato_id == candidato_id
                )
            )
        )
        evaluaciones = (
            list(
                self.sesion.scalars(
                    select(EvaluacionModelo.id).where(
                        EvaluacionModelo.postulacion_id.in_(postulaciones)
                    )
                )
            )
            if postulaciones
            else []
        )
        relaciones = [
            and_(
                EventoAuditoriaModelo.recurso_tipo == "candidato",
                EventoAuditoriaModelo.recurso_id == candidato_id,
            )
        ]
        for recurso_tipo, ids in (
            ("postulacion", postulaciones),
            ("documento", documentos),
            ("evaluacion", evaluaciones),
        ):
            if ids:
                relaciones.append(
                    and_(
                        EventoAuditoriaModelo.recurso_tipo == recurso_tipo,
                        EventoAuditoriaModelo.recurso_id.in_(ids),
                    )
                )
        consulta = select(EventoAuditoriaModelo).where(or_(*relaciones))
        if tipo:
            consulta = consulta.where(EventoAuditoriaModelo.accion == tipo)
        if desde:
            consulta = consulta.where(EventoAuditoriaModelo.ocurrido_en >= desde)
        eventos = self.sesion.scalars(
            consulta.order_by(EventoAuditoriaModelo.ocurrido_en.desc()).limit(limite)
        )
        return [
            {
                "tipo": evento.accion,
                "actor_id": evento.actor_id,
                "detalle": evento.detalle,
                "ocurrido_en": evento.ocurrido_en,
                "correlacion_id": evento.correlacion_id,
                "recurso_tipo": evento.recurso_tipo,
                "recurso_id": evento.recurso_id,
            }
            for evento in eventos
        ]

    def crear_perfil(self, datos: dict[str, object]) -> dict[str, object]:
        modelo = PerfilPuestoModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        try:
            self.sesion.flush()
        except IntegrityError as exc:
            raise ConflictoError("Ya existe un perfil con ese codigo para el cliente") from exc
        return {"id": modelo.id, "cliente_id": modelo.cliente_id, "codigo": modelo.codigo}

    def obtener_perfil(self, perfil_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(PerfilPuestoModelo, perfil_id)
        if modelo is None:
            return None
        return {
            "id": modelo.id,
            "cliente_id": modelo.cliente_id,
            "codigo": modelo.codigo,
            "titulo": modelo.titulo,
            "activo": modelo.activo,
        }

    def crear_version_perfil(self, datos: dict[str, object]) -> dict[str, object]:
        perfil_id = str(datos["perfil_id"])
        numero = (
            self.sesion.scalar(
                select(func.max(VersionPerfilPuestoModelo.numero)).where(
                    VersionPerfilPuestoModelo.perfil_id == perfil_id
                )
            )
            or 0
        )
        modelo = VersionPerfilPuestoModelo(id=nuevo_id(), numero=numero + 1, **datos)
        self.sesion.add(modelo)
        self.sesion.flush()
        return {"id": modelo.id, "perfil_id": perfil_id, "numero": modelo.numero}

    def obtener_version_perfil(self, version_id: str) -> dict[str, object] | None:
        fila = (
            self.sesion.execute(
                select(
                    VersionPerfilPuestoModelo.id,
                    VersionPerfilPuestoModelo.perfil_id,
                    VersionPerfilPuestoModelo.numero,
                    VersionPerfilPuestoModelo.publicado,
                    VersionPerfilPuestoModelo.requisitos,
                    VersionPerfilPuestoModelo.ctc,
                    PerfilPuestoModelo.cliente_id,
                    PerfilPuestoModelo.codigo,
                    PerfilPuestoModelo.titulo,
                )
                .join(
                    PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id
                )
                .where(VersionPerfilPuestoModelo.id == version_id)
            )
            .mappings()
            .one_or_none()
        )
        return dict(fila) if fila is not None else None

    def obtener_versiones_perfil(self, perfil_id: str) -> list[dict[str, object]]:
        filas = (
            self.sesion.execute(
                select(
                    VersionPerfilPuestoModelo.id,
                    VersionPerfilPuestoModelo.perfil_id,
                    VersionPerfilPuestoModelo.numero,
                    VersionPerfilPuestoModelo.publicado,
                    VersionPerfilPuestoModelo.requisitos,
                    VersionPerfilPuestoModelo.ctc,
                )
                .where(VersionPerfilPuestoModelo.perfil_id == perfil_id)
                .order_by(VersionPerfilPuestoModelo.numero.desc())
            )
            .mappings()
            .all()
        )
        return [dict(f) for f in filas]

    def listar_postulaciones_perfil(self, perfil_id: str) -> list[dict[str, object]]:
        filas = (
            self.sesion.execute(
                select(
                    PostulacionModelo.id.label("postulacion_id"),
                    PostulacionModelo.cliente_id.label("cliente_id"),
                    PostulacionModelo.candidato_id.label("candidato_id"),
                    PostulacionModelo.convocatoria_id.label("convocatoria_id"),
                    PostulacionModelo.version_perfil_id.label("version_perfil_id"),
                    PostulacionModelo.fuente.label("fuente"),
                    PostulacionModelo.estado.label("estado"),
                    PostulacionModelo.creado_en.label("creado_en"),
                    VersionPerfilPuestoModelo.numero.label("version_numero"),
                    VersionPerfilPuestoModelo.ctc.label("version_ctc"),
                )
                .join(
                    VersionPerfilPuestoModelo,
                    VersionPerfilPuestoModelo.id == PostulacionModelo.version_perfil_id,
                )
                .where(VersionPerfilPuestoModelo.perfil_id == perfil_id)
                .order_by(PostulacionModelo.creado_en.desc())
            )
            .mappings()
            .all()
        )
        return [dict(f) for f in filas]

    @staticmethod
    def _convocatoria_a_dict(modelo: ConvocatoriaModelo) -> dict[str, object]:
        return {
            "id": modelo.id,
            "cliente_id": modelo.cliente_id,
            "version_perfil_id": modelo.version_perfil_id,
            "codigo": modelo.codigo,
            "vacantes_total": modelo.vacantes_total,
            "fecha_apertura": modelo.fecha_apertura,
            "fecha_objetivo": modelo.fecha_objetivo,
            "estado": modelo.estado,
            "motivo_cierre": modelo.motivo_cierre,
            "es_compatibilidad": modelo.es_compatibilidad,
            "cerrada_en": modelo.cerrada_en,
            "version": modelo.version,
        }

    def crear_convocatoria(self, datos: dict[str, object]) -> dict[str, object]:
        modelo = ConvocatoriaModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        try:
            self.sesion.flush()
        except IntegrityError as exc:
            raise ConflictoError("Ya existe una convocatoria con ese codigo en la cuenta") from exc
        return self._convocatoria_a_dict(modelo)

    def obtener_convocatoria(self, convocatoria_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(ConvocatoriaModelo, convocatoria_id)
        if modelo is None:
            return None
        resultado = self._convocatoria_a_dict(modelo)
        contexto = (
            self.sesion.execute(
                select(
                    ClienteModelo.id.label("cuenta_id"),
                    ClienteModelo.codigo.label("cuenta_codigo"),
                    ClienteModelo.nombre.label("cuenta_nombre"),
                    PerfilPuestoModelo.id.label("perfil_id"),
                    PerfilPuestoModelo.codigo.label("perfil_codigo"),
                    PerfilPuestoModelo.titulo.label("perfil_titulo"),
                    VersionPerfilPuestoModelo.numero.label("perfil_version"),
                    VersionPerfilPuestoModelo.requisitos.label("perfil_requisitos"),
                    VersionPerfilPuestoModelo.ctc.label("perfil_ctc"),
                )
                .select_from(ConvocatoriaModelo)
                .join(
                    VersionPerfilPuestoModelo,
                    VersionPerfilPuestoModelo.id == ConvocatoriaModelo.version_perfil_id,
                )
                .join(
                    PerfilPuestoModelo,
                    PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id,
                )
                .join(ClienteModelo, ClienteModelo.id == ConvocatoriaModelo.cliente_id)
                .where(ConvocatoriaModelo.id == convocatoria_id)
            )
            .mappings()
            .one()
        )
        resultado["cuenta"] = {
            "id": contexto["cuenta_id"],
            "codigo": contexto["cuenta_codigo"],
            "nombre": contexto["cuenta_nombre"],
        }
        resultado["perfil"] = {
            "id": contexto["perfil_id"],
            "codigo": contexto["perfil_codigo"],
            "titulo": contexto["perfil_titulo"],
            "version": contexto["perfil_version"],
            "requisitos": contexto["perfil_requisitos"],
            "ctc": contexto["perfil_ctc"],
        }
        resultado["responsables"] = [
            {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "correo": usuario.correo,
                "asignado_en": asignacion.asignado_en,
            }
            for asignacion, usuario in self.sesion.execute(
                select(AsignacionReclutadorConvocatoriaModelo, UsuarioModelo)
                .join(
                    UsuarioModelo,
                    UsuarioModelo.id == AsignacionReclutadorConvocatoriaModelo.usuario_id,
                )
                .where(AsignacionReclutadorConvocatoriaModelo.convocatoria_id == convocatoria_id)
                .order_by(UsuarioModelo.nombre)
            )
        ]
        return resultado

    def listar_convocatorias(
        self,
        clientes: frozenset[str],
        cliente_id: str | None = None,
        limite: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, object]]:
        sentencia = select(ConvocatoriaModelo)
        if cliente_id is not None:
            sentencia = sentencia.where(ConvocatoriaModelo.cliente_id == cliente_id)
        elif clientes:
            sentencia = sentencia.where(ConvocatoriaModelo.cliente_id.in_(clientes))
        if cursor:
            sentencia = sentencia.where(ConvocatoriaModelo.id > cursor)
        filas = self.sesion.scalars(sentencia.order_by(ConvocatoriaModelo.id).limit(limite))
        return [self._convocatoria_a_dict(modelo) for modelo in filas]

    def obtener_o_crear_convocatoria_compatibilidad(
        self, cliente_id: str, version_perfil_id: str
    ) -> dict[str, object]:
        modelo = self.sesion.scalar(
            select(ConvocatoriaModelo).where(
                ConvocatoriaModelo.cliente_id == cliente_id,
                ConvocatoriaModelo.version_perfil_id == version_perfil_id,
                ConvocatoriaModelo.es_compatibilidad.is_(True),
                ConvocatoriaModelo.estado == "abierta",
            )
        )
        if modelo is None:
            base_codigo = f"COMPAT-{version_perfil_id[:16]}"
            codigo = base_codigo
            sufijo = 1
            while self.sesion.scalar(
                select(ConvocatoriaModelo.id).where(
                    ConvocatoriaModelo.cliente_id == cliente_id,
                    ConvocatoriaModelo.codigo == codigo,
                )
            ):
                sufijo += 1
                codigo = f"{base_codigo}-{sufijo}"
            modelo = ConvocatoriaModelo(
                id=nuevo_id(),
                cliente_id=cliente_id,
                version_perfil_id=version_perfil_id,
                codigo=codigo,
                vacantes_total=1,
                fecha_apertura=datetime.now(UTC).date(),
                fecha_objetivo=None,
                estado="abierta",
                es_compatibilidad=True,
            )
            self.sesion.add(modelo)
            self.sesion.flush()
        return self._convocatoria_a_dict(modelo)

    def usuario_asignado_cliente(self, usuario_id: str, cliente_id: str) -> bool:
        return self.sesion.get(AsignacionUsuarioClienteModelo, (usuario_id, cliente_id)) is not None

    def asignar_reclutador_convocatoria(
        self, convocatoria_id: str, usuario_id: str, asignado_por: str, asignar: bool
    ) -> dict[str, object]:
        convocatoria = self.sesion.get(ConvocatoriaModelo, convocatoria_id)
        usuario = self.sesion.get(UsuarioModelo, usuario_id)
        if convocatoria is None or usuario is None or not usuario.activo:
            raise EntradaInvalidaError("Convocatoria o usuario activo inexistente")
        rol_reclutador = self.sesion.scalar(
            select(UsuarioRolModelo.usuario_id)
            .join(RolModelo, RolModelo.id == UsuarioRolModelo.rol_id)
            .where(
                UsuarioRolModelo.usuario_id == usuario_id,
                RolModelo.codigo == "reclutador",
            )
        )
        if not self.usuario_asignado_cliente(usuario_id, convocatoria.cliente_id):
            raise EntradaInvalidaError("El reclutador no tiene acceso a la cuenta")
        if rol_reclutador is None:
            raise EntradaInvalidaError("El responsable debe tener rol reclutador")
        clave = (convocatoria_id, usuario_id)
        existente = self.sesion.get(AsignacionReclutadorConvocatoriaModelo, clave)
        if asignar and existente is None:
            self.sesion.add(
                AsignacionReclutadorConvocatoriaModelo(
                    convocatoria_id=convocatoria_id,
                    usuario_id=usuario_id,
                    asignado_por=asignado_por,
                )
            )
        elif not asignar and existente is not None:
            self.sesion.delete(existente)
        self.sesion.flush()
        return {
            "convocatoria_id": convocatoria_id,
            "usuario_id": usuario_id,
            "asignado": asignar,
        }

    def transicionar_postulacion(
        self,
        postulacion_id: str,
        destino: str,
        motivo: str | None,
        version_esperada: int,
    ) -> dict[str, object]:
        modelo = self.sesion.get(PostulacionModelo, postulacion_id)
        if modelo is None:
            raise EntradaInvalidaError("Postulacion inexistente")
        if modelo.version != version_esperada:
            raise ConflictoError(
                f"La candidatura cambio; version actual {modelo.version}, estado {modelo.estado}"
            )
        try:
            origen_estado = EstadoPostulacion(modelo.estado)
            destino_estado = EstadoPostulacion(destino)
            validar_transicion_postulacion(origen_estado, destino_estado, motivo)
        except (ValueError, TransicionPostulacionInvalidaError) as exc:
            raise EntradaInvalidaError(str(exc)) from exc
        convocatoria = self.sesion.get(ConvocatoriaModelo, modelo.convocatoria_id)
        if convocatoria is None or convocatoria.estado != "abierta":
            raise ConflictoError("La convocatoria no esta abierta")
        if destino_estado is EstadoPostulacion.FINALISTA:
            finalistas = (
                self.sesion.scalar(
                    select(func.count())
                    .select_from(PostulacionModelo)
                    .where(
                        PostulacionModelo.convocatoria_id == modelo.convocatoria_id,
                        PostulacionModelo.estado.in_(
                            ["finalista", "entrevista", "oferta", "contratada"]
                        ),
                        PostulacionModelo.id != modelo.id,
                    )
                )
                or 0
            )
            if int(finalistas) >= convocatoria.vacantes_total:
                raise ConflictoError("Los cupos de finalistas ya estan cubiertos")
        anterior = modelo.estado
        ahora = datetime.now(UTC)
        resultado_actualizacion = self.sesion.execute(
            update(PostulacionModelo)
            .where(
                PostulacionModelo.id == postulacion_id,
                PostulacionModelo.version == version_esperada,
            )
            .values(
                estado=destino_estado.value,
                version=version_esperada + 1,
                actualizado_en=ahora,
            )
            .execution_options(synchronize_session=False)
        )
        if (
            not isinstance(resultado_actualizacion, CursorResult)
            or resultado_actualizacion.rowcount != 1
        ):
            self.sesion.expire_all()
            actual = self.sesion.get(PostulacionModelo, postulacion_id)
            detalle = (
                f"version actual {actual.version}, estado {actual.estado}"
                if actual is not None
                else "candidatura inexistente"
            )
            raise ConflictoError(f"La candidatura cambio; {detalle}")
        self.sesion.expire_all()
        modelo_actualizado = self.sesion.get(PostulacionModelo, postulacion_id)
        assert modelo_actualizado is not None
        return {
            "id": modelo_actualizado.id,
            "cliente_id": modelo_actualizado.cliente_id,
            "convocatoria_id": modelo_actualizado.convocatoria_id,
            "estado_anterior": anterior,
            "estado": modelo_actualizado.estado,
            "version": modelo_actualizado.version,
            "motivo": motivo,
        }

    def listar_postulaciones_convocatoria(self, convocatoria_id: str) -> list[dict[str, object]]:
        evaluacion_actual = (
            select(EvaluacionModelo.id)
            .where(EvaluacionModelo.postulacion_id == PostulacionModelo.id)
            .order_by(EvaluacionModelo.creado_en.desc())
            .limit(1)
            .correlate(PostulacionModelo)
            .scalar_subquery()
        )
        filas = self.sesion.execute(
            select(
                PostulacionModelo.id,
                PostulacionModelo.cliente_id,
                PostulacionModelo.candidato_id,
                PostulacionModelo.convocatoria_id,
                PostulacionModelo.version_perfil_id,
                PostulacionModelo.fuente,
                PostulacionModelo.estado,
                PostulacionModelo.version,
                PostulacionModelo.actualizado_en,
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                CandidatoModelo.documento_normalizado,
                CandidatoModelo.reclutador,
                CandidatoModelo.etiquetas,
                EvaluacionModelo.id.label("evaluacion_id"),
                EvaluacionModelo.puntaje_documental,
                EvaluacionModelo.requiere_revision,
            )
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .outerjoin(EvaluacionModelo, EvaluacionModelo.id == evaluacion_actual)
            .where(PostulacionModelo.convocatoria_id == convocatoria_id)
            .order_by(PostulacionModelo.actualizado_en.desc())
        ).mappings()
        resultados: list[dict[str, object]] = []
        for fila in filas:
            resultado = dict(fila)
            etiquetas = set(resultado.pop("etiquetas") or [])
            resultado["bloqueada_ex_tcs"] = "politica-ex-tcs-bloqueado" in etiquetas
            resultado["restriccion_vigente"] = "restriccion-vigente" in etiquetas
            resultados.append(resultado)
        return resultados

    def vista_previa_cierre(self, convocatoria_id: str) -> dict[str, object]:
        convocatoria = self.sesion.get(ConvocatoriaModelo, convocatoria_id)
        if convocatoria is None:
            raise EntradaInvalidaError("Convocatoria inexistente")
        conteos = {
            str(estado): int(cantidad)
            for estado, cantidad in self.sesion.execute(
                select(PostulacionModelo.estado, func.count())
                .where(PostulacionModelo.convocatoria_id == convocatoria_id)
                .group_by(PostulacionModelo.estado)
            )
        }
        cubiertas = conteos.get("contratada", 0)
        return {
            "convocatoria_id": convocatoria_id,
            "version": convocatoria.version,
            "vacantes_total": convocatoria.vacantes_total,
            "cubiertas": cubiertas,
            "pendientes": max(0, convocatoria.vacantes_total - cubiertas),
            "aptas_para_backup": conteos.get("apta", 0),
            "conteos": conteos,
            "puede_cerrar": cubiertas >= convocatoria.vacantes_total,
        }

    def cerrar_convocatoria(
        self, convocatoria_id: str, version_esperada: int, motivo: str
    ) -> dict[str, object]:
        convocatoria = self.sesion.get(ConvocatoriaModelo, convocatoria_id)
        if convocatoria is None:
            raise EntradaInvalidaError("Convocatoria inexistente")
        if convocatoria.version != version_esperada:
            raise ConflictoError(f"La convocatoria cambio; version actual {convocatoria.version}")
        previa = self.vista_previa_cierre(convocatoria_id)
        if not bool(previa["puede_cerrar"]):
            raise ConflictoError("No se han cubierto todas las vacantes")
        if not motivo.strip():
            raise EntradaInvalidaError("El cierre requiere un motivo")
        ahora = datetime.now(UTC)
        resultado_cierre = self.sesion.execute(
            update(ConvocatoriaModelo)
            .where(
                ConvocatoriaModelo.id == convocatoria_id,
                ConvocatoriaModelo.version == version_esperada,
                ConvocatoriaModelo.estado == "abierta",
            )
            .values(
                estado="cerrada",
                motivo_cierre=motivo.strip(),
                cerrada_en=ahora,
                version=version_esperada + 1,
                actualizado_en=ahora,
            )
            .execution_options(synchronize_session=False)
        )
        if not isinstance(resultado_cierre, CursorResult) or resultado_cierre.rowcount != 1:
            self.sesion.expire_all()
            actual = self.sesion.get(ConvocatoriaModelo, convocatoria_id)
            version_actual = actual.version if actual is not None else "desconocida"
            raise ConflictoError(f"La convocatoria cambio; version actual {version_actual}")
        resultado_respaldos = self.sesion.execute(
            update(PostulacionModelo)
            .where(
                PostulacionModelo.convocatoria_id == convocatoria_id,
                PostulacionModelo.estado == "apta",
            )
            .values(
                estado="backup",
                version=PostulacionModelo.version + 1,
                actualizado_en=ahora,
            )
            .execution_options(synchronize_session=False)
        )
        respaldos_generados = (
            resultado_respaldos.rowcount
            if isinstance(resultado_respaldos, CursorResult)
            and resultado_respaldos.rowcount is not None
            else 0
        )
        self.sesion.expire_all()
        convocatoria_actualizada = self.sesion.get(ConvocatoriaModelo, convocatoria_id)
        assert convocatoria_actualizada is not None
        return {
            **self._convocatoria_a_dict(convocatoria_actualizada),
            "backups_generados": respaldos_generados,
        }

    def crear_postulacion(self, datos: dict[str, object]) -> dict[str, object]:
        existente = self.sesion.scalar(
            select(PostulacionModelo).where(
                PostulacionModelo.clave_idempotencia == datos["clave_idempotencia"]
            )
        )
        if existente is not None:
            bloqueo_aplicado = False
            if datos.get("estado") == EstadoPostulacion.NO_APTA.value and (
                existente.estado != EstadoPostulacion.NO_APTA.value
            ):
                existente.estado = EstadoPostulacion.NO_APTA.value
                existente.version += 1
                existente.actualizado_en = datetime.now(UTC)
                self.sesion.flush()
                bloqueo_aplicado = True
            return {
                "id": existente.id,
                "estado": existente.estado,
                "cliente_id": existente.cliente_id,
                "convocatoria_id": existente.convocatoria_id,
                "version": existente.version,
                "reutilizado": True,
                "bloqueo_aplicado": bloqueo_aplicado,
            }
        modelo = PostulacionModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        try:
            self.sesion.flush()
        except IntegrityError as exc:
            raise ConflictoError("La postulacion ya existe") from exc
        return {
            "id": modelo.id,
            "estado": modelo.estado,
            "cliente_id": modelo.cliente_id,
            "convocatoria_id": modelo.convocatoria_id,
            "version": modelo.version,
            "reutilizado": False,
        }

    def obtener_postulacion(self, postulacion_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(PostulacionModelo, postulacion_id)
        if modelo is None:
            return None
        return {
            "id": modelo.id,
            "cliente_id": modelo.cliente_id,
            "candidato_id": modelo.candidato_id,
            "version_perfil_id": modelo.version_perfil_id,
            "fuente": modelo.fuente,
            "estado": modelo.estado,
        }

    def guardar_documento(self, datos: dict[str, object]) -> dict[str, object]:
        modelo = DocumentoCandidatoModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        try:
            self.sesion.flush()
        except IntegrityError as exc:
            raise ConflictoError("El documento ya fue adjuntado") from exc
        return {"id": modelo.id, "hash_sha256": modelo.hash_sha256}

    def obtener_documento(self, documento_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(DocumentoCandidatoModelo, documento_id)
        if modelo is None:
            return None
        return {
            "id": modelo.id,
            "cliente_id": modelo.cliente_id,
            "candidato_id": modelo.candidato_id,
            "nombre_original": modelo.nombre_original,
            "tipo_mime": modelo.tipo_mime,
            "hash_sha256": modelo.hash_sha256,
            "ruta_almacenamiento": modelo.ruta_almacenamiento,
            "tamano_bytes": modelo.tamano_bytes,
        }

    def buscar_documento_por_hash(
        self, candidato_id: str, hash_sha256: str
    ) -> dict[str, object] | None:
        modelo = self.sesion.scalar(
            select(DocumentoCandidatoModelo).where(
                DocumentoCandidatoModelo.candidato_id == candidato_id,
                DocumentoCandidatoModelo.hash_sha256 == hash_sha256,
            )
        )
        return self.obtener_documento(modelo.id) if modelo is not None else None

    def obtener_extraccion_documento(self, documento_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(ExtraccionDocumentoModelo, documento_id)
        if modelo is None:
            return None
        sugerencias = self.sesion.scalars(
            select(SugerenciaCampoModelo)
            .where(SugerenciaCampoModelo.extraccion_id == modelo.id)
            .order_by(SugerenciaCampoModelo.campo)
        ).all()
        return {
            "id": modelo.id,
            "documento_id": modelo.documento_id,
            "estado": modelo.estado,
            "texto_sanitizado": modelo.texto_sanitizado,
            "campos": modelo.campos,
            "referencias": modelo.referencias,
            "error": modelo.error,
            "version": modelo.version,
            "sugerencias": [
                {
                    "id": sugerencia.id,
                    "campo": sugerencia.campo,
                    "valor": sugerencia.valor,
                    "confianza": sugerencia.confianza,
                    "fuente": sugerencia.fuente,
                    "estado": sugerencia.estado,
                }
                for sugerencia in sugerencias
            ],
        }

    def guardar_extraccion_documento(
        self,
        datos: dict[str, object],
        sugerencias: list[dict[str, object]],
    ) -> dict[str, object]:
        documento_id = str(datos["documento_id"])
        existente = self.obtener_extraccion_documento(documento_id)
        if existente is not None:
            return {**existente, "reutilizado": True}
        modelo = ExtraccionDocumentoModelo(id=documento_id, **datos)
        self.sesion.add(modelo)
        self.sesion.flush()
        for sugerencia in sugerencias:
            identificador = hashlib.sha256(
                f"{documento_id}:{sugerencia['campo']}".encode()
            ).hexdigest()[:32]
            self.sesion.add(
                SugerenciaCampoModelo(
                    id=identificador,
                    extraccion_id=modelo.id,
                    campo=str(sugerencia["campo"]),
                    valor=sugerencia["valor"],
                    confianza=Decimal(str(sugerencia["confianza"])),
                    fuente=sugerencia["fuente"],
                    estado="pendiente",
                )
            )
        self.sesion.flush()
        resultado = self.obtener_extraccion_documento(documento_id)
        if resultado is None:
            raise RuntimeError("No se pudo recuperar la extraccion persistida")
        return {**resultado, "reutilizado": False}

    def validar_solicitud_evaluacion(
        self,
        cliente_id: str,
        postulacion_id: str,
        documento_id: str,
        version_perfil_id: str,
    ) -> bool:
        postulacion = self.sesion.get(PostulacionModelo, postulacion_id)
        documento = self.sesion.get(DocumentoCandidatoModelo, documento_id)
        version = self.sesion.get(VersionPerfilPuestoModelo, version_perfil_id)
        return bool(
            postulacion
            and documento
            and version
            and postulacion.cliente_id == cliente_id
            and documento.cliente_id == cliente_id
            and postulacion.candidato_id == documento.candidato_id
            and postulacion.version_perfil_id == version_perfil_id
        )

    def crear_trabajo(self, datos: dict[str, object]) -> dict[str, object]:
        existente = self.sesion.scalar(
            select(TrabajoAgenteModelo).where(
                TrabajoAgenteModelo.clave_idempotencia == datos["clave_idempotencia"]
            )
        )
        if existente:
            return {"id": existente.id, "estado": existente.estado, "reutilizado": True}
        modelo = TrabajoAgenteModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        self.sesion.flush()
        return {"id": modelo.id, "estado": modelo.estado, "reutilizado": False}

    def obtener_trabajo(self, trabajo_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(TrabajoAgenteModelo, trabajo_id)
        if not modelo:
            return None
        return {
            "id": modelo.id,
            "cliente_id": modelo.cliente_id,
            "tipo": modelo.tipo,
            "estado": modelo.estado,
            "resultado": modelo.resultado,
            "error": modelo.error,
            "intentos": modelo.intentos,
        }

    def obtener_evaluacion(self, evaluacion_id: str) -> dict[str, object] | None:
        modelo = self.sesion.get(EvaluacionModelo, evaluacion_id)
        if modelo is None:
            return None
        contexto = (
            self.sesion.execute(
                select(
                    (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                    PerfilPuestoModelo.codigo.label("perfil_codigo"),
                    PerfilPuestoModelo.titulo.label("perfil_titulo"),
                    DocumentoCandidatoModelo.nombre_original.label("documento_nombre"),
                )
                .select_from(EvaluacionModelo)
                .join(PostulacionModelo, PostulacionModelo.id == EvaluacionModelo.postulacion_id)
                .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
                .join(
                    VersionPerfilPuestoModelo,
                    VersionPerfilPuestoModelo.id == EvaluacionModelo.version_perfil_id,
                )
                .join(
                    PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id
                )
                .join(
                    DocumentoCandidatoModelo,
                    DocumentoCandidatoModelo.id == EvaluacionModelo.documento_id,
                )
                .where(EvaluacionModelo.id == evaluacion_id)
            )
            .mappings()
            .one()
        )
        requisitos = self.sesion.scalars(
            select(EvaluacionRequisitoModelo)
            .where(EvaluacionRequisitoModelo.evaluacion_id == evaluacion_id)
            .order_by(EvaluacionRequisitoModelo.codigo_requisito)
        ).all()
        revisiones = self.sesion.scalars(
            select(RevisionHumanaModelo)
            .where(RevisionHumanaModelo.evaluacion_id == evaluacion_id)
            .order_by(RevisionHumanaModelo.creado_en)
        ).all()
        correcciones_por_revision: dict[str, list[dict[str, object]]] = {}
        if revisiones:
            correcciones = self.sesion.scalars(
                select(CorreccionCampoModelo)
                .where(CorreccionCampoModelo.revision_id.in_([item.id for item in revisiones]))
                .order_by(CorreccionCampoModelo.creado_en)
            ).all()
            for correccion in correcciones:
                correcciones_por_revision.setdefault(correccion.revision_id, []).append(
                    {
                        "campo": correccion.campo,
                        "valor_anterior": correccion.valor_anterior,
                        "valor_nuevo": correccion.valor_nuevo,
                    }
                )
        return {
            "id": modelo.id,
            "cliente_id": modelo.cliente_id,
            "postulacion_id": modelo.postulacion_id,
            "documento_id": modelo.documento_id,
            "version_perfil_id": modelo.version_perfil_id,
            "puntaje_documental": modelo.puntaje_documental,
            "requiere_revision": modelo.requiere_revision,
            "modelo": modelo.modelo,
            "version_prompt": modelo.version_prompt,
            "simulada": modelo.simulada,
            "candidato": contexto["candidato"],
            "perfil_codigo": contexto["perfil_codigo"],
            "perfil_titulo": contexto["perfil_titulo"],
            "documento_nombre": contexto["documento_nombre"],
            "requisitos": [
                {
                    "codigo_requisito": requisito.codigo_requisito,
                    "veredicto": requisito.veredicto,
                    "puntaje": requisito.puntaje,
                    "evidencia": requisito.evidencia,
                    "explicacion": requisito.explicacion,
                }
                for requisito in requisitos
            ],
            "revisiones": [
                {
                    "id": revision.id,
                    "estado": revision.estado,
                    "revisor_id": revision.revisor_id,
                    "comentario": revision.comentario,
                    "version": revision.version,
                    "creado_en": revision.creado_en,
                    "correcciones": correcciones_por_revision.get(revision.id, []),
                }
                for revision in revisiones
            ],
        }

    def registrar_revision(
        self,
        evaluacion_id: str,
        revisor_id: str,
        decision: str,
        comentario: str,
        correcciones: list[dict[str, object]],
    ) -> dict[str, object]:
        evaluacion = self.sesion.get(EvaluacionModelo, evaluacion_id)
        if evaluacion is None:
            raise EntradaInvalidaError("Evaluacion no encontrada")
        revision = self.sesion.execute(
            select(RevisionHumanaModelo.id, RevisionHumanaModelo.version).where(
                RevisionHumanaModelo.evaluacion_id == evaluacion_id,
                RevisionHumanaModelo.estado == "pendiente",
            )
        ).one_or_none()
        if revision is None:
            raise ConflictoError("La evaluacion no tiene una revision pendiente")
        revision_id, version = revision
        resuelta = self.sesion.execute(
            update(RevisionHumanaModelo)
            .where(
                RevisionHumanaModelo.id == revision_id,
                RevisionHumanaModelo.estado == "pendiente",
                RevisionHumanaModelo.version == version,
            )
            .values(
                estado=decision,
                revisor_id=revisor_id,
                comentario=comentario,
                version=version + 1,
            )
        )
        if not isinstance(resuelta, CursorResult) or resuelta.rowcount != 1:
            raise ConflictoError("La revision ya fue resuelta por otra persona")
        for correccion in correcciones:
            self.sesion.add(
                CorreccionCampoModelo(
                    id=nuevo_id(),
                    revision_id=revision_id,
                    campo=str(correccion["campo"]),
                    valor_anterior=correccion.get("valor_anterior"),
                    valor_nuevo=correccion["valor_nuevo"],
                )
            )
        self.sesion.flush()
        return {
            "id": revision_id,
            "evaluacion_id": evaluacion_id,
            "estado": decision,
            "revisor_id": revisor_id,
            "comentario": comentario,
            "correcciones": len(correcciones),
            "version": version + 1,
        }

    def metricas(
        self,
        clientes: frozenset[str],
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> dict[str, object]:
        filtro: Any = CandidatoModelo.cliente_id.in_(clientes) if clientes else true()
        if desde is not None:
            filtro = filtro & (CandidatoModelo.creado_en >= desde)
        if hasta is not None:
            filtro = filtro & (CandidatoModelo.creado_en <= hasta)
        candidatos = (
            self.sesion.scalar(select(func.count()).select_from(CandidatoModelo).where(filtro)) or 0
        )
        filtro_postulaciones: Any = (
            PostulacionModelo.cliente_id.in_(clientes) if clientes else true()
        )
        filtro_trabajos: Any = TrabajoAgenteModelo.cliente_id.in_(clientes) if clientes else true()
        filtro_evaluaciones: Any = EvaluacionModelo.cliente_id.in_(clientes) if clientes else true()
        filtro_metricas: Any = (
            EventoMetricaPilotoModelo.cliente_id.in_(clientes) if clientes else true()
        )
        if desde is not None:
            filtro_postulaciones &= PostulacionModelo.creado_en >= desde
            filtro_trabajos &= TrabajoAgenteModelo.creado_en >= desde
            filtro_evaluaciones &= EvaluacionModelo.creado_en >= desde
            filtro_metricas &= EventoMetricaPilotoModelo.ocurrido_en >= desde
        if hasta is not None:
            filtro_postulaciones &= PostulacionModelo.creado_en <= hasta
            filtro_trabajos &= TrabajoAgenteModelo.creado_en <= hasta
            filtro_evaluaciones &= EvaluacionModelo.creado_en <= hasta
            filtro_metricas &= EventoMetricaPilotoModelo.ocurrido_en <= hasta
        postulaciones = (
            self.sesion.scalar(
                select(func.count()).select_from(PostulacionModelo).where(filtro_postulaciones)
            )
            or 0
        )
        trabajos_total = (
            self.sesion.scalar(
                select(func.count()).select_from(TrabajoAgenteModelo).where(filtro_trabajos)
            )
            or 0
        )
        trabajos_completados = (
            self.sesion.scalar(
                select(func.count())
                .select_from(TrabajoAgenteModelo)
                .where(filtro_trabajos, TrabajoAgenteModelo.estado == "completado")
            )
            or 0
        )
        trabajos_fallidos = (
            self.sesion.scalar(
                select(func.count())
                .select_from(TrabajoAgenteModelo)
                .where(filtro_trabajos, TrabajoAgenteModelo.estado == "fallido")
            )
            or 0
        )
        trabajos_pendientes = (
            self.sesion.scalar(
                select(func.count())
                .select_from(TrabajoAgenteModelo)
                .where(
                    filtro_trabajos,
                    TrabajoAgenteModelo.estado.in_(["pendiente", "reservado"]),
                )
            )
            or 0
        )
        revisiones = (
            self.sesion.scalar(
                select(func.count())
                .select_from(EvaluacionModelo)
                .where(filtro_evaluaciones, EvaluacionModelo.requiere_revision.is_(True))
            )
            or 0
        )
        evaluaciones = (
            self.sesion.scalar(
                select(func.count()).select_from(EvaluacionModelo).where(filtro_evaluaciones)
            )
            or 0
        )
        reintentos = (
            self.sesion.scalar(
                select(func.sum(func.max(TrabajoAgenteModelo.intentos - 1, 0))).where(
                    filtro_trabajos
                )
            )
            or 0
        )
        duraciones = [
            float(valor)
            for valor in self.sesion.scalars(
                select(EventoMetricaPilotoModelo.valor).where(
                    filtro_metricas,
                    EventoMetricaPilotoModelo.nombre == "trabajo.duracion_ms",
                )
            )
        ]
        return {
            "candidatos": candidatos,
            "postulaciones": postulaciones,
            "trabajos_total": trabajos_total,
            "trabajos_completados": trabajos_completados,
            "trabajos_fallidos": trabajos_fallidos,
            "trabajos_pendientes": trabajos_pendientes,
            "tasa_exito": round(trabajos_completados / trabajos_total, 4)
            if trabajos_total
            else 0.0,
            "tasa_error": round(trabajos_fallidos / trabajos_total, 4) if trabajos_total else 0.0,
            "tasa_revision_humana": round(revisiones / evaluaciones, 4) if evaluaciones else 0.0,
            "reintentos": int(reintentos),
            "duracion_ms_p50": _percentil(duraciones, 0.50),
            "duracion_ms_p95": _percentil(duraciones, 0.95),
            "cv_util": None,
            "cv_util_estado": "bloqueado_BIZ_006",
        }

    def registrar_metrica(
        self,
        cliente_id: str,
        nombre: str,
        valor: int | float | Decimal,
        unidad: str,
        dimensiones: dict[str, object],
        clave_idempotencia: str | None = None,
    ) -> None:
        persistir_metrica(
            self.sesion,
            cliente_id=cliente_id,
            nombre=nombre,
            valor=valor,
            unidad=unidad,
            dimensiones=dimensiones,
            clave_idempotencia=clave_idempotencia,
        )

    def listar_panel_operativo(
        self, modulo: str, clientes: frozenset[str], limite: int
    ) -> list[dict[str, object]]:
        consultas: dict[str, Any] = {
            "clientes": select(
                ClienteModelo.codigo.label("codigo"),
                ClienteModelo.nombre.label("nombre"),
                ClienteModelo.activo.label("activo"),
            ).where(_filtro_clientes(ClienteModelo.id, clientes)),
            "perfiles": select(
                PerfilPuestoModelo.id.label("id"),
                PerfilPuestoModelo.codigo.label("codigo"),
                PerfilPuestoModelo.titulo.label("titulo"),
                PerfilPuestoModelo.activo.label("activo"),
                PerfilPuestoModelo.creado_en.label("creado_en"),
            ).where(_filtro_clientes(PerfilPuestoModelo.cliente_id, clientes)),
            "postulaciones": select(
                PostulacionModelo.id.label("id"),
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                (PerfilPuestoModelo.codigo + " · " + PerfilPuestoModelo.titulo).label("perfil"),
                (ClienteModelo.codigo + " · " + ClienteModelo.nombre).label("cliente"),
                ConvocatoriaModelo.codigo.label("convocatoria"),
                PostulacionModelo.fuente.label("fuente"),
                PostulacionModelo.estado.label("estado"),
                PostulacionModelo.creado_en.label("creado_en"),
            )
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .join(
                VersionPerfilPuestoModelo,
                VersionPerfilPuestoModelo.id == PostulacionModelo.version_perfil_id,
            )
            .join(PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id)
            .join(ClienteModelo, ClienteModelo.id == PostulacionModelo.cliente_id)
            .join(ConvocatoriaModelo, ConvocatoriaModelo.id == PostulacionModelo.convocatoria_id)
            .where(_filtro_clientes(PostulacionModelo.cliente_id, clientes))
            .order_by(PostulacionModelo.creado_en.desc()),
            "documentos": select(
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                DocumentoCandidatoModelo.nombre_original.label("archivo"),
                DocumentoCandidatoModelo.tipo_mime.label("tipo"),
                DocumentoCandidatoModelo.tamano_bytes.label("bytes"),
            )
            .join(CandidatoModelo, CandidatoModelo.id == DocumentoCandidatoModelo.candidato_id)
            .where(_filtro_clientes(DocumentoCandidatoModelo.cliente_id, clientes)),
            "evaluaciones": select(
                EvaluacionModelo.id.label("id"),
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                (PerfilPuestoModelo.codigo + " · " + PerfilPuestoModelo.titulo).label("perfil"),
                EvaluacionModelo.puntaje_documental.label("puntaje"),
                EvaluacionModelo.requiere_revision.label("requiere_revision"),
            )
            .join(PostulacionModelo, PostulacionModelo.id == EvaluacionModelo.postulacion_id)
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .join(
                VersionPerfilPuestoModelo,
                VersionPerfilPuestoModelo.id == PostulacionModelo.version_perfil_id,
            )
            .join(PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id)
            .where(_filtro_clientes(EvaluacionModelo.cliente_id, clientes)),
            "revisiones": select(
                RevisionHumanaModelo.id.label("id"),
                EvaluacionModelo.id.label("evaluacion_id"),
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                RevisionHumanaModelo.estado.label("estado"),
                RevisionHumanaModelo.creado_en.label("creado_en"),
            )
            .join(EvaluacionModelo, EvaluacionModelo.id == RevisionHumanaModelo.evaluacion_id)
            .join(PostulacionModelo, PostulacionModelo.id == EvaluacionModelo.postulacion_id)
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .where(_filtro_clientes(EvaluacionModelo.cliente_id, clientes)),
            "lotes": select(
                LoteImportacionModelo.tipo.label("tipo"),
                LoteImportacionModelo.estado.label("estado"),
                LoteImportacionModelo.creado_en.label("creado_en"),
            ).where(_filtro_clientes(LoteImportacionModelo.cliente_id, clientes)),
            "excolaboradores": select(
                func.substr(ExcolaboradorModelo.documento_hash, 1, 10).label("referencia"),
                ExcolaboradorModelo.elegible_reingreso.label("elegible"),
                ExcolaboradorModelo.creado_en.label("creado_en"),
            ).where(_filtro_clientes(ExcolaboradorModelo.cliente_id, clientes)),
            "exclusiones": select(
                ReporteExclusionModelo.id.label("id"),
                ReporteExclusionModelo.estado.label("estado"),
                ReporteExclusionModelo.creado_en.label("creado_en"),
            ).where(_filtro_clientes(ReporteExclusionModelo.cliente_id, clientes)),
            "trabajos": select(
                TrabajoAgenteModelo.id.label("id"),
                TrabajoAgenteModelo.tipo.label("tipo"),
                TrabajoAgenteModelo.estado.label("estado"),
                TrabajoAgenteModelo.intentos.label("intentos"),
                TrabajoAgenteModelo.error.label("error"),
            ).where(_filtro_clientes(TrabajoAgenteModelo.cliente_id, clientes)),
        }
        consulta = consultas.get(modulo)
        if consulta is None:
            return []
        filas = self.sesion.execute(consulta.limit(min(limite, 200))).mappings().all()
        return [dict(fila) for fila in filas]

    def listar_opciones_operativas(
        self, clientes: frozenset[str]
    ) -> dict[str, list[dict[str, object]]]:
        clientes_disponibles = self.sesion.execute(
            select(ClienteModelo.id, ClienteModelo.codigo, ClienteModelo.nombre)
            .where(ClienteModelo.activo.is_(True), _filtro_clientes(ClienteModelo.id, clientes))
            .order_by(ClienteModelo.nombre)
        ).mappings()
        candidatos = self.sesion.execute(
            select(
                CandidatoModelo.id,
                CandidatoModelo.cliente_id,
                ClienteModelo.nombre.label("cliente_nombre"),
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("nombre"),
            )
            .join(ClienteModelo, ClienteModelo.id == CandidatoModelo.cliente_id)
            .where(_filtro_clientes(CandidatoModelo.cliente_id, clientes))
            .order_by(CandidatoModelo.apellidos, CandidatoModelo.nombres)
        ).mappings()
        perfiles = self.sesion.execute(
            select(
                PerfilPuestoModelo.id,
                PerfilPuestoModelo.cliente_id,
                PerfilPuestoModelo.codigo,
                PerfilPuestoModelo.titulo,
            )
            .where(
                PerfilPuestoModelo.activo.is_(True),
                _filtro_clientes(PerfilPuestoModelo.cliente_id, clientes),
            )
            .order_by(PerfilPuestoModelo.codigo)
        ).mappings()
        versiones = self.sesion.execute(
            select(
                VersionPerfilPuestoModelo.id,
                PerfilPuestoModelo.cliente_id,
                PerfilPuestoModelo.id.label("perfil_id"),
                PerfilPuestoModelo.codigo,
                PerfilPuestoModelo.codigo.label("perfil_codigo"),
                PerfilPuestoModelo.titulo,
                PerfilPuestoModelo.titulo.label("perfil_titulo"),
                VersionPerfilPuestoModelo.numero,
                VersionPerfilPuestoModelo.numero.label("version_numero"),
            )
            .join(PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id)
            .where(
                VersionPerfilPuestoModelo.publicado.is_(True),
                PerfilPuestoModelo.activo.is_(True),
                _filtro_clientes(PerfilPuestoModelo.cliente_id, clientes),
            )
            .order_by(PerfilPuestoModelo.codigo, VersionPerfilPuestoModelo.numero.desc())
        ).mappings()
        convocatorias = self.sesion.execute(
            select(
                ConvocatoriaModelo.id,
                ConvocatoriaModelo.cliente_id,
                ConvocatoriaModelo.version_perfil_id,
                ConvocatoriaModelo.codigo,
                ConvocatoriaModelo.vacantes_total,
                ConvocatoriaModelo.estado,
                PerfilPuestoModelo.codigo.label("perfil_codigo"),
                PerfilPuestoModelo.titulo.label("perfil_titulo"),
            )
            .join(
                VersionPerfilPuestoModelo,
                VersionPerfilPuestoModelo.id == ConvocatoriaModelo.version_perfil_id,
            )
            .join(PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id)
            .where(
                _filtro_clientes(ConvocatoriaModelo.cliente_id, clientes),
                ConvocatoriaModelo.es_compatibilidad.is_(False),
            )
            .order_by(ConvocatoriaModelo.codigo)
        ).mappings()
        postulaciones = self.sesion.execute(
            select(
                PostulacionModelo.id,
                PostulacionModelo.cliente_id,
                PostulacionModelo.candidato_id,
                PostulacionModelo.version_perfil_id,
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                PerfilPuestoModelo.codigo.label("perfil_codigo"),
                VersionPerfilPuestoModelo.numero.label("version_numero"),
            )
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .join(
                VersionPerfilPuestoModelo,
                VersionPerfilPuestoModelo.id == PostulacionModelo.version_perfil_id,
            )
            .join(PerfilPuestoModelo, PerfilPuestoModelo.id == VersionPerfilPuestoModelo.perfil_id)
            .where(_filtro_clientes(PostulacionModelo.cliente_id, clientes))
            .order_by(PostulacionModelo.creado_en.desc())
        ).mappings()
        return {
            "clientes": [dict(item) for item in clientes_disponibles],
            "candidatos": [dict(item) for item in candidatos],
            "perfiles": [dict(item) for item in perfiles],
            "versiones": [dict(item) for item in versiones],
            "convocatorias": [dict(item) for item in convocatorias],
            "postulaciones": [dict(item) for item in postulaciones],
        }

    def crear_lote(
        self, datos: dict[str, object], filas: list[dict[str, object]]
    ) -> dict[str, object]:
        misma_clave = self.sesion.scalar(
            select(LoteImportacionModelo).where(
                LoteImportacionModelo.clave_idempotencia == datos["clave_idempotencia"]
            )
        )
        if misma_clave and (
            misma_clave.hash_archivo != datos["hash_archivo"]
            or misma_clave.cliente_id != datos["cliente_id"]
            or misma_clave.tipo != datos["tipo"]
        ):
            raise ConflictoError("La clave de idempotencia ya identifica otro archivo")
        existente = misma_clave or self.sesion.scalar(
            select(LoteImportacionModelo).where(
                LoteImportacionModelo.hash_archivo == datos["hash_archivo"],
                LoteImportacionModelo.cliente_id == datos["cliente_id"],
                LoteImportacionModelo.tipo == datos["tipo"],
            )
        )
        if existente is not None:
            return {
                "id": existente.id,
                "estado": existente.estado,
                "filas": self.sesion.scalar(
                    select(func.count())
                    .select_from(FilaImportacionModelo)
                    .where(FilaImportacionModelo.lote_id == existente.id)
                )
                or 0,
                "reutilizado": True,
            }
        lote = LoteImportacionModelo(id=nuevo_id(), **datos)
        self.sesion.add(lote)
        self.sesion.flush()
        for numero, fila in enumerate(filas, start=1):
            normalizada = {str(clave).strip().casefold(): valor for clave, valor in fila.items()}
            self.sesion.add(
                FilaImportacionModelo(
                    id=nuevo_id(),
                    lote_id=lote.id,
                    numero=numero,
                    datos=normalizada,
                    clasificacion="pendiente_validacion",
                    errores=[],
                )
            )
        self.sesion.flush()
        self._reclasificar_filas(lote)
        return {"id": lote.id, "estado": lote.estado, "filas": len(filas), "reutilizado": False}

    @staticmethod
    def _columnas_permitidas(tipo: str) -> set[str]:
        if tipo == "excolaboradores":
            return {"documento", "elegible_reingreso"}
        return {
            "nombres",
            "apellidos",
            "tipo_documento",
            "documento",
            "correo",
            "telefono",
        }

    def _reclasificar_filas(self, lote: LoteImportacionModelo) -> None:
        filas = list(
            self.sesion.scalars(
                select(FilaImportacionModelo)
                .where(FilaImportacionModelo.lote_id == lote.id)
                .order_by(FilaImportacionModelo.numero)
            )
        )
        requeridas = {"documento"} if lote.tipo == "excolaboradores" else {"nombres", "apellidos"}
        documentos_lote: set[str] = set()
        for fila in filas:
            datos = fila.datos
            errores: list[str] = []
            if not any(str(valor or "").strip() for valor in datos.values()):
                errores.append("La fila esta vacia")
            faltantes = [
                campo for campo in requeridas if not str(datos.get(campo, "") or "").strip()
            ]
            errores.extend(f"Falta el campo obligatorio: {campo}" for campo in sorted(faltantes))
            correo = normalizar_correo(str(datos.get("correo") or ""))
            if datos.get("correo") and (not correo or "@" not in correo):
                errores.append("El correo no tiene un formato valido")
            fila.errores = errores
            if errores:
                fila.clasificacion = "invalida"
                continue
            if lote.tipo == "excolaboradores":
                fila.clasificacion = "lista"
                continue
            documento = normalizar_documento(str(datos.get("documento") or ""))
            existente_documento = bool(
                documento
                and self.sesion.scalar(
                    select(CandidatoModelo.id).where(
                        CandidatoModelo.cliente_id == lote.cliente_id,
                        CandidatoModelo.documento_normalizado == documento,
                    )
                )
            )
            duplicada_lote = bool(documento and documento in documentos_lote)
            if documento:
                documentos_lote.add(documento)
            mismo_nombre = self.sesion.scalar(
                select(CandidatoModelo.id).where(
                    CandidatoModelo.cliente_id == lote.cliente_id,
                    func.lower(CandidatoModelo.nombres)
                    == str(datos.get("nombres", "")).strip().casefold(),
                    func.lower(CandidatoModelo.apellidos)
                    == str(datos.get("apellidos", "")).strip().casefold(),
                )
            )
            if existente_documento or duplicada_lote:
                fila.clasificacion = "exacta"
            elif mismo_nombre:
                fila.clasificacion = "requiere_revision"
                fila.errores = ["Coincidencia de nombre: requiere revision humana"]
            else:
                fila.clasificacion = "nueva"

    def aplicar_mapeo_lote(self, lote_id: str, mapeo: dict[str, str]) -> dict[str, object]:
        lote = self.sesion.get(LoteImportacionModelo, lote_id)
        if not lote:
            raise ConflictoError("Lote no encontrado")
        if lote.estado != "staging":
            raise ConflictoError("Solo se puede mapear un lote en staging")
        normalizado = {
            origen.strip().casefold(): destino.strip().casefold()
            for origen, destino in mapeo.items()
        }
        if not set(normalizado.values()).issubset(self._columnas_permitidas(lote.tipo)):
            raise EntradaInvalidaError("El mapeo contiene columnas de destino no permitidas")
        filas = self.sesion.scalars(
            select(FilaImportacionModelo).where(FilaImportacionModelo.lote_id == lote_id)
        )
        for fila in filas:
            corregida: dict[str, object] = {}
            for clave, valor in fila.datos.items():
                destino = normalizado.get(str(clave).casefold(), str(clave).casefold())
                if (
                    destino in corregida
                    and corregida[destino] is not None
                    and corregida[destino] != ""
                ):
                    raise EntradaInvalidaError(f"Varias columnas apuntan a {destino}")
                corregida[destino] = valor
            fila.datos = corregida
        self._reclasificar_filas(lote)
        self.sesion.flush()
        return self.obtener_lote(lote_id) or {}

    def corregir_fila_lote(
        self, lote_id: str, numero: int, datos: dict[str, object]
    ) -> dict[str, object]:
        lote = self.sesion.get(LoteImportacionModelo, lote_id)
        if not lote:
            raise ConflictoError("Lote no encontrado")
        if lote.estado != "staging":
            raise ConflictoError("Solo se puede corregir un lote en staging")
        fila = self.sesion.scalar(
            select(FilaImportacionModelo).where(
                FilaImportacionModelo.lote_id == lote_id,
                FilaImportacionModelo.numero == numero,
            )
        )
        if not fila:
            raise EntradaInvalidaError("Fila no encontrada")
        permitidas = self._columnas_permitidas(lote.tipo)
        correcciones = {str(clave).strip().casefold(): valor for clave, valor in datos.items()}
        if not set(correcciones).issubset(permitidas):
            raise EntradaInvalidaError("La correccion contiene campos no permitidos")
        fila.datos = {**fila.datos, **correcciones}
        self._reclasificar_filas(lote)
        self.sesion.flush()
        return self.obtener_lote(lote_id) or {}

    def obtener_lote(self, lote_id: str) -> dict[str, object] | None:
        lote = self.sesion.get(LoteImportacionModelo, lote_id)
        if not lote:
            return None
        filas = self.sesion.scalars(
            select(FilaImportacionModelo)
            .where(FilaImportacionModelo.lote_id == lote_id)
            .order_by(FilaImportacionModelo.numero)
        )
        return {
            "id": lote.id,
            "cliente_id": lote.cliente_id,
            "tipo": lote.tipo,
            "estado": lote.estado,
            "filas": [
                {
                    "numero": fila.numero,
                    "datos": fila.datos,
                    "clasificacion": fila.clasificacion,
                    "errores": fila.errores,
                }
                for fila in filas
            ],
        }

    def confirmar_lote(self, lote_id: str) -> dict[str, object]:
        lote = self.sesion.get(LoteImportacionModelo, lote_id)
        if not lote:
            raise ConflictoError("Lote no encontrado")
        if lote.estado == "confirmado":
            return {"id": lote.id, "estado": lote.estado, "reutilizado": True}
        bloqueadas = (
            self.sesion.scalar(
                select(func.count())
                .select_from(FilaImportacionModelo)
                .where(
                    FilaImportacionModelo.lote_id == lote_id,
                    FilaImportacionModelo.clasificacion.in_(
                        ["invalida", "requiere_revision", "pendiente_validacion"]
                    ),
                )
            )
            or 0
        )
        if bloqueadas:
            raise ConflictoError("El lote contiene filas invalidas o pendientes de revision")
        filas = list(
            self.sesion.scalars(
                select(FilaImportacionModelo)
                .where(FilaImportacionModelo.lote_id == lote_id)
                .order_by(FilaImportacionModelo.numero)
            )
        )
        if lote.tipo == "candidatos":
            importadas, omitidas = self._importar_candidatos(lote, filas)
        elif lote.tipo == "excolaboradores":
            importadas, omitidas = self._importar_excolaboradores(lote, filas)
        else:
            raise EntradaInvalidaError("Tipo de lote no soportado")
        lote.estado = "confirmado"
        self.sesion.flush()
        return {
            "id": lote.id,
            "estado": lote.estado,
            "reutilizado": False,
            "importadas": importadas,
            "omitidas": omitidas,
        }

    def cancelar_lote(self, lote_id: str) -> dict[str, object]:
        lote = self.sesion.get(LoteImportacionModelo, lote_id)
        if not lote:
            raise ConflictoError("Lote no encontrado")
        if lote.estado == "cancelado":
            return {"id": lote.id, "estado": lote.estado, "reutilizado": True}
        if lote.estado != "staging":
            raise ConflictoError("Solo se puede cancelar un lote en staging")
        lote.estado = "cancelado"
        self.sesion.flush()
        return {"id": lote.id, "estado": lote.estado, "reutilizado": False}

    def _importar_candidatos(
        self, lote: LoteImportacionModelo, filas: list[FilaImportacionModelo]
    ) -> tuple[int, int]:
        importadas = 0
        for fila in filas:
            if fila.clasificacion != "nueva":
                continue
            datos = fila.datos
            candidato = Candidato(
                cliente_id=lote.cliente_id,
                nombres=str(datos.get("nombres", "")).strip(),
                apellidos=str(datos.get("apellidos", "")).strip(),
                tipo_documento=str(datos.get("tipo_documento") or "") or None,
                documento_normalizado=normalizar_documento(str(datos.get("documento") or "")),
                correo=normalizar_correo(str(datos.get("correo") or "")),
                telefono=str(datos.get("telefono") or "").strip() or None,
                fuente="importacion",
            )
            self.sesion.add(_candidato_a_modelo(candidato))
            fila.clasificacion = "importada"
            importadas += 1
        return importadas, len(filas) - importadas

    def _importar_excolaboradores(
        self, lote: LoteImportacionModelo, filas: list[FilaImportacionModelo]
    ) -> tuple[int, int]:
        lote_ex = self.sesion.scalar(
            select(LoteExcolaboradoresModelo).where(
                LoteExcolaboradoresModelo.hash_archivo == lote.hash_archivo
            )
        )
        if lote_ex is None:
            lote_ex = LoteExcolaboradoresModelo(
                id=nuevo_id(),
                cliente_id=lote.cliente_id,
                hash_archivo=lote.hash_archivo,
                estado="confirmado",
            )
            self.sesion.add(lote_ex)
            self.sesion.flush()
        importadas = 0
        for fila in filas:
            documento = normalizar_documento(str(fila.datos.get("documento") or ""))
            hash_documento = hashlib.sha256((documento or "").encode()).hexdigest()
            existe = self.sesion.scalar(
                select(ExcolaboradorModelo.id).where(
                    ExcolaboradorModelo.lote_id == lote_ex.id,
                    ExcolaboradorModelo.documento_hash == hash_documento,
                )
            )
            if not documento or existe:
                continue
            elegible_texto = str(fila.datos.get("elegible_reingreso") or "").casefold()
            elegible = (
                True
                if elegible_texto in {"si", "sí", "true", "1"}
                else (False if elegible_texto in {"no", "false", "0"} else None)
            )
            self.sesion.add(
                ExcolaboradorModelo(
                    id=nuevo_id(),
                    lote_id=lote_ex.id,
                    cliente_id=lote.cliente_id,
                    documento_hash=hash_documento,
                    elegible_reingreso=elegible,
                )
            )
            fila.clasificacion = "importada"
            importadas += 1
        return importadas, len(filas) - importadas

    def verificar_excolaborador(self, cliente_id: str, documento_hash: str) -> dict[str, object]:
        coincidencia = self.sesion.scalar(
            select(ExcolaboradorModelo.id).where(
                ExcolaboradorModelo.cliente_id == cliente_id,
                ExcolaboradorModelo.documento_hash == documento_hash,
            )
        )
        return {"coincidencia": coincidencia is not None}

    def candidatos_para_exclusion(
        self, cliente_id: str, filtros: dict[str, object]
    ) -> list[dict[str, object]]:
        consulta = select(CandidatoModelo).where(CandidatoModelo.cliente_id == cliente_id)
        estado = str(filtros.get("estado") or "").strip()
        if estado:
            consulta = consulta.where(CandidatoModelo.estado == estado)
        candidatos = self.sesion.scalars(consulta)
        return [
            {
                "persona_id": candidato.id,
                "documento": candidato.documento_normalizado or "",
                "estado": candidato.estado,
                "motivo_generico": "No continua en el proceso",
                "vigente": False,
            }
            for candidato in candidatos
        ]

    def guardar_reporte_exclusion(
        self,
        cliente_id: str,
        filtros: dict[str, object],
        entradas: list[dict[str, str]],
        hash_contenido: str,
    ) -> dict[str, object]:
        candidatos = self.sesion.scalars(
            select(ReporteExclusionModelo).where(
                ReporteExclusionModelo.cliente_id == cliente_id,
                ReporteExclusionModelo.hash_contenido == hash_contenido,
            )
        )
        for existente in candidatos:
            if existente.filtros == filtros:
                total = self.sesion.scalar(
                    select(func.count())
                    .select_from(EntradaExclusionModelo)
                    .where(EntradaExclusionModelo.reporte_id == existente.id)
                )
                return {
                    "id": existente.id,
                    "estado": existente.estado,
                    "total": total or 0,
                    "hash_contenido": existente.hash_contenido,
                    "reutilizado": True,
                }
        reporte = ReporteExclusionModelo(
            id=nuevo_id(),
            cliente_id=cliente_id,
            filtros=filtros,
            hash_contenido=hash_contenido,
            estado="listo",
        )
        self.sesion.add(reporte)
        self.sesion.flush()
        for entrada in entradas:
            self.sesion.add(
                EntradaExclusionModelo(
                    id=nuevo_id(),
                    reporte_id=reporte.id,
                    documento=entrada["documento"],
                    motivo_generico=entrada["motivo_generico"],
                )
            )
        self.sesion.flush()
        return {
            "id": reporte.id,
            "estado": reporte.estado,
            "total": len(entradas),
            "hash_contenido": hash_contenido,
            "reutilizado": False,
        }

    def obtener_reporte_exclusion(self, reporte_id: str) -> dict[str, object] | None:
        reporte = self.sesion.get(ReporteExclusionModelo, reporte_id)
        if not reporte:
            return None
        entradas = self.sesion.scalars(
            select(EntradaExclusionModelo)
            .where(EntradaExclusionModelo.reporte_id == reporte_id)
            .order_by(EntradaExclusionModelo.documento)
        )
        return {
            "id": reporte.id,
            "cliente_id": reporte.cliente_id,
            "filtros": reporte.filtros,
            "hash_contenido": reporte.hash_contenido,
            "entradas": [
                {
                    "documento": entrada.documento,
                    "motivo_generico": entrada.motivo_generico,
                }
                for entrada in entradas
            ],
        }

    def actualizar_reporte_exclusion(
        self,
        reporte_id: str,
        filtros: dict[str, object],
        entradas: list[dict[str, str]],
        hash_contenido: str,
    ) -> dict[str, object]:
        reporte = self.sesion.get(ReporteExclusionModelo, reporte_id)
        if not reporte:
            raise ConflictoError("Reporte no encontrado")
        reporte.filtros = filtros
        reporte.hash_contenido = hash_contenido
        self.sesion.execute(
            delete(EntradaExclusionModelo).where(EntradaExclusionModelo.reporte_id == reporte_id)
        )
        for entrada in entradas:
            self.sesion.add(
                EntradaExclusionModelo(
                    id=nuevo_id(),
                    reporte_id=reporte.id,
                    documento=entrada["documento"],
                    motivo_generico=entrada["motivo_generico"],
                )
            )
        self.sesion.flush()
        return {
            "id": reporte.id,
            "estado": reporte.estado,
            "total": len(entradas),
            "hash_contenido": hash_contenido,
        }


class UnidadTrabajoSqlalchemy:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion
        self.datos = RepositorioSqlalchemy(sesion)

    def __enter__(self) -> UnidadTrabajoSqlalchemy:
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            if error is None:
                self.confirmar()
            else:
                self.revertir()
        finally:
            self.sesion.close()

    def confirmar(self) -> None:
        self.sesion.commit()

    def revertir(self) -> None:
        self.sesion.rollback()


class FabricaUnidadTrabajoSqlalchemy:
    def __init__(self, fabrica_sesiones: Any) -> None:
        self._fabrica = fabrica_sesiones

    def __call__(self) -> UnidadTrabajoSqlalchemy:
        return UnidadTrabajoSqlalchemy(self._fabrica.nueva())
