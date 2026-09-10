"""Estado del workflow de VERA.

El estado es explícito y tipado. Cada nodo declara qué claves lee y cuáles
escribe, y eso permite comprobar en un test que, por ejemplo, el nodo de
puntuación **nunca** accede a ``pii_map``. Un estado laxo tipo diccionario libre
haría esa garantía imposible de verificar.

``pii_map`` merece una nota: contiene la correspondencia entre los marcadores de
anonimización y los valores reales. Vive en el estado porque el backend necesita
rehidratar los datos para mostrarlos a una persona autorizada, pero ningún nodo
que hable con el modelo tiene permiso para leerlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from app.ai.guardrails.bias_detector import BiasReport
from app.ai.guardrails.evidence_verifier import VerificationReport
from app.ai.guardrails.injection_detector import SanitizationResult
from app.ai.schemas import (
    BiasAuditOutput,
    CandidateEvaluationOutput,
    ResumeExtractionOutput,
)
from app.core.observability import TokenUsage
from app.domain.entities import JobRequirements, ResumeExtraction
from app.domain.enums import ReviewReason
from app.domain.rules.scoring import ScoringOutcome
from app.domain.value_objects import FilterResult, ProposedAction


@dataclass(slots=True)
class NodeError:
    """Fallo ocurrido en un nodo, con lo necesario para diagnosticarlo."""

    node: str
    error_type: str
    message: str
    attempt: int = 1
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "error_type": self.error_type,
            "message": self.message,
            "attempt": self.attempt,
            "recoverable": self.recoverable,
        }


class WorkflowState(TypedDict, total=False):
    """Estado que atraviesa el grafo de evaluación.

    ``total=False`` porque el estado se va completando nodo a nodo: al empezar
    solo están los identificadores y el texto del CV.
    """

    # ── Identidad y trazabilidad ─────────────────────────────────────────────
    trace_id: str
    workflow_run_id: str
    application_id: str
    candidate_id: str
    job_id: str
    resume_id: str
    agent_version: str
    dry_run: bool

    # ── Entrada ──────────────────────────────────────────────────────────────
    raw_resume_text: str
    candidate_name: str
    candidate_email: str
    sanitized_text: str
    anonymized_text: str

    # ── Seguridad ────────────────────────────────────────────────────────────
    sanitization: SanitizationResult
    injection_detected: bool
    injection_severity: str
    pii_map: dict[str, str]
    pii_categories: list[str]
    pii_redaction_count: int

    # ── Extracción ───────────────────────────────────────────────────────────
    extraction_output: ResumeExtractionOutput
    extraction: ResumeExtraction
    extraction_attempts: int

    # ── Requisitos y filtros ─────────────────────────────────────────────────
    job_title: str
    job_department: str
    job_description: str
    requirements: JobRequirements
    filter_results: list[FilterResult]
    passed_hard_filters: bool

    # ── Evaluación ───────────────────────────────────────────────────────────
    evaluation_output: CandidateEvaluationOutput
    evidence_report: VerificationReport
    scoring_attempts: int
    scoring_outcome: ScoringOutcome

    # ── Sesgo ────────────────────────────────────────────────────────────────
    bias_report: BiasReport
    bias_audit_output: BiasAuditOutput
    bias_detected: bool

    # ── Decisión ─────────────────────────────────────────────────────────────
    requires_human_review: bool
    review_reasons: list[ReviewReason]
    policy_decisions: list[dict[str, str]]
    proposed_actions: list[ProposedAction]

    # ── Observabilidad ───────────────────────────────────────────────────────
    node_timings: dict[str, float]
    node_sequence: list[str]
    token_usage: TokenUsage
    budget_exhausted: bool
    errors: list[NodeError]
    terminated_early: bool
    termination_reason: str


def initial_state(
    *,
    trace_id: str,
    workflow_run_id: str,
    application_id: str,
    candidate_id: str,
    job_id: str,
    resume_id: str,
    raw_resume_text: str,
    candidate_name: str,
    candidate_email: str,
    requirements: JobRequirements,
    job_title: str,
    job_department: str = "",
    job_description: str = "",
    agent_version: str = "",
    dry_run: bool = False,
) -> WorkflowState:
    """Construye el estado inicial con todos los acumuladores ya vacíos.

    Inicializar aquí las listas y diccionarios evita que cada nodo tenga que
    comprobar si existen, que es una fuente clásica de fallos intermitentes.
    """
    return WorkflowState(
        trace_id=trace_id,
        workflow_run_id=workflow_run_id,
        application_id=application_id,
        candidate_id=candidate_id,
        job_id=job_id,
        resume_id=resume_id,
        agent_version=agent_version,
        dry_run=dry_run,
        raw_resume_text=raw_resume_text,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        sanitized_text="",
        anonymized_text="",
        injection_detected=False,
        injection_severity="info",
        pii_map={},
        pii_categories=[],
        pii_redaction_count=0,
        extraction_attempts=0,
        scoring_attempts=0,
        job_title=job_title,
        job_department=job_department,
        job_description=job_description,
        requirements=requirements,
        filter_results=[],
        passed_hard_filters=False,
        bias_detected=False,
        requires_human_review=True,
        review_reasons=[],
        policy_decisions=[],
        proposed_actions=[],
        node_timings={},
        node_sequence=[],
        token_usage=TokenUsage(),
        budget_exhausted=False,
        errors=[],
        terminated_early=False,
        termination_reason="",
    )


def add_error(state: WorkflowState, error: NodeError) -> None:
    state.setdefault("errors", []).append(error)


def add_review_reason(state: WorkflowState, reason: ReviewReason) -> None:
    reasons = state.setdefault("review_reasons", [])
    if reason not in reasons:
        reasons.append(reason)
    state["requires_human_review"] = True


def add_proposed_action(state: WorkflowState, action: ProposedAction) -> None:
    state.setdefault("proposed_actions", []).append(action)


def state_summary(state: WorkflowState) -> dict[str, Any]:
    """Resumen del estado apto para logs y auditoría.

    Nunca incluye ``pii_map``, ``raw_resume_text`` ni los textos completos: un
    resumen de estado que arrastre el CV entero convierte el log en una copia no
    controlada de datos personales.
    """
    usage = state.get("token_usage") or TokenUsage()
    outcome = state.get("scoring_outcome")
    return {
        "trace_id": state.get("trace_id", ""),
        "workflow_run_id": state.get("workflow_run_id", ""),
        "application_id": state.get("application_id", ""),
        "nodes_executed": list(state.get("node_sequence", [])),
        "injection_detected": state.get("injection_detected", False),
        "injection_severity": state.get("injection_severity", "info"),
        "pii_redactions": state.get("pii_redaction_count", 0),
        "pii_categories": list(state.get("pii_categories", [])),
        "policy_decisions": list(state.get("policy_decisions", [])),
        "passed_hard_filters": state.get("passed_hard_filters", False),
        "total_score": float(outcome.total) if outcome else None,
        "recommendation": outcome.recommendation.value if outcome else None,
        "requires_human_review": state.get("requires_human_review", True),
        "review_reasons": [r.value for r in state.get("review_reasons", [])],
        "bias_detected": state.get("bias_detected", False),
        "evidence_rate": (
            round(state["evidence_report"].verification_rate, 3)
            if state.get("evidence_report")
            else None
        ),
        "proposed_actions": [str(a) for a in state.get("proposed_actions", [])],
        "errors": [e.to_dict() for e in state.get("errors", [])],
        "token_usage": usage.to_dict(),
        "terminated_early": state.get("terminated_early", False),
    }


__all__ = [
    "NodeError", "WorkflowState", "add_error", "add_proposed_action",
    "add_review_reason", "initial_state", "state_summary",
]
