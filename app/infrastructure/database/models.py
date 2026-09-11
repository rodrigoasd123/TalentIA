"""Modelos de persistencia (SQLAlchemy).

Están separados de las entidades de dominio a propósito. Las entidades expresan
reglas de negocio; estos modelos expresan cómo se guardan las filas. Mezclarlos
haría que un cambio de motor de base de datos se propagara al dominio.

El código se escribe como si ya estuviéramos en PostgreSQL, y SQLite se adapta:
UTC explícito en todas las fechas, columna ``version`` para bloqueo optimista
desde el primer día, y restricciones de unicidad donde la integridad no puede
depender de que la aplicación se acuerde de comprobarla.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base declarativa. ``JSON`` se traduce a JSONB en PostgreSQL."""

    type_annotation_map = {dict: JSON, list: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# ── Configuración en caliente ────────────────────────────────────────────────


class RuntimeSettingModel(Base):
    """Configuración editable desde el panel.

    Los valores marcados como secretos se guardan cifrados. La columna
    ``is_secret`` existe para que la API sepa que nunca debe devolver el valor
    en claro, solo una versión enmascarada.
    """

    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    updated_by: Mapped[str] = mapped_column(String(64), default="")


# ── Identidad ────────────────────────────────────────────────────────────────


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32), index=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Vacantes ─────────────────────────────────────────────────────────────────


class JobModel(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), default="default", index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    department: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    employment_type: Mapped[str] = mapped_column(String(40), default="full_time")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    opening_date: Mapped[str] = mapped_column(String(12), default="")
    closing_date: Mapped[str] = mapped_column(String(12), default="")
    recruiter_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hiring_manager_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


# ── Candidatos ───────────────────────────────────────────────────────────────


class CandidateModel(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), default="default", index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    national_id: Mapped[str] = mapped_column(String(40), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    source: Mapped[str] = mapped_column(String(40), default="direct")
    consent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    processing_status: Mapped[str] = mapped_column(String(32), default="allowed", index=True)
    legal_basis_status: Mapped[str] = mapped_column(String(32), default="consent")
    client: Mapped[str] = mapped_column(String(160), default="")
    candidate_status: Mapped[str] = mapped_column(
        String(32), default="pendiente_contacto", index=True
    )
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recruiter: Mapped[str] = mapped_column(String(160), default="")
    q: Mapped[str] = mapped_column(String(80), default="")
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reported_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bgc: Mapped[str] = mapped_column(String(160), default="")
    technical_knowledge: Mapped[str] = mapped_column(Text, default="")
    equifax_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_expectation: Mapped[float | None] = mapped_column(Float, nullable=True)
    requested: Mapped[str] = mapped_column(String(160), default="")
    role_ctc: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctc_variation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    availability: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        # Un candidato por correo y tenant. La unicidad se garantiza en la base
        # de datos, no en la aplicación: es la única forma de que sobreviva a
        # dos peticiones simultáneas.
        UniqueConstraint("tenant_id", "email", name="uq_candidate_tenant_email"),
    )


class ResumeModel(Base, TimestampMixin):
    __tablename__ = "candidate_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(16))
    storage_path: Mapped[str] = mapped_column(String(500), default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    resume_version: Mapped[int] = mapped_column(Integer, default=1)
    extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Candidaturas ─────────────────────────────────────────────────────────────


class ApplicationModel(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), default="default", index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    resume_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    source: Mapped[str] = mapped_column(String(40), default="direct")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    entered_stage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), default="")
    requirements_version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_application_idempotency"),
        Index("ix_application_job_status", "job_id", "status"),
    )


# ── Evaluación ───────────────────────────────────────────────────────────────


