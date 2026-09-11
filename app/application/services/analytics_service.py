"""Analítica del proceso: embudo, métricas de rendimiento y panel de equidad.

El panel de equidad merece una explicación, porque es la parte menos habitual y
la más importante.

Un sesgo algorítmico casi nunca es visible caso a caso. Ninguna evaluación
individual dice «he penalizado a esta persona por X»; lo que ocurre es que, al
mirar cien evaluaciones, aparece un patrón. Por eso la auditoría de sesgo tiene
dos niveles: uno por caso, que revisa el razonamiento, y este, que analiza la
distribución agregada.

Lo que se mide aquí **no son atributos protegidos** —el sistema no los almacena
para la evaluación, y esa es precisamente la protección—. Se miden proxies
observables de la calidad del proceso: dispersión de puntuaciones, tasa de
rechazo por filtro, proporción de evidencia verificada y grado de acuerdo entre
la sugerencia de la IA y la decisión humana.

Ese último indicador es el más revelador. Si los revisores contradicen a la IA el
5 % de las veces, o la IA es excelente o los revisores han dejado de mirar. Si la
contradicen el 60 %, el sistema no aporta valor. Ambos extremos son problemas, y
solo se ven mirando el conjunto.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.unit_of_work import UnitOfWork
from app.domain.entities import Evaluation
from app.domain.enums import ApplicationStatus, Recommendation

#: Orden canónico del embudo. Los estados terminales quedan fuera porque no son
#: una etapa por la que se pasa, sino una salida.
FUNNEL_STAGES: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.NEW,
    ApplicationStatus.RESUME_PROCESSED,
    ApplicationStatus.UNDER_EVALUATION,
    ApplicationStatus.HUMAN_REVIEW,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.APPROVED_FOR_INTERVIEW,
    ApplicationStatus.INTERVIEW_SCHEDULED,
    ApplicationStatus.INTERVIEWED,
    ApplicationStatus.APPROVED,
    ApplicationStatus.HIRED,
)

#: Rango esperado de revisión humana. Fuera de él, algo va mal en la
#: calibración: por debajo la supervisión es simbólica, por encima el sistema no
#: está ahorrando trabajo.
EXPECTED_REVIEW_RATE = (0.10, 0.45)

#: Umbral por debajo del cual la evidencia verificada indica un problema de
#: calidad del modelo o del prompt.
MIN_HEALTHY_EVIDENCE_RATE = 0.85


@dataclass(slots=True)
class EquityFinding:
    """Un patrón detectado en la distribución agregada."""

    code: str
    severity: str
    title: str
    detail: str
    recommendation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "recommendation": self.recommendation,
        }


@dataclass(slots=True)
class EquityReport:
    job_code: str
    sample_size: int
    findings: list[EquityFinding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def is_reliable(self) -> bool:
        """Con pocos casos, cualquier patrón es ruido.

        Se informa explícitamente en lugar de presentar porcentajes calculados
        sobre cuatro evaluaciones como si significaran algo.
        """
        return self.sample_size >= 20

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_code": self.job_code,
            "sample_size": self.sample_size,
            "reliable": self.is_reliable,
            "metrics": self.metrics,
            "findings": [f.to_dict() for f in self.findings],
        }


class AnalyticsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ── Panel ejecutivo ──────────────────────────────────────────────────────

    def dashboard(self) -> dict[str, Any]:
        applications = self.uow.applications.list_all(limit=5000)
        jobs = self.uow.jobs.list(limit=500)
        review_counts = self.uow.reviews.counts_by_status()

        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        this_week = [a for a in applications if a.applied_at >= week_ago]

        by_status = Counter(a.status.value for a in applications)
        hired = by_status.get(ApplicationStatus.HIRED.value, 0)
        rejected = by_status.get(ApplicationStatus.REJECTED.value, 0)
        shortlisted = sum(
            by_status.get(s.value, 0)
            for s in (
                ApplicationStatus.SHORTLISTED,
                ApplicationStatus.APPROVED_FOR_INTERVIEW,
                ApplicationStatus.INTERVIEW_SCHEDULED,
                ApplicationStatus.INTERVIEWED,
                ApplicationStatus.APPROVED,
                ApplicationStatus.HIRED,
            )
        )
        total = len(applications)

        return {
            "active_jobs": sum(1 for j in jobs if j.status.value == "open"),
            "total_jobs": len(jobs),
            "total_candidates": len({a.candidate_id for a in applications}),
            "total_applications": total,
            "applications_this_week": len(this_week),
            "by_status": dict(by_status),
            "shortlist_rate": _ratio(shortlisted, total),
            "rejection_rate": _ratio(rejected, total),
            "hire_rate": _ratio(hired, total),
            "pending_review": review_counts.get("pending", 0)
            + review_counts.get("assigned", 0)
            + review_counts.get("in_progress", 0),
            "avg_score": _mean([a.final_score for a in applications if a.final_score]),
            "sources": dict(Counter(a.source for a in applications)),
            "audit_events": len(self.uow.audit.list(limit=10000)),
        }

    def funnel(self, job_id: str | None = None) -> list[dict[str, Any]]:
        """Embudo con conversión entre etapas consecutivas.

        Se cuentan las candidaturas que **alcanzaron o superaron** cada etapa, no
        las que están en ella ahora mismo. Contar solo el estado actual daría un
        embudo lleno de ceros en cuanto la gente avanza.
        """
        applications = (
            self.uow.applications.list_for_job(job_id)
            if job_id
            else self.uow.applications.list_all(limit=5000)
        )
        order = {status: index for index, status in enumerate(FUNNEL_STAGES)}

        reached = Counter()
        for application in applications:
            position = order.get(application.status)
            if position is None:
                # Estado terminal: se contabiliza hasta donde llegó antes de salir.
                position = order[ApplicationStatus.UNDER_EVALUATION]
            for index in range(position + 1):
                reached[FUNNEL_STAGES[index]] += 1

        rows: list[dict[str, Any]] = []
        previous_count: int | None = None
        for stage in FUNNEL_STAGES:
            count = reached.get(stage, 0)
            rows.append(
                {
                    "stage": stage.value,
                    "count": count,
                    "conversion_from_previous": (
                        _ratio(count, previous_count) if previous_count else None
                    ),
                    "conversion_from_start": _ratio(count, reached.get(FUNNEL_STAGES[0], 0)),
                }
            )
            previous_count = count
        return rows

    def stage_durations(self, job_id: str | None = None) -> dict[str, float]:
        """Horas medias que las candidaturas llevan en su etapa actual.

        Es una aproximación: la medida exacta requeriría reconstruir cada
        transición desde la auditoría. Sirve para detectar atascos, que es para
        lo que se usa.
        """
        applications = (
            self.uow.applications.list_for_job(job_id)
            if job_id
            else self.uow.applications.list_all(limit=5000)
        )
        buckets: dict[str, list[float]] = {}
        for application in applications:
            buckets.setdefault(application.status.value, []).append(
                application.hours_in_stage
            )
        return {k: round(statistics.mean(v), 1) for k, v in buckets.items() if v}

    def sla_alerts(self, hours: int = 72) -> list[dict[str, Any]]:
        """Candidaturas estancadas más de lo admisible.

        Que alguien lleve cinco días esperando sin que nadie lo sepa es un fallo
        de proceso, no de la persona.
        """
        stale = self.uow.applications.stale_applications(hours)
        alerts = []
        for application in stale:
            candidate = self.uow.candidates.get(application.candidate_id)
            job = self.uow.jobs.get(application.job_id)
            alerts.append(
                {
                    "application_id": application.id,
                    "candidate": candidate.full_name if candidate else "—",
                    "job_code": job.code if job else "—",
                    "status": application.status.value,
                    "hours_in_stage": round(application.hours_in_stage, 1),
                    "days": round(application.hours_in_stage / 24, 1),
                }
            )
        return sorted(alerts, key=lambda a: -a["hours_in_stage"])

    def source_analytics(self) -> list[dict[str, Any]]:
        """Qué origen de candidaturas produce mejores resultados."""
        applications = self.uow.applications.list_all(limit=5000)
        by_source: dict[str, list[Any]] = {}
        for application in applications:
            by_source.setdefault(application.source, []).append(application)

        rows = []
        for source, items in by_source.items():
            scores = [a.final_score for a in items if a.final_score is not None]
            advanced = sum(
                1 for a in items
                if a.status in {
                    ApplicationStatus.SHORTLISTED, ApplicationStatus.APPROVED_FOR_INTERVIEW,
                    ApplicationStatus.INTERVIEWED, ApplicationStatus.APPROVED,
                    ApplicationStatus.HIRED,
                }
            )
            rows.append(
                {
                    "source": source,
                    "applications": len(items),
                    "avg_score": _mean(scores),
                    "shortlist_rate": _ratio(advanced, len(items)),
                }
            )
        return sorted(rows, key=lambda r: -(r["avg_score"] or 0))

    def candidate_disposition_report(self) -> list[dict[str, Any]]:
        """Seguimiento operativo sin PII sensible ni inferencias de un LLM."""
        interviewed = {
            ApplicationStatus.INTERVIEWED, ApplicationStatus.APPROVED,
            ApplicationStatus.HIRED,
        }
        applications = self.uow.applications.list_all(limit=10000)
        by_candidate: dict[str, list[Any]] = {}
        for application in applications:
            by_candidate.setdefault(application.candidate_id, []).append(application)

        rows: list[dict[str, Any]] = []
        for candidate in self.uow.candidates.list(limit=10000):
            candidate_apps = by_candidate.get(candidate.id, [])
            adecco_source = next(
                (
                    value
                    for value in [candidate.source, *(app.source for app in candidate_apps)]
                    if "adecco" in (value or "").casefold()
                ),
                None,
            )
            categories: list[str] = []
            if adecco_source:
                categories.append("adecco")
            if any(app.status in interviewed for app in candidate_apps):
                categories.append("entrevistado")
            if any(app.status is ApplicationStatus.REJECTED for app in candidate_apps):
                categories.append("descartado")
            if not categories:
                continue
            latest = max(candidate_apps, key=lambda app: app.applied_at, default=None)
            job = self.uow.jobs.get(latest.job_id) if latest else None
            rows.append({
                "candidate_id": candidate.id, "candidate": candidate.full_name,
                "client": candidate.client, "recruiter": candidate.recruiter,
                "source": adecco_source or (latest.source if latest else candidate.source),
                "categories": categories,
                "application_id": latest.id if latest else None,
                "application_status": latest.status.value if latest else None,
                "job_code": job.code if job else None,
                "job_title": job.title if job else None,
                "date": (
                    candidate.record_date.isoformat() if candidate.record_date
                    else candidate.created_at.date().isoformat()
                ),
            })
        return sorted(rows, key=lambda row: (row["date"], row["candidate"]), reverse=True)

    # ── Panel de equidad ─────────────────────────────────────────────────────

    def equity_report(self, job_id: str | None = None) -> EquityReport:
        """Analiza la distribución agregada en busca de patrones anómalos."""
        if job_id:
            job = self.uow.jobs.get(job_id)
            evaluations = self.uow.evaluations.list_for_job(job_id)
            code = job.code if job else job_id
        else:
            evaluations = [
                e
                for application in self.uow.applications.list_all(limit=5000)
                for e in [self.uow.evaluations.get_current(application.id)]
                if e is not None
            ]
            code = "todas las vacantes"

        report = EquityReport(job_code=code, sample_size=len(evaluations))
        if not evaluations:
            return report

        report.metrics = self._equity_metrics(evaluations)
        report.findings = self._equity_findings(report.metrics, evaluations)
        return report

    def _equity_metrics(self, evaluations: list[Evaluation]) -> dict[str, Any]:
        scores = [float(e.total_score) for e in evaluations if e.total_score is not None]

        # La evidencia solo se promedia sobre las evaluaciones que llegaron a la
        # fase semántica. Incluir a quienes quedaron fuera por un filtro
        # determinístico —que nunca tuvieron citas porque nunca se les pidieron—
        # hundiría la media y dispararía una alarma falsa sobre la calidad del
        # modelo.
        semantic = [e for e in evaluations if e.dimension_scores]
        evidence_rates = [e.evidence_verification_rate for e in semantic]
        recommendations = Counter(e.recommendation.value for e in evaluations)
        review_needed = sum(1 for e in evaluations if e.requires_human_review)
        bias_flagged = sum(
            1 for e in evaluations if e.bias_audit and e.bias_audit.bias_detected
        )

        failed_filters = Counter()
        for evaluation in evaluations:
            for result in evaluation.hard_filter_results:
                if not result.passed and result.mandatory:
                    failed_filters[result.filter_label] += 1

        return {
            "evaluations": len(evaluations),
            "semantically_evaluated": len(semantic),
            "score_mean": _mean(scores),
            "score_median": round(statistics.median(scores), 2) if scores else None,
            "score_stdev": (
                round(statistics.stdev(scores), 2) if len(scores) > 1 else 0.0
            ),
            "score_min": round(min(scores), 2) if scores else None,
            "score_max": round(max(scores), 2) if scores else None,
            "evidence_rate_mean": _mean(evidence_rates),
            "recommendations": dict(recommendations),
            "human_review_rate": _ratio(review_needed, len(evaluations)),
            "bias_flag_rate": _ratio(bias_flagged, len(evaluations)),
            "failed_filters": dict(failed_filters.most_common()),
            "human_agreement": self._human_agreement(evaluations),
        }

    def _human_agreement(self, evaluations: list[Evaluation]) -> dict[str, Any]:
        """Grado de acuerdo entre la sugerencia de la IA y la decisión humana.

        Es el indicador que revela si la supervisión es real. Un acuerdo del
        100 % puede significar que la IA acierta siempre o que nadie la está
        revisando de verdad, y esas dos cosas se parecen mucho desde fuera.
        """
        agreed = disagreed = 0
        for evaluation in evaluations:
            item = self.uow.reviews.find_open_for_application(evaluation.application_id)
            if item is not None:
                continue  # sin resolver todavía
            decisions = [
                e for e in self.uow.audit.list(
                    resource_id=evaluation.application_id,
                    action="human_review.decided",
                    limit=10,
                )
            ]
            if not decisions:
                continue
            decision = (decisions[0].new_state or {}).get("decision", "")
            suggested = evaluation.recommendation
            coincide = (
                (decision == "approve" and suggested is Recommendation.SHORTLIST)
                or (decision == "reject" and suggested is Recommendation.REJECT)
            )
            agreed += int(coincide)
            disagreed += int(not coincide)

        resolved = agreed + disagreed
        return {
            "resolved_reviews": resolved,
            "agreement_rate": _ratio(agreed, resolved),
            "override_rate": _ratio(disagreed, resolved),
        }

    @staticmethod
    def _equity_findings(
        metrics: dict[str, Any], evaluations: list[Evaluation]
    ) -> list[EquityFinding]:
        findings: list[EquityFinding] = []

        review_rate = metrics.get("human_review_rate")
        if review_rate is not None:
            low, high = EXPECTED_REVIEW_RATE
            if review_rate > high:
                findings.append(
                    EquityFinding(
                        code="review_rate_high",
                        severity="medium",
                        title="Tasa de revisión humana muy alta",
                        detail=(
                            f"El {review_rate:.0%} de las evaluaciones acaba en revisión "
                            f"manual, por encima del {high:.0%} esperado."
                        ),
                        recommendation=(
                            "Revisa los umbrales de la vacante y el margen de zona gris. "
                            "Una cola saturada acaba revisándose por encima, que es lo "
                            "contrario de lo que se busca."
                        ),
                    )
                )
            elif review_rate < low:
                findings.append(
                    EquityFinding(
                        code="review_rate_low",
                        severity="high",
                        title="Supervisión humana casi inexistente",
                        detail=(
                            f"Solo el {review_rate:.0%} de las evaluaciones pasa por una "
                            "persona."
                        ),
                        recommendation=(
                            "Comprueba que los umbrales no se hayan relajado en exceso. "
                            "Un sistema de decisión sobre personas sin supervisión "
                            "efectiva es difícil de defender."
                        ),
                    )
                )

        evidence = metrics.get("evidence_rate_mean")
        # Se exige una muestra mínima de evaluaciones semánticas: con tres casos
        # cualquier porcentaje es anecdótico y avisar de ello solo genera ruido.
        if (
            evidence is not None
            and evidence < MIN_HEALTHY_EVIDENCE_RATE
            and metrics.get("semantically_evaluated", 0) >= 5
        ):
            findings.append(
                EquityFinding(
                    code="evidence_low",
                    severity="high",
                    title="Evidencia verificada por debajo de lo saludable",
                    detail=(
                        f"Solo el {evidence:.0%} de las citas del modelo se localiza en "
                        "los CV originales."
                    ),
                    recommendation=(
                        "Revisa el prompt de evaluación: el modelo está afirmando cosas "
                        "que no puede respaldar. Considera no promover esta versión."
                    ),
                )
            )

        stdev = metrics.get("score_stdev")
        if stdev is not None and stdev < 5 and metrics["evaluations"] >= 10:
            findings.append(
                EquityFinding(
                    code="score_compression",
                    severity="medium",
                    title="Las puntuaciones apenas se diferencian",
                    detail=(
                        f"La desviación típica es de {stdev:.1f} puntos: el sistema está "
                        "puntuando a casi todo el mundo igual."
                    ),
                    recommendation=(
                        "Un ranking sin dispersión no ordena nada. Revisa si los pesos "
                        "de la vacante discriminan realmente entre perfiles."
                    ),
                )
            )

        agreement = metrics.get("human_agreement", {})
        resolved = agreement.get("resolved_reviews", 0)
        override = agreement.get("override_rate")
        if resolved >= 10 and override is not None:
            if override > 0.5:
                findings.append(
                    EquityFinding(
                        code="override_high",
                        severity="high",
                        title="Los revisores contradicen a la IA con frecuencia",
                        detail=(
                            f"El {override:.0%} de las decisiones humanas va en contra de "
                            "la recomendación automática."
                        ),
                        recommendation=(
                            "El sistema no está aportando valor en su forma actual. "
                            "Revisa criterios, pesos y prompt antes de ampliar su uso."
                        ),
                    )
                )
            elif override < 0.05:
                findings.append(
                    EquityFinding(
                        code="override_suspiciously_low",
                        severity="medium",
                        title="Los revisores casi nunca discrepan",
                        detail=(
                            f"Solo el {override:.0%} de las decisiones humanas se aparta "
                            "de la sugerencia automática."
                        ),
                        recommendation=(
                            "Puede indicar que la supervisión se ha vuelto un trámite. "
                            "Conviene comprobar que los revisores están viendo la "
                            "evidencia antes de decidir."
                        ),
                    )
                )

        bias_rate = metrics.get("bias_flag_rate")
        if bias_rate is not None and bias_rate > 0.05:
            findings.append(
                EquityFinding(
                    code="bias_flags_frequent",
                    severity="critical",
                    title="El auditor de sesgo se activa con frecuencia",
                    detail=f"El {bias_rate:.0%} de las evaluaciones presenta indicios de sesgo.",
                    recommendation=(
                        "Revisa manualmente una muestra de esas evaluaciones y considera "
                        "detener la automatización de esta vacante mientras se investiga."
                    ),
                )
            )

        failed = metrics.get("failed_filters", {})
        total = metrics.get("evaluations", 0)
        for label, count in failed.items():
            if total and count / total > 0.8:
                findings.append(
                    EquityFinding(
                        code="filter_excludes_almost_everyone",
                        severity="medium",
                        title=f"El filtro «{label}» excluye a casi todo el mundo",
                        detail=f"Descarta al {count / total:.0%} de las candidaturas.",
                        recommendation=(
                            "Comprueba que el requisito es realmente imprescindible y "
                            "que está bien redactado. Un filtro que excluye a casi todos "
                            "suele indicar un criterio mal calibrado, no un mercado vacío."
                        ),
                    )
                )
        return findings


def _ratio(part: int, whole: int | None) -> float | None:
    if not whole:
        return None
    return round(part / whole, 4)


def _mean(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(statistics.mean(clean), 2) if clean else None


__all__ = [
    "EXPECTED_REVIEW_RATE", "FUNNEL_STAGES", "MIN_HEALTHY_EVIDENCE_RATE",
    "AnalyticsService", "EquityFinding", "EquityReport",
]
