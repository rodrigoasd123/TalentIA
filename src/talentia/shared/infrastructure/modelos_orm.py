"""Modelo relacional greenfield. Las reglas de negocio viven fuera del ORM."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class MarcasTiempo:
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
    version: Mapped[int] = mapped_column(Integer, default=1)


class RolModelo(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    permisos: Mapped[list[str]] = mapped_column(JSON, default=list)


class UsuarioModelo(Base, MarcasTiempo):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    correo: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class UsuarioRolModelo(Base):
    __tablename__ = "user_roles"
    usuario_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rol_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class ClienteModelo(Base, MarcasTiempo):
    __tablename__ = "clients"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(160))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class AsignacionUsuarioClienteModelo(Base):
    __tablename__ = "user_client_assignments"
    usuario_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    cliente_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True
    )


class CandidatoModelo(Base, MarcasTiempo):
    __tablename__ = "candidates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(160))
    tipo_documento: Mapped[str | None] = mapped_column(String(20))
    documento_normalizado: Mapped[str | None] = mapped_column(String(64))
    correo: Mapped[str | None] = mapped_column(String(255))
    telefono: Mapped[str | None] = mapped_column(String(40))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    ubicacion: Mapped[str | None] = mapped_column(String(160))
    fuente: Mapped[str | None] = mapped_column(String(80))
    reclutador: Mapped[str | None] = mapped_column(String(160))
    perfil_solicitado: Mapped[str | None] = mapped_column(String(160))
    conocimiento_tecnico: Mapped[str | None] = mapped_column(Text)
    disponibilidad: Mapped[str | None] = mapped_column(String(100))
    expectativa_salarial: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    ctc_rol: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    bgc_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary)
    equifax_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary)
    estado: Mapped[str] = mapped_column(String(32), index=True)
    etiquetas: Mapped[list[str]] = mapped_column(JSON, default=list)
    __table_args__ = (
        UniqueConstraint(
            "cliente_id", "documento_normalizado", name="uq_candidate_client_document"
        ),
        Index("ix_candidate_client_email", "cliente_id", "correo"),
        Index("ix_candidate_client_phone", "cliente_id", "telefono"),
    )


class IdentidadCandidatoModelo(Base, MarcasTiempo):
    __tablename__ = "candidate_identities"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    candidato_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(30))
    valor_normalizado: Mapped[str] = mapped_column(String(255), index=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class EventoCandidatoModelo(Base):
    __tablename__ = "candidate_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    candidato_id: Mapped[str] = mapped_column(String(32), ForeignKey("candidates.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(80))
    actor_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    detalle: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class LoteExcolaboradoresModelo(Base, MarcasTiempo):
    __tablename__ = "former_employee_batches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    hash_archivo: Mapped[str] = mapped_column(String(64), unique=True)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")


class ExcolaboradorModelo(Base, MarcasTiempo):
    __tablename__ = "former_employees"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lote_id: Mapped[str] = mapped_column(String(32), ForeignKey("former_employee_batches.id"))
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    documento_hash: Mapped[str] = mapped_column(String(64), index=True)
    elegible_reingreso: Mapped[bool | None] = mapped_column(Boolean)


class PerfilPuestoModelo(Base, MarcasTiempo):
    __tablename__ = "job_profiles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(50))
    titulo: Mapped[str] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("cliente_id", "codigo", name="uq_profile_code"),)


class VersionPerfilPuestoModelo(Base, MarcasTiempo):
    __tablename__ = "job_profile_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    perfil_id: Mapped[str] = mapped_column(String(32), ForeignKey("job_profiles.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    requisitos: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    ctc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    publicado: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("perfil_id", "numero", name="uq_profile_version"),)


class PostulacionModelo(Base, MarcasTiempo):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    candidato_id: Mapped[str] = mapped_column(String(32), ForeignKey("candidates.id"), index=True)
    version_perfil_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("job_profile_versions.id"), index=True
    )
    fuente: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(32), index=True)
    clave_idempotencia: Mapped[str] = mapped_column(String(80), unique=True)


class DocumentoCandidatoModelo(Base, MarcasTiempo):
    __tablename__ = "candidate_documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    candidato_id: Mapped[str] = mapped_column(String(32), ForeignKey("candidates.id"), index=True)
    nombre_original: Mapped[str] = mapped_column(String(255))
    tipo_mime: Mapped[str] = mapped_column(String(100))
    hash_sha256: Mapped[str] = mapped_column(String(64), index=True)
    ruta_almacenamiento: Mapped[str] = mapped_column(String(500))
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("candidato_id", "hash_sha256", name="uq_document_hash"),)


class ExtraccionDocumentoModelo(Base, MarcasTiempo):
    __tablename__ = "document_extractions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    documento_id: Mapped[str] = mapped_column(String(32), ForeignKey("candidate_documents.id"))
    estado: Mapped[str] = mapped_column(String(30))
    texto_sanitizado: Mapped[str | None] = mapped_column(Text)
    campos: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    referencias: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String(300))


class SugerenciaCampoModelo(Base, MarcasTiempo):
    __tablename__ = "field_suggestions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    extraccion_id: Mapped[str] = mapped_column(String(32), ForeignKey("document_extractions.id"))
    campo: Mapped[str] = mapped_column(String(80))
    valor: Mapped[dict[str, object]] = mapped_column(JSON)
    confianza: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    fuente: Mapped[dict[str, object]] = mapped_column(JSON)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")


class EvaluacionModelo(Base, MarcasTiempo):
    __tablename__ = "evaluations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    postulacion_id: Mapped[str] = mapped_column(String(32), ForeignKey("applications.id"))
    documento_id: Mapped[str] = mapped_column(String(32), ForeignKey("candidate_documents.id"))
    version_perfil_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("job_profile_versions.id")
    )
    puntaje_documental: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=True)
    modelo: Mapped[str | None] = mapped_column(String(100))
    version_prompt: Mapped[str | None] = mapped_column(String(40))
    simulada: Mapped[bool] = mapped_column(Boolean, default=False)


class EvaluacionRequisitoModelo(Base):
    __tablename__ = "requirement_assessments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    evaluacion_id: Mapped[str] = mapped_column(String(32), ForeignKey("evaluations.id"), index=True)
    codigo_requisito: Mapped[str] = mapped_column(String(80))
    veredicto: Mapped[str] = mapped_column(String(30))
    puntaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    evidencia: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    explicacion: Mapped[str] = mapped_column(Text, default="")


class RevisionHumanaModelo(Base, MarcasTiempo):
    __tablename__ = "human_reviews"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    evaluacion_id: Mapped[str] = mapped_column(String(32), ForeignKey("evaluations.id"), index=True)
    revisor_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"))
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")
    comentario: Mapped[str | None] = mapped_column(Text)


class CorreccionCampoModelo(Base, MarcasTiempo):
    __tablename__ = "field_corrections"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(32), ForeignKey("human_reviews.id"))
    campo: Mapped[str] = mapped_column(String(80))
    valor_anterior: Mapped[dict[str, object] | None] = mapped_column(JSON)
    valor_nuevo: Mapped[dict[str, object]] = mapped_column(JSON)


class LoteImportacionModelo(Base, MarcasTiempo):
    __tablename__ = "import_batches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    hash_archivo: Mapped[str] = mapped_column(String(64), unique=True)
    estado: Mapped[str] = mapped_column(String(30), default="staging")
    clave_idempotencia: Mapped[str] = mapped_column(String(80), unique=True)


class FilaImportacionModelo(Base):
    __tablename__ = "import_rows"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lote_id: Mapped[str] = mapped_column(String(32), ForeignKey("import_batches.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    datos: Mapped[dict[str, object]] = mapped_column(JSON)
    clasificacion: Mapped[str] = mapped_column(String(40))
    errores: Mapped[list[str]] = mapped_column(JSON, default=list)


class ReporteExclusionModelo(Base, MarcasTiempo):
    __tablename__ = "exclusion_reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    filtros: Mapped[dict[str, object]] = mapped_column(JSON)
    hash_contenido: Mapped[str] = mapped_column(String(64))
    estado: Mapped[str] = mapped_column(String(30), default="listo")


class EntradaExclusionModelo(Base):
    __tablename__ = "exclusion_entries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    reporte_id: Mapped[str] = mapped_column(String(32), ForeignKey("exclusion_reports.id"))
    documento: Mapped[str] = mapped_column(String(64))
    motivo_generico: Mapped[str] = mapped_column(String(100))


class TrabajoAgenteModelo(Base, MarcasTiempo):
    __tablename__ = "agent_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(40))
    estado: Mapped[str] = mapped_column(String(30), index=True, default="pendiente")
    carga: Mapped[dict[str, object]] = mapped_column(JSON)
    resultado: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(300))
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    max_intentos: Mapped[int] = mapped_column(Integer, default=3)
    disponible_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    reservado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clave_idempotencia: Mapped[str] = mapped_column(String(80), unique=True)


class CheckpointWorkflowModelo(Base, MarcasTiempo):
    __tablename__ = "workflow_checkpoints"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trabajo_id: Mapped[str] = mapped_column(String(32), ForeignKey("agent_jobs.id"), index=True)
    nodo: Mapped[str] = mapped_column(String(80))
    estado: Mapped[dict[str, object]] = mapped_column(JSON)
    secuencia: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("trabajo_id", "secuencia", name="uq_checkpoint_seq"),)


class EventoAuditoriaModelo(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str | None] = mapped_column(String(32), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(32), index=True)
    accion: Mapped[str] = mapped_column(String(100), index=True)
    recurso_tipo: Mapped[str] = mapped_column(String(60))
    recurso_id: Mapped[str | None] = mapped_column(String(32))
    detalle: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    hash_anterior: Mapped[str] = mapped_column(String(64), default="")
    hash_evento: Mapped[str] = mapped_column(String(64), unique=True)
    correlacion_id: Mapped[str] = mapped_column(String(40), index=True)


class EventoMetricaPilotoModelo(Base):
    __tablename__ = "pilot_metric_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(32), ForeignKey("clients.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(80), index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unidad: Mapped[str] = mapped_column(String(30))
    dimensiones: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
