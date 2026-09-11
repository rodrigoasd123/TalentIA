"""Agente de evaluación gobernada de TalentIA.

Fachada de la capa de IA. Es el único punto por el que el resto del sistema
habla con el agente, y expone una superficie deliberadamente pequeña: se le pasa
un candidato y una vacante, y devuelve un resultado con puntuación, evidencia
verificada y acciones **propuestas**.

Lo que el agente no hace, y no es un olvido:

* No escribe en la base de datos.
* No cambia el estado de ninguna candidatura.
* No envía correos.
* No tiene herramientas de escritura, red ni sistema de ficheros.

Todo eso corresponde a la capa de aplicación, que valida cada propuesta contra
el motor de políticas antes de actuar. El agente propone; el backend decide.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.ai.graphs.evaluation_graph import GRAPH_NAME, GRAPH_VERSION, build_evaluation_graph
from app.ai.prompts.registry import get_prompt_registry
from app.ai.state import WorkflowState, initial_state, state_summary
from app.core.config import get_settings
from app.core.logging import get_logger, get_trace_id, set_trace_id
from app.core.observability import METRICS, BudgetGuard, TokenUsage, timed
from app.domain.entities import (
    BiasAuditResult,
    Evaluation,
    JobRequirements,
    ResumeExtraction,
    WorkflowRun,
)
from app.domain.enums import Recommendation, ReviewReason, Severity, WorkflowStatus
from app.domain.ports import LLMPort
from app.domain.value_objects import ProposedAction, Score
from app.ai.nodes.deterministic import ScoreCalculationNode

logger = get_logger(__name__)

AGENT_NAME = "TalentIA"
AGENT_VERSION = "1.0.0"
AGENT_FULL_NAME = "TalentIA Evaluation Agent"


@dataclass(slots=True)
class EvaluationRequest:
    """Todo lo que TalentIA necesita para evaluar. Nada más, nada menos.

    Nótese que no recibe repositorios ni sesión de base de datos: quien invoca
    ya cargó los datos. Un agente sin acceso a la persistencia no puede
    corromperla, ni siquiera por error.
    """

    application_id: str
    candidate_id: str
    job_id: str
    resume_id: str
    resume_text: str
    candidate_name: str
    candidate_email: str
    requirements: JobRequirements
    job_title: str
    job_department: str = ""
    job_description: str = ""
    dry_run: bool = False
    trace_id: str = ""


@dataclass(slots=True)
class EvaluationResult:
    """Salida de TalentIA: una evaluación y unas acciones propuestas."""

    evaluation: Evaluation
    workflow_run: WorkflowRun
    proposed_actions: list[ProposedAction] = field(default_factory=list)
    extraction: ResumeExtraction | None = None
    anonymized_text: str = ""
    pii_map: dict[str, str] = field(default_factory=dict)
    state_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_human_review(self) -> bool:
        return self.evaluation.requires_human_review

    @property
    def total_score(self) -> float:
        return float(self.evaluation.total_score) if self.evaluation.total_score else 0.0

    def explain(self) -> str:
        """Explicación legible de la decisión, apta para mostrar al recruiter."""
        lines = [
            f"{AGENT_NAME} evaluó esta candidatura con una puntuación de "
            f"{self.total_score:.1f} sobre 100.",
            f"Recomendación: {self.evaluation.recommendation.value}.",
        ]
        if self.evaluation.hard_filter_results:
            failed = [r for r in self.evaluation.hard_filter_results if not r.passed]
            if failed:
                lines.append(
                    "Requisitos no cumplidos: "
                    + "; ".join(f.filter_label for f in failed)
                    + "."
                )
            else:
                lines.append("Cumple todos los requisitos obligatorios.")
        verified = sum(1 for e in self.evaluation.all_evidence if e.verified)
        total = len(self.evaluation.all_evidence)
        if total:
            lines.append(
                f"Evidencia: {verified} de {total} citas verificadas contra el CV "
                f"({self.evaluation.evidence_verification_rate:.0%})."
            )
        if self.evaluation.requires_human_review:
            if self.evaluation.review_reasons:
                reasons = ", ".join(r.value for r in self.evaluation.review_reasons)
                lines.append(f"Requiere revisión humana por: {reasons}.")
            else:
                # No hay incidencia: simplemente la automatización está apagada,
                # que es el comportamiento por defecto del sistema.
                lines.append(
                    "Pasa a revisión humana porque la automatización de esta decisión "
                    "está desactivada en la configuración."
                )
        return " ".join(lines)


class VeraAgent:
    """El agente. Orquesta el grafo y traduce su estado final a entidades."""

    name = AGENT_NAME
    version = AGENT_VERSION
    full_name = AGENT_FULL_NAME

    def __init__(
        self,
        llm: LLMPort,
        *,
        enable_llm_bias_audit: bool = True,
        budget_usd: float | None = None,
        prefer_langgraph: bool = True,
    ) -> None:
        settings = get_settings()
        self.llm = llm
        self.budget = BudgetGuard(
            budget_usd if budget_usd is not None else settings.llm_budget_usd_per_job
        )
        self.enable_llm_bias_audit = enable_llm_bias_audit
        self._graph = build_evaluation_graph(
            llm,
            budget=self.budget,
            enable_llm_bias_audit=enable_llm_bias_audit,
            prefer_langgraph=prefer_langgraph,
        )

    # ── API pública ──────────────────────────────────────────────────────────

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Ejecuta el grafo completo sobre una candidatura."""
        trace_id = set_trace_id(request.trace_id or None)
        run_id = uuid.uuid4().hex

        run = WorkflowRun(
            id=run_id,
            application_id=request.application_id,
            graph_name=GRAPH_NAME,
            agent_version=f"{AGENT_NAME}/{AGENT_VERSION}",
            status=WorkflowStatus.RUNNING,
            trace_id=trace_id,
            dry_run=request.dry_run,
        )

        logger.info(
            "Inicio de evaluación",
            agent=AGENT_NAME,
            version=AGENT_VERSION,
            application_id=request.application_id,
            job_id=request.job_id,
            model=self.llm.model_name,
            dry_run=request.dry_run,
        )

        state = initial_state(
            trace_id=trace_id,
            workflow_run_id=run_id,
            application_id=request.application_id,
            candidate_id=request.candidate_id,
            job_id=request.job_id,
            resume_id=request.resume_id,
            raw_resume_text=request.resume_text,
            candidate_name=request.candidate_name,
            candidate_email=request.candidate_email,
            requirements=request.requirements,
            job_title=request.job_title,
            job_department=request.job_department,
            job_description=request.job_description,
            agent_version=f"{AGENT_NAME}/{AGENT_VERSION}",
            dry_run=request.dry_run,
        )

        with timed("vera.evaluation.duration", graph=GRAPH_NAME) as timing:
            try:
                final_state = self._graph.invoke(state)
                run.status = WorkflowStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001 — se registra y se degrada
                logger.exception(
                    "El grafo falló de forma irrecuperable",
                    application_id=request.application_id,
                    error=str(exc)[:300],
                )
                run.status = WorkflowStatus.FAILED
                run.error = str(exc)[:500]
                final_state = state
                final_state["requires_human_review"] = True
                reasons = final_state.setdefault("review_reasons", [])
                if ReviewReason.LLM_FAILURE not in reasons:
                    reasons.append(ReviewReason.LLM_FAILURE)

        usage: TokenUsage = final_state.get("token_usage") or TokenUsage()
        run.finished_at = datetime.now(UTC)
        run.node_timings = dict(final_state.get("node_timings", {}))
        run.token_usage = usage.to_dict()
        run.cost_usd = round(usage.estimated_cost_usd, 6)
        if final_state.get("requires_human_review") and run.status is WorkflowStatus.COMPLETED:
            run.status = WorkflowStatus.AWAITING_HUMAN

        evaluation = self._build_evaluation(request, final_state, run)
        self._record_metrics(evaluation, run, timing.get("elapsed_seconds", 0.0))

        return EvaluationResult(
            evaluation=evaluation,
            workflow_run=run,
            proposed_actions=list(final_state.get("proposed_actions", [])),
            extraction=final_state.get("extraction"),
            anonymized_text=final_state.get("anonymized_text", ""),
            pii_map=dict(final_state.get("pii_map", {})),
            state_summary=state_summary(final_state),
        )

    def health(self) -> dict[str, Any]:
        """Estado del agente, para el panel de configuración y los health checks."""
        registry = get_prompt_registry()
        return {
            "agent": AGENT_NAME,
            "full_name": AGENT_FULL_NAME,
            "version": AGENT_VERSION,
            "graph": f"{GRAPH_NAME}@{GRAPH_VERSION}",
            "llm_configured": self.llm.is_configured,
            "model": self.llm.model_name,
            "llm_bias_audit": self.enable_llm_bias_audit,
            "budget_usd": self.budget.limit_usd,
            "budget_spent_usd": round(self.budget.spent_usd, 4),
            "prompts": [
                {"id": p.full_id, "schema": p.output_schema, "checksum": p.checksum}
                for p in registry.list_all()
            ],
        }

    # ── Traducción del estado a entidades ────────────────────────────────────

    def _build_evaluation(
        self, request: EvaluationRequest, state: WorkflowState, run: WorkflowRun
    ) -> Evaluation:
        """Convierte el estado final del grafo en una entidad de dominio.

        Toda la información de reproducibilidad (modelo, versiones de prompt,
        temperatura, coste) se guarda aquí. Sin ella, la evaluación sería un
        número sin procedencia.
        """
        outcome = state.get("scoring_outcome")
        evaluation_output = state.get("evaluation_output")
        evidence_report = state.get("evidence_report")
        bias_report = state.get("bias_report")
        bias_output = state.get("bias_audit_output")
        usage: TokenUsage = state.get("token_usage") or TokenUsage()

        dimension_scores = ScoreCalculationNode._build_dimension_scores(state)

        bias_audit = None
        if bias_report is not None or bias_output is not None:
            indicators = list(bias_report.categories) if bias_report else []
            if bias_output is not None:
                indicators.extend(i.category for i in bias_output.indicators)
            bias_audit = BiasAuditResult(
                bias_detected=bool(state.get("bias_detected")),
                indicators=sorted({str(i) for i in indicators}),
                categories=sorted({str(i) for i in indicators}),
                severity=(bias_report.max_severity if bias_report else Severity.INFO),
                explanation=(
                    bias_output.overall_assessment
                    if bias_output
                    else (bias_report.summary() if bias_report else "")
                ),
            )

        return Evaluation(
            application_id=request.application_id,
            evaluation_type="ai_automatic",
            passed_hard_filters=bool(state.get("passed_hard_filters")),
            hard_filter_results=list(state.get("filter_results", [])),
            dimension_scores=dimension_scores,
            total_score=(outcome.total if outcome else Score(value=0.0)),
            recommendation=(outcome.recommendation if outcome else Recommendation.REVIEW),
            missing_requirements=(
                list(evaluation_output.missing_requirements) if evaluation_output else
                [r.filter_label for r in state.get("filter_results", []) if not r.passed]
            ),
            strengths=list(evaluation_output.strengths) if evaluation_output else [],
            gaps=list(evaluation_output.gaps) if evaluation_output else [],
            summary=(evaluation_output.summary if evaluation_output else
                     (outcome.explanation if outcome else "Evaluación no completada")),
            bias_audit=bias_audit,
            evidence_verification_rate=(
                round(evidence_report.verification_rate, 4) if evidence_report else 0.0
            ),
            requires_human_review=bool(state.get("requires_human_review", True)),
            review_reasons=list(state.get("review_reasons", [])),
            model_name=self.llm.model_name,
            model_version=self.llm.model_name,
            prompt_versions=self._prompt_versions(),
            temperature=get_prompt_registry().get("candidate_evaluation").temperature,
            token_usage=usage.to_dict(),
            cost_usd=round(usage.estimated_cost_usd, 6),
            requirements_version=request.requirements.version,
            agent_version=f"{AGENT_NAME}/{AGENT_VERSION}",
            trace_id=get_trace_id(),
            workflow_run_id=run.id,
            created_by=AGENT_NAME.lower(),
        )

    @staticmethod
    def _prompt_versions() -> dict[str, str]:
        registry = get_prompt_registry()
        names = ["resume_extraction", "candidate_evaluation", "bias_audit"]
        versions: dict[str, str] = {}
        for name in names:
            try:
                versions[name] = registry.get(name).version
            except KeyError:  # pragma: no cover — prompt ausente en disco
                versions[name] = "missing"
        return versions

    @staticmethod
    def _record_metrics(evaluation: Evaluation, run: WorkflowRun, elapsed: float) -> None:
        METRICS.increment("vera.evaluations.total")
        METRICS.increment(
            "vera.evaluations.by_recommendation",
            recommendation=evaluation.recommendation.value,
        )
        if evaluation.requires_human_review:
            METRICS.increment("vera.evaluations.human_review")
        if evaluation.bias_audit and evaluation.bias_audit.bias_detected:
            METRICS.increment("vera.evaluations.bias_detected")
        METRICS.observe("vera.evaluation.cost_usd", run.cost_usd)
        METRICS.observe("vera.evaluation.evidence_rate", evaluation.evidence_verification_rate)
        METRICS.observe("vera.evaluation.elapsed_seconds", elapsed)


__all__ = [
    "AGENT_FULL_NAME", "AGENT_NAME", "AGENT_VERSION", "EvaluationRequest",
    "EvaluationResult", "VeraAgent",
]
