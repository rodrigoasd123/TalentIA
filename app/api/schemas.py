"""Esquemas de entrada y salida de la API.

Separados de las entidades de dominio a propósito: lo que la API expone y lo que
el dominio modela evolucionan a ritmos distintos, y acoplarlos obliga a romper el
contrato público cada vez que cambia una regla interna.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    provider: Literal["gemini", "mock"] = "gemini"
    api_key: str = ""
    model: str = "gemini-2.5-flash"


class CredentialTestResponse(BaseModel):
    ok: bool
    message: str
    available_models: list[str] = Field(default_factory=list)


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


class IntakeResponse(BaseModel):
    candidate_id: str
    resume_id: str
    application_id: str
    was_existing_candidate: bool
    duplicates: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


__all__ = [
    "AgentHealthResponse", "CredentialTestRequest", "CredentialTestResponse",
    "DimensionOut", "ErrorDetail", "ErrorResponse", "EvaluationResponse",
    "EvaluationRunRequest", "EvidenceOut", "FilterResultOut", "HealthResponse",
    "IntakeResponse", "JobCreateRequest", "JobUpdateRequest", "JobSummary", "ResumeSummary", "SettingItem", "SettingsResponse",
    "SettingsUpdateRequest",
]