class EvaluationModel(Base, TimestampMixin):
    """Inmutable. Una reevaluación crea otra fila y marca esta como sustituida."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    evaluation_type: Mapped[str] = mapped_column(String(32), default="ai_automatic")
    passed_hard_filters: Mapped[bool] = mapped_column(Boolean, default=False)
    hard_filter_results: Mapped[list] = mapped_column(JSON, default=list)
    dimension_scores: Mapped[list] = mapped_column(JSON, default=list)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    recommendation: Mapped[str] = mapped_column(String(24), default="review", index=True)
    missing_requirements: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    bias_audit: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_verification_rate: Mapped[float] = mapped_column(Float, default=0.0)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    review_reasons: Mapped[list] = mapped_column(JSON, default=list)

    model_name: Mapped[str] = mapped_column(String(80), default="")
    model_version: Mapped[str] = mapped_column(String(80), default="")
    prompt_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    requirements_version: Mapped[int] = mapped_column(Integer, default=1)
    agent_version: Mapped[str] = mapped_column(String(40), default="")
    trace_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    workflow_run_id: Mapped[str] = mapped_column(String(32), default="")
    superseded_by_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="vera")


# ── Supervisión humana ───────────────────────────────────────────────────────


class HumanReviewModel(Base, TimestampMixin):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    evaluation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    sla_hours: Mapped[int] = mapped_column(Integer, default=24)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    decided_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    score_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)


# ── Comunicación ─────────────────────────────────────────────────────────────


class EmailTemplateModel(Base, TimestampMixin):
    __tablename__ = "email_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    subject_template: Mapped[str] = mapped_column(Text)
    body_template: Mapped[str] = mapped_column(Text)
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_variables: Mapped[list] = mapped_column(JSON, default=list)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)


class EmailModel(Base, TimestampMixin):
    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(32), index=True)
    candidate_id: Mapped[str] = mapped_column(String(32), index=True)
    job_id: Mapped[str] = mapped_column(String(32), index=True)
    template_id: Mapped[str] = mapped_column(String(32))
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    gmail_message_id: Mapped[str] = mapped_column(String(120), default="")
    gmail_thread_id: Mapped[str] = mapped_column(String(120), default="")
    initiated_by: Mapped[str] = mapped_column(String(64), default="")
    approved_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        # La imposibilidad de enviar dos veces el mismo correo se garantiza aquí,
        # a nivel de motor. Cualquier comprobación en la aplicación puede perder
        # una carrera entre dos procesos; esta restricción no.
        UniqueConstraint("idempotency_key", name="uq_email_idempotency"),
    )


# ── Trazabilidad ─────────────────────────────────────────────────────────────


class AuditEventModel(Base):
    """Solo inserción. No hereda ``TimestampMixin`` porque no se actualiza nunca."""

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    trace_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    actor_type: Mapped[str] = mapped_column(String(16), default="system", index=True)
    actor_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), default="", index=True)
    resource_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_version: Mapped[str] = mapped_column(String(40), default="")
    prompt_version: Mapped[str] = mapped_column(String(40), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    policy_result: Mapped[str] = mapped_column(String(40), default="")
    human_approval_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="info", index=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64), default="")
    event_hash: Mapped[str] = mapped_column(String(64), default="", index=True)


class WorkflowRunModel(Base, TimestampMixin):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    graph_name: Mapped[str] = mapped_column(String(60), default="")
    agent_version: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    trace_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    node_timings: Mapped[dict] = mapped_column(JSON, default=dict)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Importación histórica ───────────────────────────────────────────────────


class ImportBatchModel(Base, TimestampMixin):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), default="default", index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(120), default="historical")
    sheet_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    column_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(64))
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cancellation_reason: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        UniqueConstraint("tenant_id", "checksum", name="uq_import_batch_checksum"),
        UniqueConstraint("confirmation_key", name="uq_import_confirmation_key"),
    )


class ImportRowModel(Base):
    __tablename__ = "import_rows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    normalized_data: Mapped[dict] = mapped_column(JSON, default=dict)
    classification: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    candidate_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    application_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_import_row_number"),
        Index("ix_import_row_batch_classification", "batch_id", "classification"),
    )


class ImportMappingTemplateModel(Base, TimestampMixin):
    __tablename__ = "import_mapping_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), default="default", index=True)
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(120), default="historical")
    column_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_import_mapping_template_name"),
    )


ALL_MODELS = (
    RuntimeSettingModel, UserModel, JobModel, CandidateModel, ResumeModel,
    ApplicationModel, EvaluationModel, HumanReviewModel, EmailTemplateModel,
    EmailModel, AuditEventModel, WorkflowRunModel, ImportBatchModel,
    ImportRowModel, ImportMappingTemplateModel,
)

__all__ = [
    "ALL_MODELS", "ApplicationModel", "AuditEventModel", "Base", "CandidateModel",
    "EmailModel", "EmailTemplateModel", "EvaluationModel", "HumanReviewModel",
    "JobModel", "ResumeModel", "RuntimeSettingModel", "UserModel",
    "WorkflowRunModel", "ImportBatchModel", "ImportRowModel",
    "ImportMappingTemplateModel", "utcnow",
]
