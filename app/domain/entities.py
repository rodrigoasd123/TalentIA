"""Entidades del dominio.

Estas clases no saben nada de SQLAlchemy, de FastAPI ni de LangChain. Se pueden
instanciar y probar sin base de datos ni red, y esa es exactamente la propiedad
que permite migrar de SQLite a PostgreSQL cambiando un adaptador.

Los modelos de persistencia viven aparte, en ``app.infrastructure.database``, y
los repositorios traducen entre ambos mundos.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    ActorType,
    ApplicationStatus,
    CandidateStatus,
    DocumentType,
    EmailStatus,
    EmailTemplateKind,
    JobStatus,
    Recommendation,
    ReviewReason,
    ReviewStatus,
    Role,
    ScoringDimension,
    Severity,
    WorkflowStatus,
)
from app.domain.value_objects import (
    ConsentRecord,
    EmailAddress,
    EvidenceSpan,
    FilterResult,
    HardFilter,
    LanguageSkill,
    Score,
    ScoringWeights,
)

_ENTITY = ConfigDict(extra="forbid", validate_assignment=True)


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    """Siempre UTC explícito. SQLite no guarda zona horaria y un ``now()``
    ingenuo produce cálculos de SLA erróneos en cuanto cambia la máquina."""
    return datetime.now(UTC)


class Entity(BaseModel):
    """Base común: identidad, marcas de tiempo y versión para bloqueo optimista."""

    model_config = _ENTITY
    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    version: int = 1

    def touch(self) -> None:
        self.updated_at = _now()
        self.version += 1


# ── Identidad y acceso ───────────────────────────────────────────────────────


class User(Entity):
    email: EmailAddress
    full_name: str
    role: Role
    password_hash: str = ""
    is_active: bool = True
    mfa_enabled: bool = False
    failed_login_attempts: int = 0
    locked_until: datetime | None = None

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > _now()


# ── Vacantes ─────────────────────────────────────────────────────────────────


class JobRequirements(BaseModel):
    """Criterios de una vacante, versionados de forma independiente.

    Se versionan aparte de la vacante porque cambiar los criterios no debe
    alterar las evaluaciones ya emitidas: una evaluación apunta a la versión de
    criterios con la que se hizo.
    """

    model_config = _ENTITY
    version: int = 1
    hard_filters: list[HardFilter] = Field(default_factory=list)
    weights: ScoringWeights = Field(default_factory=ScoringWeights.balanced_default)
    minimum_score: float = Field(default=70.0, ge=0, le=100)
    review_threshold: float = Field(default=5.0, ge=0, le=50)
    mandatory_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0
    education_level: str = ""
    languages: list[LanguageSkill] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    @property
    def mandatory_filters(self) -> list[HardFilter]:
        return [f for f in self.hard_filters if f.mandatory]


class Job(Entity):
    code: str
    title: str
    description: str = ""
    department: str = ""
    location: str = ""
    employment_type: str = "full_time"
    status: JobStatus = JobStatus.DRAFT
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = "USD"
    opening_date: date | None = None
    closing_date: date | None = None
    recruiter_id: str | None = None
    hiring_manager_id: str | None = None
    tenant_id: str = "default"

    @property
    def is_accepting_applications(self) -> bool:
        if self.status is not JobStatus.OPEN:
            return False
        if self.closing_date and self.closing_date < date.today():
            return False
        return True


# ── Candidatos ───────────────────────────────────────────────────────────────


class WorkExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str | None = None
    is_current: bool = False
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    years: float = 0.0


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")
    degree: str = ""
    field_of_study: str = ""
    institution: str = ""
    graduation_year: int | None = None
    level: str = ""


class ResumeExtraction(BaseModel):
    """Datos estructurados extraídos de un CV.

    ``field_confidence`` permite derivar a revisión humana los casos en los que
    el modelo no estuvo seguro, en lugar de tratar toda extracción como igual de
    fiable.
    """

    model_config = ConfigDict(extra="forbid")
    total_years_experience: float = 0.0
    seniority: str = ""
    current_role: str = ""
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    experiences: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[LanguageSkill] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    availability: str = ""
    field_confidence: dict[str, float] = Field(default_factory=dict)
    suspicious_content_found: bool = False
    suspicious_content_note: str = ""

    @property
    def average_confidence(self) -> float:
        if not self.field_confidence:
            return 1.0
        return sum(self.field_confidence.values()) / len(self.field_confidence)

    def normalized_skills(self) -> set[str]:
        return {s.strip().lower() for s in (*self.skills, *self.technologies) if s.strip()}


class Candidate(Entity):
    full_name: str
    email: EmailAddress | None = None
    phone: str = ""
    national_id: str = ""
    location: str = ""
    source: str = "direct"
    consent: ConsentRecord | None = None
    tags: list[str] = Field(default_factory=list)
    tenant_id: str = "default"
    processing_status: str = "allowed"
    legal_basis_status: str = "consent"
    client: str = ""
    candidate_status: CandidateStatus = CandidateStatus.PENDIENTE_CONTACTO
    record_date: date | None = None
    recruiter: str = ""
    q: str = ""
    birth_date: date | None = None
    reported_age: int | None = Field(default=None, ge=0, le=120)
    bgc: str = ""
    technical_knowledge: str = ""
    equifax_debt: float | None = Field(default=None, ge=0)
    salary_expectation: float | None = Field(default=None, ge=0)
    requested: str = ""
    role_ctc: float | None = Field(default=None, ge=0)
    ctc_variation_pct: float | None = None
    availability: str = ""
    notes: str = ""

    @property
    def age(self) -> int | None:
        if self.birth_date is None:
            return self.reported_age
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def can_be_processed(self) -> bool:
        if self.processing_status == "restricted_review":
            return False
        if self.legal_basis_status == "unknown":
            return False
        if self.legal_basis_status == "consent":
            return self.consent is not None and self.consent.is_valid
        return True


class ResumeDocument(Entity):
    candidate_id: str
    filename: str
    document_type: DocumentType
    storage_path: str = ""
    content_hash: str = ""
    raw_text: str = ""
    char_count: int = 0
    resume_version: int = 1
    extraction: ResumeExtraction | None = None
    is_suspicious: bool = False


# ── Aplicaciones ─────────────────────────────────────────────────────────────


class Application(Entity):
    """Candidatura de una persona a una vacante concreta.

    Es la entidad central del sistema. El estado vive aquí y no en el candidato,
    porque una misma persona puede estar preseleccionada en una vacante y
    rechazada en otra sin que ambas cosas se contradigan.
    """

    candidate_id: str
    job_id: str
    resume_id: str | None = None
    status: ApplicationStatus = ApplicationStatus.NEW
    source: str = "direct"
    applied_at: datetime = Field(default_factory=_now)
    entered_stage_at: datetime = Field(default_factory=_now)
    final_score: float | None = None
    assigned_to: str | None = None
    idempotency_key: str = ""
    requirements_version: int = 1
    tenant_id: str = "default"

    @property
    def hours_in_stage(self) -> float:
        return (_now() - self.entered_stage_at).total_seconds() / 3600

    def move_to(self, status: ApplicationStatus) -> None:
        """Cambia de estado. La validez de la transición la comprueba la máquina
        de estados antes de llamar aquí; este método solo aplica el efecto."""
        self.status = status
        self.entered_stage_at = _now()
        self.touch()


# ── Evaluación ───────────────────────────────────────────────────────────────


class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: ScoringDimension
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=100)
    reasoning: str = ""
    evidence: list[EvidenceSpan] = Field(default_factory=list)

    @property
    def weighted_contribution(self) -> float:
        return self.score * self.weight / 100

    @property
    def verified_evidence(self) -> list[EvidenceSpan]:
        return [e for e in self.evidence if e.verified]


class BiasAuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bias_detected: bool = False
    indicators: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    severity: Severity = Severity.INFO
    explanation: str = ""


class Evaluation(Entity):
    """Resultado de evaluar una aplicación. Inmutable por diseño.

    Reevaluar no modifica esta fila: crea otra y marca la anterior como
    sustituida. Sin esta propiedad, la pregunta "¿con qué criterios se rechazó a
    esta persona en marzo?" no tiene respuesta.
    """

    application_id: str
    evaluation_type: str = "ai_automatic"
    passed_hard_filters: bool = False
    hard_filter_results: list[FilterResult] = Field(default_factory=list)
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    total_score: Score | None = None
    recommendation: Recommendation = Recommendation.REVIEW
    missing_requirements: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    summary: str = ""
    bias_audit: BiasAuditResult | None = None
    evidence_verification_rate: float = 0.0
    requires_human_review: bool = True
    review_reasons: list[ReviewReason] = Field(default_factory=list)

    # Reproducibilidad: sin estos campos una decisión pasada no puede explicarse.
    model_name: str = ""
    model_version: str = ""
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    temperature: float = 0.0
    token_usage: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    requirements_version: int = 1
    agent_version: str = ""
    trace_id: str = ""
    workflow_run_id: str = ""
    superseded_by_id: str | None = None
    created_by: str = "talentia"

    @property
    def all_evidence(self) -> list[EvidenceSpan]:
        return [e for d in self.dimension_scores for e in d.evidence]

    @property
    def is_current(self) -> bool:
        return self.superseded_by_id is None


# ── Supervisión humana ───────────────────────────────────────────────────────


class HumanReviewItem(Entity):
    application_id: str
    evaluation_id: str | None = None
    reasons: list[ReviewReason] = Field(default_factory=list)
    priority: Severity = Severity.MEDIUM
    status: ReviewStatus = ReviewStatus.PENDING
    sla_hours: int = 24
    assigned_to: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str = ""
    score_override: float | None = None
    context: dict[str, Any] = Field(default_factory=dict)

    @property
    def due_at(self) -> datetime:
        from datetime import timedelta

        return self.created_at + timedelta(hours=self.sla_hours)

    @property
    def is_overdue(self) -> bool:
        return self.status in {ReviewStatus.PENDING, ReviewStatus.ASSIGNED} and _now() > self.due_at


# ── Comunicación ─────────────────────────────────────────────────────────────


class EmailTemplate(Entity):
    code: str
    kind: EmailTemplateKind
    subject_template: str
    body_template: str
    template_version: int = 1
    approved: bool = False
    allowed_variables: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True


class EmailMessage(Entity):
    application_id: str
    candidate_id: str
    job_id: str
    template_id: str
    template_version: int = 1
    recipient: EmailAddress
    subject: str = ""
    body: str = ""
    status: EmailStatus = EmailStatus.DRAFT
    idempotency_key: str = ""
    gmail_message_id: str = ""
    gmail_thread_id: str = ""
    initiated_by: str = ""
    approved_by: str | None = None
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    retry_count: int = 0
    error_message: str = ""


# ── Trazabilidad ─────────────────────────────────────────────────────────────


class AuditEvent(BaseModel):
    """Evento de auditoría. Solo inserción: no tiene ``touch()`` ni versión.

    ``previous_hash`` y ``event_hash`` encadenan los eventos para que alterar
    uno pasado invalide toda la cadena posterior y la manipulación sea detectable.
    """

    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_now)
    trace_id: str = ""
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = ""
    ip_address: str = ""
    user_agent: str = ""
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    agent_version: str = ""
    prompt_version: str = ""
    model: str = ""
    policy_result: str = ""
    human_approval_by: str | None = None
    severity: Severity = Severity.INFO
    metadata: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str = ""
    event_hash: str = ""


class WorkflowRun(Entity):
    application_id: str = ""
    graph_name: str = ""
    agent_version: str = ""
    status: WorkflowStatus = WorkflowStatus.RUNNING
    trace_id: str = ""
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    node_timings: dict[str, float] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    error: str = ""
    dry_run: bool = False

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or _now()
        return (end - self.started_at).total_seconds()


class NodeRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=_new_id)
    workflow_run_id: str = ""
    node_name: str = ""
    node_version: str = "1"
    sequence: int = 0
    started_at: datetime = Field(default_factory=_now)
    duration_seconds: float = 0.0
    succeeded: bool = True
    error: str = ""
    attempts: int = 1
    output_summary: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "Application", "AuditEvent", "BiasAuditResult", "Candidate", "DimensionScore",
    "Education", "EmailMessage", "EmailTemplate", "Entity", "Evaluation",
    "HumanReviewItem", "Job", "JobRequirements", "NodeRun", "ResumeDocument",
    "ResumeExtraction", "User", "WorkExperience", "WorkflowRun",
]
