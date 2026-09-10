"""Caso de uso: evaluar una candidatura.

Es la operación central del sistema y donde se materializa el principio de
arquitectura. La secuencia es deliberada:

    precondiciones → política → ejecutar agente → persistir evaluación
    → validar cada acción propuesta → ejecutar solo lo permitido → auditar

El agente se ejecuta **antes** de que se decida nada, y lo que devuelve no se
aplica: cada acción propuesta pasa por el motor de políticas de forma
independiente. Una propuesta denegada no aborta la operación; genera un elemento
en la cola de revisión humana.

Todo ocurre dentro de una transacción. Si algo falla a mitad, no queda una
evaluación registrada sin su cambio de estado, ni un cambio de estado sin
auditoría.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.agent import AGENT_NAME, EvaluationRequest, EvaluationResult, VeraAgent
from app.ai.policies.policy_engine import PolicyContext, PolicyEngine, PolicyResult
from app.application.services.audit_service import Actor, AuditService
from app.application.services.review_service import ReviewService
from app.application.unit_of_work import UnitOfWork
from app.core.config import get_settings
from app.core.exceptions import (
    ApplicationNotFound,
    BudgetExceeded,
    CandidateNotFound,
    ConsentMissingOrExpired,
    JobNotFound,
    ResumeNotFound,
)
from app.core.logging import get_logger
from app.domain.entities import Application, Evaluation
from app.domain.enums import ActionType, ApplicationStatus, ReviewReason, Severity
from app.domain.rules.state_machine import ApplicationStateMachine
from app.domain.value_objects import ProposedAction
from app.infrastructure.llm.factory import build_llm_from_settings

logger = get_logger(__name__)


@dataclass(slots=True)
class EvaluationOutcome:
    """Lo que ocurrió realmente, que no siempre coincide con lo propuesto."""

    evaluation: Evaluation
    application: Application
    agent_result: EvaluationResult
    executed_actions: list[str] = field(default_factory=list)
    rejected_actions: list[dict[str, str]] = field(default_factory=list)
    review_item_id: str | None = None
    status_changed: bool = False

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation.id,
            "score": float(self.evaluation.total_score) if self.evaluation.total_score else 0.0,
            "recommendation": self.evaluation.recommendation.value,
            "status": self.application.status.value,
            "status_changed": self.status_changed,
            "executed_actions": self.executed_actions,
            "rejected_actions": self.rejected_actions,
            "review_item_id": self.review_item_id,
            "requires_human_review": self.evaluation.requires_human_review,
        }


class EvaluateApplicationUseCase:
    """Orquesta la evaluación completa de una candidatura."""

    def __init__(self, uow: UnitOfWork, *, agent: VeraAgent | None = None) -> None:
        self.uow = uow
        self.audit = AuditService(uow.audit)
        self.reviews = ReviewService(uow)
        self.policy = PolicyEngine()
        self._agent = agent

    def execute(
        self,
        *,
        application_id: str,
        actor: Actor,
        dry_run: bool | None = None,
        force_reevaluation: bool = False,
    ) -> EvaluationOutcome:
        application, candidate, job, resume = self._load(application_id)
        self._check_preconditions(candidate, application)

        settings = self.uow.settings
        flags = settings.feature_flags()
        effective_dry_run = flags["DRY_RUN"] if dry_run is None else dry_run

        self._check_budget(job.id, settings.llm_config()["budget_usd"])

        decision = self.policy.evaluate(
            PolicyContext(
                action=ActionType.EVALUATE_CANDIDATE,
                actor_id=actor.actor_id,
                is_human_actor=actor.actor_type.value == "user",
                application_id=application_id,
                application_status=application.status,
                dry_run=False,  # evaluar no tiene efecto externo; el dry-run afecta a las acciones
                feature_flags=flags,
            )
        )
        if not decision.allowed:
            self.audit.record(
                action="evaluation.denied",
                actor=actor,
                resource_type="application",
                resource_id=application_id,
                policy_result=str(decision),
                severity=Severity.MEDIUM,
            )
            from app.core.exceptions import PolicyDenied

            raise PolicyDenied(decision.reason)

        # La candidatura avanza por su ciclo de vida mientras se evalúa. Sin
        # esto, el pipeline visual muestra todo en «nuevo» y el estado deja de
        # reflejar lo que realmente está pasando con la persona.
        self._advance_to_evaluation(application, actor)

        # ── Ejecución del agente ─────────────────────────────────────────────
        agent = self._agent or self._build_agent()
        result = agent.evaluate(
            EvaluationRequest(
                application_id=application.id,
                candidate_id=candidate.id,
                job_id=job.id,
                resume_id=resume.id,
                resume_text=resume.raw_text,
                candidate_name=candidate.full_name,
                candidate_email=str(candidate.email or ""),
                requirements=job.requirements,
                job_title=job.title,
                job_department=job.department,
                job_description=job.description,
                dry_run=effective_dry_run,
            )
        )

        # ── Persistencia ─────────────────────────────────────────────────────
        self.uow.workflows.add(result.workflow_run)

        previous = self.uow.evaluations.get_current(application_id)
        evaluation = self.uow.evaluations.add(result.evaluation)
        if previous is not None and (force_reevaluation or True):
            # Reevaluar no borra ni modifica: marca la anterior como sustituida.
            self.uow.evaluations.supersede(previous.id, evaluation.id)

        # Los datos extraídos se guardan en el documento para poder reevaluar
        # sin volver a llamar al modelo.
        if result.extraction is not None:
            resume.extraction = result.extraction
            resume.is_suspicious = bool(result.state_summary.get("injection_detected"))
            self.uow.resumes.update(resume)

        outcome = EvaluationOutcome(
            evaluation=evaluation, application=application, agent_result=result
        )

        self._record_security_findings(result, actor, application_id)

        # ── Validación y ejecución de las acciones propuestas ────────────────
        for action in result.proposed_actions:
            self._process_action(
                action=action,
                outcome=outcome,
                actor=actor,
                candidate_email=str(candidate.email or ""),
                flags=flags,
                dry_run=effective_dry_run,
            )

        # Invariante del sistema: si la evaluación exige supervisión, tiene que
        # existir un elemento en la cola. No basta con que la candidatura quede
        # en estado «revisión humana»: un estado que anuncia trabajo pendiente
        # sin que nadie lo tenga asignado es peor que no tenerlo, porque el
        # pipeline muestra actividad que en realidad no existe.
        if evaluation.requires_human_review and outcome.review_item_id is None:
            self._enqueue_review(
                outcome,
                ProposedAction(
                    action_type=ActionType.REQUEST_HUMAN_REVIEW.value,
                    payload={"reasons": [r.value for r in evaluation.review_reasons]},
                    rationale=evaluation.summary[:300],
                    proposed_by_node="use_case_invariant",
                ),
            )

        if evaluation.total_score is not None:
            application.final_score = float(evaluation.total_score)
            self.uow.applications.update(application)

        # ── Auditoría ────────────────────────────────────────────────────────
        self.audit.record_evaluation(
            actor=Actor.agent(f"{AGENT_NAME}/{evaluation.agent_version}"),
            application_id=application_id,
            evaluation_id=evaluation.id,
            score=float(evaluation.total_score) if evaluation.total_score else None,
            recommendation=evaluation.recommendation.value,
            model=evaluation.model_name,
            agent_version=evaluation.agent_version,
            prompt_versions=evaluation.prompt_versions,
            requires_review=evaluation.requires_human_review,
            review_reasons=[r.value for r in evaluation.review_reasons],
            cost_usd=evaluation.cost_usd,
        )

        logger.info(
            "Candidatura evaluada",
            application_id=application_id,
            score=float(evaluation.total_score) if evaluation.total_score else None,
            recommendation=evaluation.recommendation.value,
            executed=outcome.executed_actions,
            rejected=len(outcome.rejected_actions),
            dry_run=effective_dry_run,
        )
        return outcome

    # ── Carga y precondiciones ───────────────────────────────────────────────

    def _load(self, application_id: str):  # noqa: ANN202
        application = self.uow.applications.get(application_id)
        if application is None:
            raise ApplicationNotFound(f"No existe la candidatura {application_id}")

        candidate = self.uow.candidates.get(application.candidate_id)
        if candidate is None:
            raise CandidateNotFound(f"No existe el candidato {application.candidate_id}")

        job = self.uow.jobs.get(application.job_id)
        if job is None:
            raise JobNotFound(f"No existe la vacante {application.job_id}")

        if not application.resume_id:
            raise ResumeNotFound("La candidatura no tiene CV asociado")
        resume = self.uow.resumes.get(application.resume_id)
        if resume is None:
            raise ResumeNotFound(f"No existe el documento {application.resume_id}")

        return application, candidate, job, resume

    @staticmethod
    def _check_preconditions(candidate, application) -> None:  # noqa: ANN001
        """El consentimiento se comprueba **antes** de procesar, no después.

        Procesar los datos de alguien cuyo consentimiento expiró y descubrirlo al
        final significa que ya se procesaron.
        """
        if not candidate.can_be_processed:
            raise ConsentMissingOrExpired(
                f"El candidato {candidate.id} no tiene consentimiento vigente para "
                "el tratamiento de sus datos"
            )
        if ApplicationStateMachine.is_terminal(application.status):
            from app.core.exceptions import InvalidStateTransition

            raise InvalidStateTransition(
                f"La candidatura está en «{application.status.value}», un estado "
                "cerrado. Para volver a evaluar hay que abrir una candidatura nueva."
            )

    def _check_budget(self, job_id: str, budget_usd: float) -> None:
        """Corta antes de gastar, no después.

        Un presupuesto agotado no degrada la calidad en silencio: el caso pasa a
        revisión humana.
        """
        if budget_usd <= 0:
            return
        spent = self.uow.workflows.total_cost_for_job(job_id)
        if spent >= budget_usd:
            raise BudgetExceeded(
                f"La vacante ha consumido ${spent:.2f} de un presupuesto de "
                f"${budget_usd:.2f}. Amplíalo en Configuración o revisa manualmente."
            )

    def _advance_to_evaluation(self, application: Application, actor: Actor) -> None:
        """Lleva la candidatura hasta «en evaluación» por el camino legítimo.

        Recorre las transiciones definidas en la máquina de estados en lugar de
        saltar directamente: así el historial refleja cada paso y no aparece un
        cambio de estado sin explicación entre dos etapas no contiguas.
        """
        path = {
            ApplicationStatus.NEW: [
                ApplicationStatus.RESUME_PROCESSED,
                ApplicationStatus.UNDER_EVALUATION,
            ],
            ApplicationStatus.RESUME_PROCESSED: [ApplicationStatus.UNDER_EVALUATION],
            ApplicationStatus.HUMAN_REVIEW: [ApplicationStatus.UNDER_EVALUATION],
        }.get(application.status, [])

        for target in path:
            if not ApplicationStateMachine.can_transition(application.status, target):
                break
            previous = application.status
            application.move_to(target)
            self.uow.applications.update(application)
            self.audit.record_status_change(
                actor=actor,
                application_id=application.id,
                previous=previous.value,
                new=target.value,
                reason="Progreso automático del pipeline de evaluación",
            )

    def _build_agent(self) -> VeraAgent:
        config = self.uow.settings.llm_config()
        return VeraAgent(
            build_llm_from_settings(self.uow.settings),
            enable_llm_bias_audit=bool(config["enable_bias_audit"]),
            budget_usd=float(config["budget_usd"]),
        )

    # ── Acciones propuestas ──────────────────────────────────────────────────

    def _process_action(
        self,
        *,
        action: ProposedAction,
        outcome: EvaluationOutcome,
        actor: Actor,
        candidate_email: str,
        flags: dict[str, bool],
        dry_run: bool,
    ) -> None:
        """Valida una propuesta del agente y la ejecuta solo si procede.

        Aquí es donde «el agente propone, el backend decide» deja de ser una
        frase: cada acción se evalúa por separado y una denegación no se ignora,
        se convierte en trabajo para una persona.
        """
        if action.action_type == ActionType.REQUEST_HUMAN_REVIEW.value:
            self._enqueue_review(outcome, action)
            return

        if action.action_type == ActionType.CHANGE_STATUS.value:
            target = ApplicationStatus(action.payload["target_status"])
            decision = self.policy.evaluate(
                PolicyContext(
                    action=ActionType.CHANGE_STATUS,
                    is_human_actor=False,
                    application_id=outcome.application.id,
                    application_status=outcome.application.status,
                    target_status=target,
                    candidate_email=candidate_email,
                    injection_detected=bool(
                        outcome.agent_result.state_summary.get("injection_detected")
                    ),
                    dry_run=dry_run,
                    feature_flags=flags,
                )
            )
            if decision.allowed:
                self._apply_status_change(outcome, target, actor, decision)
            else:
                outcome.rejected_actions.append(
                    {"action": str(action), "rule": decision.rule, "reason": decision.reason}
                )
                self._enqueue_review(outcome, action, policy=decision)
            return

        # Cualquier otro tipo de acción se rechaza por defecto. Añadir una
        # capacidad nueva exige tocar este método conscientemente.
        outcome.rejected_actions.append(
            {
                "action": str(action),
                "rule": "unsupported_action",
                "reason": "El caso de uso no admite esta acción",
            }
        )

    def _apply_status_change(
        self,
        outcome: EvaluationOutcome,
        target: ApplicationStatus,
        actor: Actor,
        decision: PolicyResult,
    ) -> None:
        previous = outcome.application.status
        try:
            ApplicationStateMachine.validate(previous, target, is_human_actor=False)
        except Exception as exc:  # noqa: BLE001 — la máquina de estados es la autoridad
            outcome.rejected_actions.append(
                {"action": f"change_status→{target.value}", "rule": "state_machine",
                 "reason": str(exc)}
            )
            return

        outcome.application.move_to(target)
        self.uow.applications.update(outcome.application)
        outcome.status_changed = True
        outcome.executed_actions.append(f"change_status→{target.value}")

        self.audit.record_status_change(
            actor=Actor.agent(outcome.evaluation.agent_version),
            application_id=outcome.application.id,
            previous=previous.value,
            new=target.value,
            reason=outcome.evaluation.summary[:200],
            policy_result=str(decision),
        )

    def _enqueue_review(
        self,
        outcome: EvaluationOutcome,
        action: ProposedAction,
        *,
        policy: PolicyResult | None = None,
    ) -> None:
        """Encola el caso para una persona, sin duplicar si ya hay uno abierto."""
        if outcome.review_item_id is not None:
            return
        existing = self.uow.reviews.find_open_for_application(outcome.application.id)
        if existing is not None:
            outcome.review_item_id = existing.id
            return

        item = self.reviews.create_from_evaluation(
            application=outcome.application,
            evaluation=outcome.evaluation,
            context={
                "proposed_action": str(action),
                "rationale": action.rationale,
                "policy_rule": policy.rule if policy else "",
                "policy_reason": policy.reason if policy else "",
            },
        )
        outcome.review_item_id = item.id
        outcome.executed_actions.append("request_human_review")

        # Si el caso entra en revisión, la candidatura debe reflejarlo. Un
        # elemento en cola sobre una candidatura que aparece «en evaluación»
        # confunde a quien mira el pipeline.
        if outcome.application.status != ApplicationStatus.HUMAN_REVIEW:
            if ApplicationStateMachine.can_transition(
                outcome.application.status, ApplicationStatus.HUMAN_REVIEW
            ):
                previous = outcome.application.status
                outcome.application.move_to(ApplicationStatus.HUMAN_REVIEW)
                self.uow.applications.update(outcome.application)
                outcome.status_changed = True
                self.audit.record_status_change(
                    actor=Actor.system(),
                    application_id=outcome.application.id,
                    previous=previous.value,
                    new=ApplicationStatus.HUMAN_REVIEW.value,
                    reason="Derivado a la cola de revisión humana",
                )

    def _record_security_findings(
        self, result: EvaluationResult, actor: Actor, application_id: str
    ) -> None:
        """Deja constancia separada de lo que fue un incidente de seguridad."""
        summary = result.state_summary
        if summary.get("injection_detected"):
            self.audit.record_security_incident(
                actor=Actor.agent(),
                resource_id=application_id,
                incident="prompt_injection_detected",
                severity=Severity.CRITICAL,
                injection_severity=summary.get("injection_severity", ""),
                detected_by="injection_detector",
            )
        if summary.get("bias_detected"):
            self.audit.record_security_incident(
                actor=Actor.agent(),
                resource_id=application_id,
                incident="bias_detected",
                severity=Severity.HIGH,
            )
        if ReviewReason.EVIDENCE_UNVERIFIABLE in result.evaluation.review_reasons:
            self.audit.record_security_incident(
                actor=Actor.agent(),
                resource_id=application_id,
                incident="evidence_unverifiable",
                severity=Severity.MEDIUM,
                verification_rate=result.evaluation.evidence_verification_rate,
            )


__all__ = ["EvaluateApplicationUseCase", "EvaluationOutcome"]
