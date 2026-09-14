"""Esquemas de entrada y salida de la API.

Separados de las entidades de dominio a propósito: lo que la API expone y lo que
el dominio modela evolucionan a ritmos distintos, y acoplarlos obliga a romper el
contrato público cada vez que cambia una regla interna.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import CandidateStatus


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""
    timestamp: str = ""


class ErrorResponse(BaseModel):
    """Envelope uniforme de error. Todos los fallos de la API tienen esta forma."""

    error: ErrorDetail


class SettingItem(BaseModel):
    key: str
    label: str
    group: str
    help_text: str
    is_secret: bool
    is_set: bool
    value: str
    updated_at: str | None = None
    updated_by: str = ""


class SettingsResponse(BaseModel):
    settings: list[SettingItem]
    llm_ready: bool
    provider: str
    model: str
    is_simulated: bool


class SettingsUpdateRequest(BaseModel):
    """Actualización parcial: solo se tocan las claves incluidas.

    Un secreto se deja sin cambiar omitiéndolo, no enviando una cadena vacía. Es
    importante para que el panel pueda reenviar el formulario sin borrar la API
    key que el usuario no ha vuelto a escribir.
    """

    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(default_factory=dict)
    updated_by: str = "panel"


class CredentialTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="genai_lab", min_length=2, max_length=64)
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    base_url: str = ""


class CredentialTestResponse(BaseModel):
    ok: bool
    message: str
    available_models: list[str] = Field(default_factory=list)


class ModelBenchmarkRequest(BaseModel):
    models: list[str] = Field(min_length=1, max_length=5)
    baseline_model: str = ""
    confirmed: bool = False


class AIProviderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=2, max_length=120)
    base_url: str = Field(min_length=8, max_length=500)


class AIProviderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    is_enabled: bool | None = None


class AIProviderCredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    credential: str = Field(min_length=1, max_length=4096)


class AIModelCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=1, max_length=160)
    display_name: str = Field(default="", max_length=160)
    capabilities: list[str] = Field(default_factory=lambda: ["generation"])
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)


class AIModelUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, max_length=160)
    is_enabled: bool | None = None
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)


class JobSummary(BaseModel):
    id: str
    code: str
    title: str
    department: str
    location: str
    status: str
    minimum_score: float
    review_threshold: float
    min_years_experience: float
    mandatory_skills: list[str]
    hard_filter_count: int
    weights: dict[str, float]
    requirements_version: int = 1
    language_required: bool = False
    language_level: str = "b2"
    language_mode: str = "weighted"
    language_penalty_percent: float = 15.0


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=3, max_length=40)
    title: str = Field(min_length=3, max_length=160)
    description: str = ""
    department: str = ""
    location: str = ""
    mandatory_skills: list[str] = Field(default_factory=list)
    minimum_score: float = Field(default=70.0, ge=0, le=100)
    review_threshold: float = Field(default=5.0, ge=0, le=50)
    min_years_experience: float = Field(default=0.0, ge=0, le=80)
    criteria_approved: bool = False
    language_required: bool = False
    language_level: str = "b2"
    language_mode: Literal["weighted", "excludent"] = "weighted"
    language_penalty_percent: float = Field(default=15.0, ge=0, le=100)


class JobUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = None
    department: str | None = None
    location: str | None = None
    mandatory_skills: list[str] | None = None
    minimum_score: float | None = Field(default=None, ge=0, le=100)
    review_threshold: float | None = Field(default=None, ge=0, le=50)
    min_years_experience: float | None = Field(default=None, ge=0, le=80)
    criteria_approved: bool | None = None
    language_required: bool | None = None
    language_level: str | None = None
    language_mode: Literal["weighted", "excludent"] | None = None
    language_penalty_percent: float | None = Field(default=None, ge=0, le=100)


class CandidateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=40)
    location: str = Field(default="", max_length=160)
    client: str = Field(default="", max_length=160)
    candidate_status: CandidateStatus = CandidateStatus.PENDIENTE_CONTACTO
    record_date: date | None = None
    recruiter: str = Field(default="", max_length=160)
    source: str = Field(default="manual", max_length=80)
    q: str = Field(default="", max_length=80)
    birth_date: date | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    national_id: str = Field(default="", max_length=40)
    bgc: str = Field(default="", max_length=160)
    technical_knowledge: str = Field(default="", max_length=10000)
    equifax_debt: float | None = Field(default=None, ge=0)
    salary_expectation: float | None = Field(default=None, ge=0)
    requested: str = Field(default="", max_length=160)
    role_ctc: float | None = Field(default=None, ge=0)
    ctc_variation_pct: float | None = Field(default=None, ge=-1000, le=1000)
    availability: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=10000)

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("La fecha de nacimiento no puede estar en el futuro")
        return value


class CandidateIdentityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=40)
    national_id: str = Field(default="", max_length=40)


class CandidateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    client: str | None = Field(default=None, max_length=160)
    candidate_status: CandidateStatus | None = None
    record_date: date | None = None
    recruiter: str | None = Field(default=None, max_length=160)
    source: str | None = Field(default=None, max_length=80)
    q: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    national_id: str | None = Field(default=None, max_length=40)
    bgc: str | None = Field(default=None, max_length=160)
    technical_knowledge: str | None = Field(default=None, max_length=10000)
    equifax_debt: float | None = Field(default=None, ge=0)
    salary_expectation: float | None = Field(default=None, ge=0)
    requested: str | None = Field(default=None, max_length=160)
    role_ctc: float | None = Field(default=None, ge=0)
    ctc_variation_pct: float | None = Field(default=None, ge=-1000, le=1000)
    availability: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, value: date | None) -> date | None:
        return CandidateCreateRequest.birth_date_not_future(value)


class IntakeResponse(BaseModel):
    candidate_id: str
    resume_id: str
    application_id: str
    was_existing_candidate: bool
    duplicates: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResumePrefillRequest(BaseModel):
    """Campos extraídos que RR. HH. decidió incorporar explícitamente."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    technical_knowledge: str | None = Field(default=None, max_length=10000)
    availability: str | None = Field(default=None, max_length=160)


