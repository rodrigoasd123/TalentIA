"""Cálculo de la puntuación total y decisión de revisión humana.

El modelo puntúa cada dimensión por separado; **el total lo calcula este
módulo**, en Python, a partir de los pesos configurados en la vacante. Es una
decisión deliberada: si el modelo devolviera el total, un candidato podría
intentar influir en él mediante el contenido de su CV, y además el número
dejaría de ser reproducible.

Aquí también vive la regla de cuándo un caso debe pasar por una persona.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.entities import DimensionScore, ResumeExtraction
from app.domain.enums import Recommendation, ReviewReason, ScoringDimension
from app.domain.value_objects import FilterResult, Score, ScoringWeights

#: Umbral de confianza de extracción por debajo del cual el caso se revisa.
MIN_PARSE_CONFIDENCE = 0.65

#: Años de experiencia a partir de los cuales el perfil se considera senior y
#: la decisión no se automatiza, con independencia de su puntuación.
SENIOR_YEARS_THRESHOLD = 10.0


@dataclass(slots=True)
class ScoringOutcome:
    """Resultado del cálculo determinístico posterior a la evaluación del modelo."""

    total: Score
    recommendation: Recommendation
    requires_human_review: bool
    review_reasons: list[ReviewReason] = field(default_factory=list)
    explanation: str = ""


class ScoringPolicy:
    """Combina puntuaciones por dimensión y decide si hace falta una persona."""

    def __init__(
        self,
        *,
        auto_shortlist_enabled: bool = False,
        auto_rejection_enabled: bool = False,
        max_unverified_evidence_ratio: float = 0.20,
    ) -> None:
        self.auto_shortlist_enabled = auto_shortlist_enabled
        self.auto_rejection_enabled = auto_rejection_enabled
        self.max_unverified_evidence_ratio = max_unverified_evidence_ratio

    # ── Cálculo ──────────────────────────────────────────────────────────────

    def compute_total(
        self, dimension_scores: list[DimensionScore], weights: ScoringWeights
    ) -> Score:
        """Media ponderada sobre las dimensiones con peso asignado.

        Si el modelo no puntuó alguna dimensión configurada, se renormaliza
        sobre las presentes en lugar de asumir cero: un fallo del modelo no debe
        traducirse en una penalización silenciosa al candidato.
        """
        if not dimension_scores:
            return Score(value=0.0)
        total_weight = 0.0
        accumulated = 0.0
        for item in dimension_scores:
            weight = weights.weight_of(item.dimension)
            if weight <= 0:
                continue
            accumulated += item.score * weight
            total_weight += weight
        if total_weight <= 0:
            return Score(value=0.0)
        return Score(value=accumulated / total_weight)

    def apply_weights(
        self, raw_scores: dict[ScoringDimension, tuple[float, str]], weights: ScoringWeights
    ) -> list[DimensionScore]:
        """Asocia a cada dimensión su peso configurado."""
        return [
            DimensionScore(
                dimension=dimension,
                score=value,
                weight=weights.weight_of(dimension),
                reasoning=reasoning,
            )
            for dimension, (value, reasoning) in raw_scores.items()
            if weights.weight_of(dimension) > 0
        ]

    # ── Decisión ─────────────────────────────────────────────────────────────

    def decide(
        self,
        *,
        total: Score,
        minimum_score: float,
        review_threshold: float,
        filter_results: list[FilterResult],
        extraction: ResumeExtraction | None,
        evidence_verification_rate: float,
        bias_detected: bool,
        injection_detected: bool,
        evaluation_performed: bool = True,
        extra_reasons: list[ReviewReason] | None = None,
    ) -> ScoringOutcome:
        """Determina recomendación y necesidad de revisión humana.

        El orden de las comprobaciones importa: los motivos de seguridad se
        evalúan antes que la puntuación, porque un intento de manipulación
        invalida el resultado numérico con independencia de cuál sea.
        """
        reasons: list[ReviewReason] = list(extra_reasons or [])

        if injection_detected:
            reasons.append(ReviewReason.INJECTION_DETECTED)
        if bias_detected:
            reasons.append(ReviewReason.BIAS_DETECTED)
        # La evidencia solo se exige cuando hubo evaluación semántica. Si el
        # candidato quedó excluido por un filtro determinístico, no se le pidió
        # al modelo que citase nada y reclamar evidencia inexistente confundiría
        # el motivo real de la decisión.
        if evaluation_performed and evidence_verification_rate < (
            1 - self.max_unverified_evidence_ratio
        ):
            reasons.append(ReviewReason.EVIDENCE_UNVERIFIABLE)

        failed_mandatory = [r for r in filter_results if r.mandatory and not r.passed]
        if failed_mandatory:
            reasons.append(ReviewReason.HARD_FILTER_FAILED)

        if extraction is not None:
            if extraction.average_confidence < MIN_PARSE_CONFIDENCE:
                reasons.append(ReviewReason.LOW_PARSE_CONFIDENCE)
            if not extraction.experiences and not extraction.education:
                reasons.append(ReviewReason.INCOMPLETE_RESUME)
            if extraction.total_years_experience >= SENIOR_YEARS_THRESHOLD:
                reasons.append(ReviewReason.SENIOR_CANDIDATE)

        in_grey_zone = total.is_within(minimum_score, review_threshold)
        if in_grey_zone:
            reasons.append(ReviewReason.SCORE_BORDERLINE)

        recommendation = self._recommend(
            total=total,
            minimum_score=minimum_score,
            failed_mandatory=bool(failed_mandatory),
            in_grey_zone=in_grey_zone,
            blocked=bool(reasons) and not self._only_soft_reasons(reasons),
        )

        requires_human = self._requires_human(
            recommendation=recommendation, reasons=reasons
        )

        return ScoringOutcome(
            total=total,
            recommendation=recommendation,
            requires_human_review=requires_human,
            review_reasons=_dedupe(reasons),
            explanation=self._explain(
                total, minimum_score, failed_mandatory, reasons, recommendation
            ),
        )

    # ── Reglas internas ──────────────────────────────────────────────────────

    @staticmethod
    def _only_soft_reasons(reasons: list[ReviewReason]) -> bool:
        soft = {ReviewReason.SCORE_BORDERLINE, ReviewReason.SENIOR_CANDIDATE}
        return all(r in soft for r in reasons)

    def _recommend(
        self,
        *,
        total: Score,
        minimum_score: float,
        failed_mandatory: bool,
        in_grey_zone: bool,
        blocked: bool,
    ) -> Recommendation:
        if failed_mandatory:
            return Recommendation.REJECT
        if blocked or in_grey_zone:
            return Recommendation.REVIEW
        if total.is_above(minimum_score):
            return Recommendation.SHORTLIST
        return Recommendation.REJECT

    def _requires_human(
        self, *, recommendation: Recommendation, reasons: list[ReviewReason]
    ) -> bool:
        """Un caso se automatiza solo si el flag correspondiente está activo y
        no hay ningún motivo de revisión pendiente."""
        if reasons:
            return True
        if recommendation is Recommendation.SHORTLIST:
            return not self.auto_shortlist_enabled
        if recommendation is Recommendation.REJECT:
            return not self.auto_rejection_enabled
        return True

    @staticmethod
    def _explain(
        total: Score,
        minimum_score: float,
        failed_mandatory: list[FilterResult],
        reasons: list[ReviewReason],
        recommendation: Recommendation,
    ) -> str:
        parts = [f"Puntuación total {total} sobre un mínimo de {minimum_score:.0f}."]
        if failed_mandatory:
            labels = ", ".join(r.filter_label for r in failed_mandatory)
            parts.append(f"No cumple requisitos obligatorios: {labels}.")
        if reasons:
            parts.append(
                "Requiere revisión humana por: "
                + ", ".join(sorted({r.value for r in reasons}))
                + "."
            )
        parts.append(f"Recomendación del sistema: {recommendation.value}.")
        return " ".join(parts)


def _dedupe(reasons: list[ReviewReason]) -> list[ReviewReason]:
    seen: set[ReviewReason] = set()
    result: list[ReviewReason] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            result.append(reason)
    return result


def compare_candidates(
    a_scores: list[DimensionScore], b_scores: list[DimensionScore]
) -> list[dict[str, object]]:
    """Explica dimensión a dimensión por qué un candidato puntúa más que otro.

    Devuelve datos, no texto: la interfaz decide cómo presentarlos. Existe para
    responder a "¿por qué A y no B?", que es la pregunta que realmente se hace un
    hiring manager.
    """
    by_dimension_a = {d.dimension: d for d in a_scores}
    by_dimension_b = {d.dimension: d for d in b_scores}
    rows: list[dict[str, object]] = []
    for dimension in sorted(set(by_dimension_a) | set(by_dimension_b), key=lambda d: d.value):
        da = by_dimension_a.get(dimension)
        db = by_dimension_b.get(dimension)
        score_a = da.score if da else 0.0
        score_b = db.score if db else 0.0
        weight = (da or db).weight if (da or db) else 0.0
        rows.append(
            {
                "dimension": dimension.value,
                "score_a": score_a,
                "score_b": score_b,
                "difference": round(score_a - score_b, 2),
                "weight": weight,
                "weighted_difference": round((score_a - score_b) * weight / 100, 2),
                "evidence_a": [e.quote for e in (da.verified_evidence if da else [])],
                "evidence_b": [e.quote for e in (db.verified_evidence if db else [])],
            }
        )
    return sorted(rows, key=lambda r: abs(float(r["weighted_difference"])), reverse=True)


__all__ = [
    "MIN_PARSE_CONFIDENCE", "SENIOR_YEARS_THRESHOLD", "ScoringOutcome",
    "ScoringPolicy", "compare_candidates",
]
