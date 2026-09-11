"""Objetos de valor del dominio.

Un objeto de valor no tiene identidad: dos puntuaciones de 87 son la misma cosa.
Se validan en el constructor y son inmutables, de modo que un valor inválido no
puede existir en el sistema. Esto elimina una clase entera de comprobaciones
defensivas repartidas por el código.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    LANGUAGE_LEVEL_ORDER,
    CriterionMode,
    CriterionStatus,
    FilterOperator,
    LanguageLevel,
    ScoringDimension,
)

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]{2,}$")
_FROZEN = ConfigDict(frozen=True, extra="forbid")


class EmailAddress(BaseModel):
    """Dirección de correo validada y normalizada."""

    model_config = _FROZEN
    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, v: str) -> str:
        normalized = v.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError(f"Dirección de correo inválida: {v!r}")
        return normalized

    @property
    def domain(self) -> str:
        return self.value.split("@", 1)[1]

    def masked(self) -> str:
        """Versión enmascarada para mostrar sin revelar la dirección completa."""
        local, domain = self.value.split("@", 1)
        head = local[:2] if len(local) > 2 else local[:1]
        return f"{head}{'•' * 5}@{domain}"

    def __str__(self) -> str:
        return self.value


class Score(BaseModel):
    """Puntuación en el rango cerrado 0–100."""

    model_config = _FROZEN
    value: float = Field(ge=0.0, le=100.0)

    @field_validator("value")
    @classmethod
    def _round(cls, v: float) -> float:
        return round(v, 2)

    def is_above(self, threshold: float) -> bool:
        return self.value >= threshold

    def is_within(self, threshold: float, margin: float) -> bool:
        """¿Está la puntuación en la zona gris alrededor del umbral?"""
        return abs(self.value - threshold) <= margin

    def __float__(self) -> float:
        return self.value

    def __str__(self) -> str:
        return f"{self.value:.1f}"


class EvidenceSpan(BaseModel):
    """Fragmento del CV que respalda una afirmación del evaluador.

    ``verified`` lo rellena el verificador de evidencia, nunca el modelo. Que el
    modelo pudiera marcar su propia evidencia como verificada anularía el control.
    """

    model_config = ConfigDict(extra="forbid")
    quote: str = Field(min_length=3, max_length=500)
    dimension: ScoringDimension
    verified: bool = False
    match_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    source_offset: int | None = None

    def __str__(self) -> str:
        mark = "✓" if self.verified else "✗"
        return f"{mark} [{self.dimension.value}] {self.quote}"


class ScoringWeights(BaseModel):
    """Distribución de pesos por dimensión. Debe sumar exactamente 100."""

    model_config = ConfigDict(extra="forbid")
    weights: dict[ScoringDimension, float]

    @model_validator(mode="after")
    def _validate_sum(self) -> Self:
        if not self.weights:
            raise ValueError("Debe definirse al menos una dimensión de scoring")
        total = sum(self.weights.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Los pesos deben sumar 100, suman {total:.2f}")
        for dimension, weight in self.weights.items():
            if weight < 0:
                raise ValueError(f"Peso negativo en {dimension.value}")
        return self

    @property
    def dimensions(self) -> list[ScoringDimension]:
        return sorted(self.weights, key=lambda d: -self.weights[d])

    def weight_of(self, dimension: ScoringDimension) -> float:
        return self.weights.get(dimension, 0.0)

    @classmethod
    def balanced_default(cls) -> ScoringWeights:
        """Reparto por defecto para una vacante técnica."""
        return cls(
            weights={
                ScoringDimension.TECHNICAL: 30.0,
                ScoringDimension.EXPERIENCE: 25.0,
                ScoringDimension.PROJECTS: 20.0,
                ScoringDimension.SEMANTIC: 15.0,
                ScoringDimension.EDUCATION: 10.0,
            }
        )


class HardFilter(BaseModel):
    """Criterio determinístico de admisión. Nunca se evalúa con IA.

    ``legal_basis`` es obligatorio y no decorativo: obliga a justificar por qué
    un criterio excluyente es pertinente para el puesto. Un filtro que nadie
    puede justificar por escrito probablemente no debería existir.
    """

    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1, max_length=60)
    operator: FilterOperator
    value: Any
    label: str = Field(min_length=1, max_length=160)
    mandatory: bool = True
    legal_basis: str = Field(min_length=3, max_length=300)
    mode: CriterionMode | None = None
    penalty_percent: float | None = Field(default=None, ge=0, le=100)

    @property
    def effective_mode(self) -> CriterionMode:
        if self.mode is not None:
            return self.mode
        # Compatibilidad: los idiomas heredados pasan a ponderados; los demás
        # filtros conservan su comportamiento excluyente.
        if self.operator is FilterOperator.MIN_LEVEL:
            return CriterionMode.WEIGHTED
        return CriterionMode.EXCLUDENT

    @property
    def effective_penalty_percent(self) -> float:
        if self.penalty_percent is not None:
            return self.penalty_percent
        return 15.0 if self.effective_mode is CriterionMode.WEIGHTED else 0.0

    @model_validator(mode="after")
    def _validate_operator_value(self) -> Self:
        list_ops = {FilterOperator.CONTAINS_ALL, FilterOperator.CONTAINS_ANY, FilterOperator.IN}
        if self.operator in list_ops and not isinstance(self.value, (list, tuple, set)):
            raise ValueError(f"El operador {self.operator.value} requiere una lista de valores")
        if self.operator in {FilterOperator.GTE, FilterOperator.LTE} and not isinstance(
            self.value, (int, float)
        ):
            raise ValueError(f"El operador {self.operator.value} requiere un valor numérico")
        if self.operator is FilterOperator.MIN_LEVEL:
            if not isinstance(self.value, dict) or "language" not in self.value:
                raise ValueError("min_level requiere {'language': ..., 'level': ...}")
            LanguageLevel(str(self.value.get("level", "")).lower())
        return self


class FilterResult(BaseModel):
    """Resultado de aplicar un filtro concreto a un candidato."""

    model_config = ConfigDict(extra="forbid")
    filter_label: str
    field: str
    passed: bool
    mandatory: bool
    expected: Any
    actual: Any
    explanation: str
    status: CriterionStatus = CriterionStatus.FAILED
    mode: CriterionMode = CriterionMode.EXCLUDENT
    penalty_percent: float = Field(default=0.0, ge=0, le=100)

    @property
    def is_blocking(self) -> bool:
        return self.mode is CriterionMode.EXCLUDENT and self.status is CriterionStatus.FAILED

    def __str__(self) -> str:
        return f"{'✓' if self.passed else '✗'} {self.filter_label}: {self.explanation}"


class DateRange(BaseModel):
    """Periodo con fin opcional (posición actual)."""

    model_config = _FROZEN
    start: date
    end: date | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.end and self.end < self.start:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
        if self.start > date.today():
            raise ValueError("La fecha de inicio no puede estar en el futuro")
        return self

    @property
    def months(self) -> int:
        finish = self.end or date.today()
        return max(0, (finish.year - self.start.year) * 12 + finish.month - self.start.month)

    @property
    def years(self) -> float:
        return round(self.months / 12, 2)

    @property
    def is_current(self) -> bool:
        return self.end is None


class LanguageSkill(BaseModel):
    model_config = _FROZEN
    language: str
    level: LanguageLevel

    @field_validator("language")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return v.strip().lower()

    def satisfies(self, required_level: LanguageLevel) -> bool:
        return LANGUAGE_LEVEL_ORDER[self.level] >= LANGUAGE_LEVEL_ORDER[required_level]


class ConsentRecord(BaseModel):
    """Consentimiento del candidato para un propósito concreto.

    Sin consentimiento vigente el sistema no procesa al candidato. La comprobación
    es una precondición del caso de uso, no un aviso en la interfaz.
    """

    model_config = ConfigDict(extra="forbid")
    purpose: str
    granted_at: date
    expires_at: date
    legal_basis: str = "consentimiento explícito del candidato"
    revoked: bool = False

    @property
    def is_valid(self) -> bool:
        return not self.revoked and self.expires_at >= date.today()


class ProposedAction(BaseModel):
    """Acción que el agente propone y que el backend decidirá si ejecuta.

    Es el corazón del modelo de confianza del sistema: el grafo produce estos
    objetos y termina. Quien decide y ejecuta es el motor de políticas y la capa
    de aplicación, fuera del alcance de cualquier contenido no confiable.
    """

    model_config = ConfigDict(extra="forbid")
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    proposed_by_node: str = ""

    def __str__(self) -> str:
        return f"{self.action_type}({', '.join(f'{k}={v!r}' for k, v in self.payload.items())})"


__all__ = [
    "ConsentRecord", "DateRange", "EmailAddress", "EvidenceSpan", "FilterResult",
    "HardFilter", "LanguageSkill", "ProposedAction", "Score", "ScoringWeights",
]
