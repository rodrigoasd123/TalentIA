"""Adaptador SQLAlchemy para los puertos de aplicacion."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any

from sqlalchemy import delete, func, or_, select, true, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from talentia.modules.candidates.domain.modelos import (
    Candidato,
    EstadoCandidato,
    normalizar_correo,
    normalizar_documento,
    tokens_nombre,
)
from talentia.shared.application.errores import ConflictoError, EntradaInvalidaError
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.modelos_orm import (
    AsignacionUsuarioClienteModelo,
    CandidatoModelo,
    ClienteModelo,
    CorreccionCampoModelo,
    DocumentoCandidatoModelo,
    EntradaExclusionModelo,
    EvaluacionModelo,
    EvaluacionRequisitoModelo,
    EventoAuditoriaModelo,
    EventoCandidatoModelo,
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
            "roles": list(roles),
            "clientes": list(clientes),
        }

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
        elif not asignar and existente is not None:
            self.sesion.execute(delete(UsuarioRolModelo).filter_by(**clave))
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
        elif not asignar and existente is not None:
            self.sesion.execute(delete(AsignacionUsuarioClienteModelo).filter_by(**clave))
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
        sentencia = select(CandidatoModelo).where(CandidatoModelo.cliente_id == cliente_id)
        if condiciones:
            sentencia = sentencia.where(or_(*condiciones))
        else:
            sentencia = sentencia.limit(200)
        encontrados: list[dict[str, object]] = []
        for modelo in self.sesion.scalars(sentencia):
            nombre_tokens = tokens_nombre(f"{modelo.nombres} {modelo.apellidos}")
            criterio = "nombre" if tokens and nombre_tokens == tokens else ""
            if documento and modelo.documento_normalizado == documento:
                criterio = "documento"
            elif correo and modelo.correo == correo:
                criterio = "correo"
            elif telefono and (modelo.telefono or "").endswith(telefono):
                criterio = "telefono"
            if criterio:
                encontrados.append({"id": modelo.id, "criterio": criterio})
        return encontrados

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

    def traza_candidato(self, candidato_id: str, limite: int) -> list[dict[str, object]]:
        eventos = self.sesion.scalars(
            select(EventoCandidatoModelo)
            .where(EventoCandidatoModelo.candidato_id == candidato_id)
            .order_by(EventoCandidatoModelo.ocurrido_en.desc())
            .limit(limite)
        )
        return [
            {
                "tipo": evento.tipo,
                "actor_id": evento.actor_id,
                "detalle": evento.detalle,
                "ocurrido_en": evento.ocurrido_en,
            }
            for evento in eventos
        ]

    def crear_perfil(self, datos: dict[str, object]) -> dict[str, object]:
        modelo = PerfilPuestoModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        self.sesion.flush()
        return {"id": modelo.id, "cliente_id": modelo.cliente_id, "codigo": modelo.codigo}

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

    def crear_postulacion(self, datos: dict[str, object]) -> dict[str, object]:
        modelo = PostulacionModelo(id=nuevo_id(), **datos)
        self.sesion.add(modelo)
        try:
            self.sesion.flush()
        except IntegrityError as exc:
            raise ConflictoError("La postulacion ya existe") from exc
        return {"id": modelo.id, "estado": modelo.estado, "cliente_id": modelo.cliente_id}

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
        revision = self.sesion.scalar(
            select(RevisionHumanaModelo).where(
                RevisionHumanaModelo.evaluacion_id == evaluacion_id,
                RevisionHumanaModelo.estado == "pendiente",
            )
        )
        if revision is None:
            raise ConflictoError("La evaluacion no tiene una revision pendiente")
        revision.estado = decision
        revision.revisor_id = revisor_id
        revision.comentario = comentario
        revision.version += 1
        for correccion in correcciones:
            self.sesion.add(
                CorreccionCampoModelo(
                    id=nuevo_id(),
                    revision_id=revision.id,
                    campo=str(correccion["campo"]),
                    valor_anterior=correccion.get("valor_anterior"),
                    valor_nuevo=correccion["valor_nuevo"],
                )
            )
        self.sesion.flush()
        return {
            "id": revision.id,
            "evaluacion_id": evaluacion_id,
            "estado": revision.estado,
            "revisor_id": revision.revisor_id,
            "comentario": revision.comentario,
            "correcciones": len(correcciones),
            "version": revision.version,
        }

    def metricas(self, clientes: frozenset[str]) -> dict[str, object]:
        filtro = CandidatoModelo.cliente_id.in_(clientes) if clientes else true()
        candidatos = (
            self.sesion.scalar(select(func.count()).select_from(CandidatoModelo).where(filtro)) or 0
        )
        postulaciones = (
            self.sesion.scalar(
                select(func.count())
                .select_from(PostulacionModelo)
                .where(PostulacionModelo.cliente_id.in_(clientes) if clientes else true())
            )
            or 0
        )
        trabajos_pendientes = (
            self.sesion.scalar(
                select(func.count())
                .select_from(TrabajoAgenteModelo)
                .where(
                    TrabajoAgenteModelo.estado.in_(["pendiente", "reservado"]),
                    TrabajoAgenteModelo.cliente_id.in_(clientes) if clientes else true(),
                )
            )
            or 0
        )
        return {
            "candidatos": candidatos,
            "postulaciones": postulaciones,
            "trabajos_pendientes": trabajos_pendientes,
            "muestra_suficiente": postulaciones >= 20,
            "ahorro_validado": False,
        }

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
                PerfilPuestoModelo.codigo.label("codigo"),
                PerfilPuestoModelo.titulo.label("titulo"),
                PerfilPuestoModelo.activo.label("activo"),
                PerfilPuestoModelo.creado_en.label("creado_en"),
            ).where(_filtro_clientes(PerfilPuestoModelo.cliente_id, clientes)),
            "postulaciones": select(
                (CandidatoModelo.nombres + " " + CandidatoModelo.apellidos).label("candidato"),
                PostulacionModelo.fuente.label("fuente"),
                PostulacionModelo.estado.label("estado"),
                PostulacionModelo.creado_en.label("creado_en"),
            )
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .where(_filtro_clientes(PostulacionModelo.cliente_id, clientes)),
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
                EvaluacionModelo.puntaje_documental.label("puntaje"),
                EvaluacionModelo.requiere_revision.label("requiere_revision"),
            )
            .join(PostulacionModelo, PostulacionModelo.id == EvaluacionModelo.postulacion_id)
            .join(CandidatoModelo, CandidatoModelo.id == PostulacionModelo.candidato_id)
            .where(_filtro_clientes(EvaluacionModelo.cliente_id, clientes)),
            "revisiones": select(
                RevisionHumanaModelo.id.label("id"),
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

    def crear_lote(
        self, datos: dict[str, object], filas: list[dict[str, object]]
    ) -> dict[str, object]:
        existente = self.sesion.scalar(
            select(LoteImportacionModelo).where(
                or_(
                    LoteImportacionModelo.hash_archivo == datos["hash_archivo"],
                    LoteImportacionModelo.clave_idempotencia == datos["clave_idempotencia"],
                )
            )
        )
        if existente:
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
        tipo = str(datos["tipo"])
        requeridas = {"documento"} if tipo == "excolaboradores" else {"nombres", "apellidos"}
        encabezados = {str(clave).strip().casefold() for clave in filas[0] if clave}
        if not requeridas.issubset(encabezados):
            raise EntradaInvalidaError(
                "Faltan columnas obligatorias: " + ", ".join(sorted(requeridas - encabezados))
            )
        documentos_lote: set[str] = set()
        for numero, fila in enumerate(filas, start=1):
            normalizada = {str(clave).strip().casefold(): valor for clave, valor in fila.items()}
            errores = ["fila_vacia"] if not any(valor for valor in normalizada.values()) else []
            if any(not str(normalizada.get(campo, "") or "").strip() for campo in requeridas):
                errores.append("campo_obligatorio_vacio")
            clasificacion = "invalida" if errores else "lista"
            if tipo == "candidatos" and not errores:
                documento = normalizar_documento(str(normalizada.get("documento", "") or ""))
                existente_documento = bool(
                    documento
                    and self.sesion.scalar(
                        select(CandidatoModelo.id).where(
                            CandidatoModelo.cliente_id == datos["cliente_id"],
                            CandidatoModelo.documento_normalizado == documento,
                        )
                    )
                )
                if documento and documento in documentos_lote:
                    existente_documento = True
                if documento:
                    documentos_lote.add(documento)
                clasificacion = "exacta" if existente_documento else "nueva"
            self.sesion.add(
                FilaImportacionModelo(
                    id=nuevo_id(),
                    lote_id=lote.id,
                    numero=numero,
                    datos=normalizada,
                    clasificacion=clasificacion,
                    errores=errores,
                )
            )
        self.sesion.flush()
        return {"id": lote.id, "estado": lote.estado, "filas": len(filas), "reutilizado": False}

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
        invalidas = (
            self.sesion.scalar(
                select(func.count())
                .select_from(FilaImportacionModelo)
                .where(
                    FilaImportacionModelo.lote_id == lote_id,
                    FilaImportacionModelo.clasificacion == "invalida",
                )
            )
            or 0
        )
        if invalidas:
            raise ConflictoError("El lote contiene filas invalidas")
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

    def candidatos_para_exclusion(self, cliente_id: str) -> list[dict[str, object]]:
        candidatos = self.sesion.scalars(
            select(CandidatoModelo).where(CandidatoModelo.cliente_id == cliente_id)
        )
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