class ResumeSummary(BaseModel):
    code: str
    full_name: str
    email_masked: str
    char_count: int
    purpose: str = ""
    is_security_fixture: bool = False


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_code: str
    resume_code: str
    dry_run: bool = True


class FilterResultOut(BaseModel):
    label: str
    passed: bool
    mandatory: bool
    explanation: str
    status: str = "failed"
    mode: str = "excludent"
    penalty_percent: float = 0.0


class EvidenceOut(BaseModel):
    quote: str
    dimension: str
    verified: bool
    match_ratio: float


class DimensionOut(BaseModel):
    dimension: str
    score: float
    weight: float
    reasoning: str
    evidence: list[EvidenceOut]


class EvaluationResponse(BaseModel):
    """Resultado de una evaluación, con todo lo necesario para explicarla."""

    application_id: str
    trace_id: str
    workflow_run_id: str
    agent: str
    agent_version: str
    model: str
    is_simulated: bool

    total_score: float
    score_calculated: bool = True
    recommendation: str
    passed_hard_filters: bool
    requires_human_review: bool
    review_reasons: list[str]

    hard_filters: list[FilterResultOut]
    dimensions: list[DimensionOut]
    strengths: list[str]
    gaps: list[str]
    missing_requirements: list[str]
    summary: str
    explanation: str

    evidence_verification_rate: float
    injection_detected: bool
    injection_severity: str
    bias_detected: bool
    pii_redactions: int
    pii_categories: list[str]

    proposed_actions: list[str]
    policy_decisions: list[dict[str, str]]
    nodes_executed: list[str]
    node_timings: dict[str, float]
    token_usage: dict[str, Any]
    cost_usd: float
    prompt_versions: dict[str, str]

    #: Recordatorio explícito en la propia respuesta: nada se ha aplicado.
    actions_executed: bool = False


class AgentHealthResponse(BaseModel):
    agent: str
    full_name: str
    version: str
    graph: str
    llm_configured: bool
    model: str
    provider: str
    is_simulated: bool
    llm_bias_audit: bool
    budget_usd: float
    prompts: list[dict[str, str]]
    langgraph_available: bool


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    llm_ready: bool
    version: str


class ImportValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping: dict[str, str]
    expected_version: int | None = Field(default=None, ge=1)
    template_name: str = Field(default="", max_length=120)


class ImportSelectSheetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sheet_name: str = Field(min_length=1, max_length=120)
    expected_version: int | None = Field(default=None, ge=1)


class ImportConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=80)
    expected_version: int | None = Field(default=None, ge=1)


class ImportCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


__all__ = [
    "AIModelCreateRequest",
    "AIModelUpdateRequest",
    "AIProviderCreateRequest",
    "AIProviderCredentialRequest",
    "AIProviderUpdateRequest",
    "AgentHealthResponse",
    "CandidateIdentityCheckRequest",
    "CredentialTestRequest",
    "CredentialTestResponse",
    "DimensionOut",
    "ErrorDetail",
    "ErrorResponse",
    "EvaluationResponse",
    "EvaluationRunRequest",
    "EvidenceOut",
    "FilterResultOut",
    "HealthResponse",
    "ImportCancelRequest",
    "ImportConfirmRequest",
    "ImportSelectSheetRequest",
    "ImportValidateRequest",
    "IntakeResponse",
    "JobCreateRequest",
    "JobSummary",
    "JobUpdateRequest",
    "ModelBenchmarkRequest",
    "ResumePrefillRequest",
    "ResumeSummary",
    "SettingItem",
    "SettingsResponse",
    "SettingsUpdateRequest",
]
