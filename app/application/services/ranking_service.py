"""Ranking explicable y comparación entre candidaturas.

Un ranking que solo devuelve números ordenados no sirve para decidir. La pregunta
que un hiring manager se hace de verdad no es «¿quién puntúa más?», sino «¿por
qué esta persona y no aquella?». Este servicio responde a la segunda.

Dos límites deliberados:

**No se comparan candidaturas de vacantes distintas.** Las puntuaciones son
relativas a los criterios de cada convocatoria; un 85 en una vacante de datos y
un 85 en una de infraestructura no significan lo mismo, y ordenarlos juntos
produciría un ranking sin sentido que además parecería riguroso.

**Toda comparación arrastra su evidencia.** Si una dimensión marca la diferencia,
se muestran las citas que la sostienen en cada perfil. Una diferencia de 20
puntos sin evidencia detrás no es un argumento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.unit_of_work import UnitOfWork
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities import Evaluation
from app.domain.rules.scoring import compare_candidates


@dataclass(slots=True)
class RankedCandidate:
    position: int
    application_id: str
    candidate_id: str
    candidate_name: str
    score: float
    recommendation: str
    passed_hard_filters: bool
    evidence_rate: float
    requires_human_review: bool
    review_reasons: list[str] = field(default_factory=list)
    dimensions: dict[str, float] = field(default_factory=dict)
    missing_requirements: list[str] = field(default_factory=list)
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "application_id": self.application_id,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "score": self.score,
            "recommendation": self.recommendation,
            "passed_hard_filters": self.passed_hard_filters,
            "evidence_rate": self.evidence_rate,
            "requires_human_review": self.requires_human_review,
            "review_reasons": self.review_reasons,
            "dimensions": self.dimensions,
            "missing_requirements": self.missing_requirements,
            "status": self.status,
        }


@dataclass(slots=True)
class Comparison:
    """Comparación explicada entre dos candidaturas de la misma vacante."""

    job_code: str
    candidate_a: str
    candidate_b: str
    score_a: float
    score_b: float
    rows: list[dict[str, Any]] = field(default_factory=list)
    narrative: str = ""

    @property
    def difference(self) -> float:
        return round(self.score_a - self.score_b, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_code": self.job_code,
            "candidate_a": self.candidate_a,
            "candidate_b": self.candidate_b,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "difference": self.difference,
            "rows": self.rows,
            "narrative": self.narrative,
        }


class RankingService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def rank_job(self, job_id: str, *, include_rejected: bool = False) -> list[RankedCandidate]:
        """Ordena las candidaturas de una vacante con su desglose."""
        job = self.uow.jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"No existe la vacante {job_id}")

        ranked: list[RankedCandidate] = []
        for application in self.uow.applications.list_for_job(job_id):
            evaluation = self.uow.evaluations.get_current(application.id)
            if evaluation is None:
                continue
            if not include_rejected and not evaluation.passed_hard_filters:
                continue
            candidate = self.uow.candidates.get(application.candidate_id)
            ranked.append(
                RankedCandidate(
                    position=0,
                    application_id=application.id,
                    candidate_id=application.candidate_id,
                    candidate_name=candidate.full_name if candidate else "—",
                    score=float(evaluation.total_score) if evaluation.total_score else 0.0,
                    recommendation=evaluation.recommendation.value,
                    passed_hard_filters=evaluation.passed_hard_filters,
                    evidence_rate=evaluation.evidence_verification_rate,
                    requires_human_review=evaluation.requires_human_review,
                    review_reasons=[r.value for r in evaluation.review_reasons],
                    dimensions={
                        d.dimension.value: d.score for d in evaluation.dimension_scores
                    },
                    missing_requirements=list(evaluation.missing_requirements),
                    status=application.status.value,
                )
            )

        # Quien no supera los filtros va al final con independencia de su
        # puntuación semántica: un requisito excluyente no se compensa con
        # buenas notas en el resto.
        ranked.sort(key=lambda r: (not r.passed_hard_filters, -r.score))
        for index, item in enumerate(ranked, start=1):
            item.position = index
        return ranked

    def compare(self, application_a: str, application_b: str) -> Comparison:
        """Explica dimensión a dimensión por qué una candidatura supera a la otra."""
        app_a = self.uow.applications.get(application_a)
        app_b = self.uow.applications.get(application_b)
        if app_a is None or app_b is None:
            raise NotFoundError("Alguna de las candidaturas no existe")

        if app_a.job_id != app_b.job_id:
            raise ValidationError(
                "Solo se pueden comparar candidaturas de la misma vacante. "
                "Las puntuaciones son relativas a los criterios de cada convocatoria, "
                "así que compararlas entre vacantes distintas daría un resultado "
                "aparentemente riguroso pero sin significado."
            )

        eval_a = self.uow.evaluations.get_current(application_a)
        eval_b = self.uow.evaluations.get_current(application_b)
        if eval_a is None or eval_b is None:
            raise ValidationError("Alguna de las candidaturas no tiene evaluación vigente")

        cand_a = self.uow.candidates.get(app_a.candidate_id)
        cand_b = self.uow.candidates.get(app_b.candidate_id)
        job = self.uow.jobs.get(app_a.job_id)

        rows = compare_candidates(eval_a.dimension_scores, eval_b.dimension_scores)
        comparison = Comparison(
            job_code=job.code if job else "",
            candidate_a=cand_a.full_name if cand_a else "A",
            candidate_b=cand_b.full_name if cand_b else "B",
            score_a=float(eval_a.total_score) if eval_a.total_score else 0.0,
            score_b=float(eval_b.total_score) if eval_b.total_score else 0.0,
            rows=rows,
        )
        comparison.narrative = self._narrate(comparison, eval_a, eval_b)
        return comparison

    @staticmethod
    def _narrate(comparison: Comparison, eval_a: Evaluation, eval_b: Evaluation) -> str:
        """Redacta la explicación en lenguaje llano.

        Se construye a partir de los datos ya calculados; no interviene ningún
        modelo. Una explicación generada por IA sobre una decisión de IA añadiría
        una capa más que verificar.
        """
        a, b = comparison.candidate_a, comparison.candidate_b
        partes: list[str] = []

        if abs(comparison.difference) < 2:
            partes.append(
                f"{a} y {b} obtienen puntuaciones prácticamente equivalentes "
                f"({comparison.score_a:.1f} frente a {comparison.score_b:.1f}). "
                "La diferencia está dentro del margen de error del sistema y no debería "
                "usarse por sí sola para decidir."
            )
        else:
            lider, seguidor = (a, b) if comparison.difference > 0 else (b, a)
            partes.append(
                f"{lider} supera a {seguidor} por {abs(comparison.difference):.1f} puntos "
                f"({comparison.score_a:.1f} frente a {comparison.score_b:.1f})."
            )

        decisivas = [r for r in comparison.rows if abs(float(r["weighted_difference"])) >= 2][:3]
        if decisivas:
            detalle = []
            for fila in decisivas:
                dimension = fila["dimension"]
                diferencia = float(fila["difference"])
                favorecido = a if diferencia > 0 else b
                detalle.append(
                    f"en «{dimension}» {favorecido} obtiene {abs(diferencia):.0f} puntos más "
                    f"(peso {fila['weight']:.0f}%)"
                )
            partes.append("La diferencia se concentra en: " + "; ".join(detalle) + ".")

        if eval_a.passed_hard_filters != eval_b.passed_hard_filters:
            incumple = b if eval_a.passed_hard_filters else a
            faltantes = (
                eval_b.missing_requirements if eval_a.passed_hard_filters
                else eval_a.missing_requirements
            )
            partes.append(
                f"Además, {incumple} no cumple requisitos obligatorios"
                + (f": {', '.join(faltantes[:3])}." if faltantes else ".")
            )

        for nombre, evaluacion in ((a, eval_a), (b, eval_b)):
            if evaluacion.evidence_verification_rate < 0.85:
                partes.append(
                    f"Atención: la evaluación de {nombre} tiene solo un "
                    f"{evaluacion.evidence_verification_rate:.0%} de evidencia verificada, "
                    "así que su puntuación es menos fiable."
                )
        return " ".join(partes)

    def top_candidates(self, job_id: str, limit: int = 5) -> list[RankedCandidate]:
        return self.rank_job(job_id)[:limit]

    def pipeline_view(self, job_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Candidaturas agrupadas por etapa, para el pipeline visual."""
        applications = (
            self.uow.applications.list_for_job(job_id)
            if job_id
            else self.uow.applications.list_all(limit=2000)
        )
        columns: dict[str, list[dict[str, Any]]] = {}
        for application in applications:
            candidate = self.uow.candidates.get(application.candidate_id)
            job = self.uow.jobs.get(application.job_id)
            columns.setdefault(application.status.value, []).append(
                {
                    "application_id": application.id,
                    "candidate_name": candidate.full_name if candidate else "—",
                    "job_code": job.code if job else "—",
                    "score": application.final_score,
                    "hours_in_stage": round(application.hours_in_stage, 1),
                    "assigned_to": application.assigned_to,
                }
            )
        for items in columns.values():
            items.sort(key=lambda x: -(x["score"] or 0))
        return columns


__all__ = ["Comparison", "RankedCandidate", "RankingService"]
