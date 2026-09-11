"""Esquemas de las salidas del modelo.

Todo lo que TalentIA obtiene de un modelo de lenguaje pasa por uno de estos
esquemas antes de tocar el resto del sistema. Ninguno tiene campos de texto
libre que el sistema interprete como decisión, y todos prohíben campos
adicionales: si el modelo inventa una clave, la validación falla en vez de
arrastrar un dato no previsto.

Nótese lo que **no** está aquí: no hay campo para ejecutar acciones, ni para
indicar destinatarios de correo, ni para la puntuación total. Esas cosas no las
decide el modelo, y la forma más sólida de garantizarlo es que no exista un
sitio donde pueda escribirlas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ── Extracción de CV ─────────────────────────────────────────────────────────


class ExtractedExperience(BaseModel):
    model_config = _STRICT
    company: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    start_date: str = Field(default="", max_length=20, description="AAAA-MM o AAAA")
    end_date: str | None = Field(default=None, max_length=20)
    is_current: bool = False
    description: str = Field(default="", max_length=1500)
    technologies: list[str] = Field(default_factory=list, max_length=40)
    years: float = Field(default=0.0, ge=0, le=60)


class ExtractedEducation(BaseModel):
    model_config = _STRICT
    degree: str = Field(default="", max_length=200)
    field_of_study: str = Field(default="", max_length=200)
    institution: str = Field(default="", max_length=200)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    level: str = Field(default="", max_length=60)


class ExtractedLanguage(BaseModel):
    model_config = _STRICT
    language: str = Field(max_length=60)
    level: Literal["a1", "a2", "b1", "b2", "c1", "c2", "native"] = "b1"


class ResumeExtractionOutput(BaseModel):
    """Salida del nodo de extracción.

    ``suspicious_content_found`` permite al modelo señalar que el documento
    intentaba darle instrucciones. Es una señal complementaria, nunca la única:
    el detector determinístico se ejecuta antes y no depende de que el modelo
    coopere.
    """

    model_config = _STRICT

    total_years_experience: float = Field(default=0.0, ge=0, le=60)
    seniority: Literal["junior", "semi_senior", "senior", "lead", "principal", "unknown"] = "unknown"
    current_role: str = Field(default="", max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=80)
    technologies: list[str] = Field(default_factory=list, max_length=80)
    experiences: list[ExtractedExperience] = Field(default_factory=list, max_length=30)
    education: list[ExtractedEducation] = Field(default_factory=list, max_length=15)
    languages: list[ExtractedLanguage] = Field(default_factory=list, max_length=15)
    certifications: list[str] = Field(default_factory=list, max_length=30)
    availability: str = Field(default="", max_length=120)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    suspicious_content_found: bool = False
    suspicious_content_note: str = Field(default="", max_length=500)

    @field_validator("field_confidence")
    @classmethod
    def _clamp_confidence(cls, value: dict[str, float]) -> dict[str, float]:
        return {k: min(1.0, max(0.0, float(v))) for k, v in value.items()}


# ── Evaluación ───────────────────────────────────────────────────────────────


class EvidenceItem(BaseModel):
    """Cita textual que respalda una puntuación.

    ``quote`` debe ser un fragmento literal del CV. El verificador comprobará
    después que existe; el modelo no puede marcar su propia evidencia como
    válida porque este esquema no tiene ese campo.
    """

    model_config = _STRICT
    quote: str = Field(min_length=3, max_length=400)
    dimension: Literal["technical", "experience", "education", "projects", "semantic", "languages"]


class DimensionEvaluation(BaseModel):
    model_config = _STRICT
    dimension: Literal["technical", "experience", "education", "projects", "semantic", "languages"]
    score: float = Field(ge=0, le=100)
    reasoning: str = Field(default="", max_length=800)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)


class CandidateEvaluationOutput(BaseModel):
    """Salida del nodo de evaluación semántica.

    No incluye ``total_score`` de forma intencionada: el total es una función
    determinística de estas dimensiones y de los pesos de la vacante, y se
    calcula en ``app.domain.rules.scoring``.
    """

    model_config = _STRICT

    dimensions: list[DimensionEvaluation] = Field(min_length=1, max_length=6)
    strengths: list[str] = Field(default_factory=list, max_length=10)
    gaps: list[str] = Field(default_factory=list, max_length=10)
    missing_requirements: list[str] = Field(default_factory=list, max_length=20)
    summary: str = Field(default="", max_length=1200)
    recommendation: Literal["reject", "review", "shortlist"] = "review"

    @property
    def all_evidence(self) -> list[EvidenceItem]:
        return [e for d in self.dimensions for e in d.evidence]

    @property
    def evidence_count(self) -> int:
        return len(self.all_evidence)


# ── Auditoría de sesgo ───────────────────────────────────────────────────────


class BiasIndicator(BaseModel):
    model_config = _STRICT
    category: Literal[
        "age", "gender", "nationality", "ethnicity", "religion", "disability",
        "marital_status", "appearance", "socioeconomic_proxy", "institution_prestige",
        "employment_gap", "other",
    ]
    excerpt: str = Field(max_length=400)
    explanation: str = Field(max_length=500)
    severity: Literal["low", "medium", "high", "critical"] = "medium"


class BiasAuditOutput(BaseModel):
    """Salida del auditor de sesgo.

    Audita el *razonamiento* del evaluador, no el CV. La distinción importa: lo
    que buscamos es que la justificación de una puntuación no se apoye en
    atributos que no deberían haber influido.
    """

    model_config = _STRICT
    bias_detected: bool = False
    indicators: list[BiasIndicator] = Field(default_factory=list, max_length=15)
    overall_assessment: str = Field(default="", max_length=800)

    @property
    def max_severity(self) -> str:
        order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        if not self.indicators:
            return "info"
        return max((i.severity for i in self.indicators), key=lambda s: order[s])


# ── Comunicación ─────────────────────────────────────────────────────────────


class EmailDraftOutput(BaseModel):
    """Variables para rellenar una plantilla aprobada.

    El modelo no redacta el correo: solo aporta los valores de un conjunto
    acotado de variables. Ni el destinatario, ni el asunto completo, ni el
    cuerpo salen de aquí. Es lo que impide que una instrucción escondida en un
    CV termine convertida en un correo.
    """

    model_config = _STRICT
    variables: dict[str, str] = Field(default_factory=dict)
    tone_note: str = Field(default="", max_length=300)

    @field_validator("variables")
    @classmethod
    def _limit_variable_size(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 20:
            raise ValueError("Demasiadas variables en el borrador")
        return {k: str(v)[:500] for k, v in value.items()}


#: Registro de esquemas por nombre lógico. El registro de prompts lo usa para
#: saber contra qué validar cada salida.
OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "ResumeExtractionOutput": ResumeExtractionOutput,
    "CandidateEvaluationOutput": CandidateEvaluationOutput,
    "BiasAuditOutput": BiasAuditOutput,
    "EmailDraftOutput": EmailDraftOutput,
}


def schema_hint(model: type[BaseModel]) -> str:
    """Descripción compacta del esquema para incluir en el prompt.

    Se usa el JSON Schema de Pydantic en lugar de un ejemplo escrito a mano
    porque así el prompt no puede desincronizarse del esquema real.
    """
    import json

    schema = model.model_json_schema()
    schema.pop("$defs", None)
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


__all__ = [
    "OUTPUT_SCHEMAS", "BiasAuditOutput", "BiasIndicator", "CandidateEvaluationOutput",
    "DimensionEvaluation", "EmailDraftOutput", "EvidenceItem", "ExtractedEducation",
    "ExtractedExperience", "ExtractedLanguage", "ResumeExtractionOutput", "schema_hint",
]
