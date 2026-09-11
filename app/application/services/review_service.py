"""Cola de revisión humana.

El punto donde el sistema devuelve el control a una persona. Cuatro reglas de
gobernanza que el código hace cumplir, no solo documenta:

1. **Toda anulación de una decisión de IA exige justificación escrita.** Sin
   texto no hay decisión: el método lanza.
2. **Un elemento nunca se resuelve solo al vencer el plazo.** Expira, se
   reasigna y sube de prioridad, pero sigue esperando a una persona.
3. **La prioridad la determina el motivo, no quien lo crea.** Un intento de
   manipulación es crítico aunque la puntuación sea excelente.
4. **Modificar una puntuación queda auditado con el valor anterior y el nuevo.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.application.services.audit_service import Actor, AuditService
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.entities import Application, Evaluation, HumanReviewItem
from app.domain.enums import (
    REVIEW_SLA_HOURS,
    ApplicationStatus,
    Permission,
    ReviewReason,
    ReviewStatus,
    Severity,
)
from app.domain.rules.state_machine import ApplicationStateMachine

logger = get_logger(__name__)

#: Prioridad por motivo. Los de seguridad encabezan la cola porque un intento de
#: manipulación no debe esperar un día a que alguien lo mire.
_PRIORITY_BY_REASON: dict[ReviewReason, Severity] = {
    ReviewReason.INJECTION_DETECTED: Severity.CRITICAL,
    ReviewReason.BIAS_DETECTED: Severity.CRITICAL,
    ReviewReason.JOB_OFFER: Severity.CRITICAL,
    ReviewReason.EVIDENCE_UNVERIFIABLE: Severity.HIGH,
    ReviewReason.SENSITIVE_EMAIL: Severity.HIGH,
    ReviewReason.SENIOR_CANDIDATE: Severity.HIGH,
    ReviewReason.AMBIGUOUS_REJECTION: Severity.HIGH,
    ReviewReason.HARD_FILTER_FAILED: Severity.MEDIUM,
    ReviewReason.CRITERION_UNVERIFIED: Severity.MEDIUM,
    ReviewReason.SCORE_BORDERLINE: Severity.MEDIUM,
    ReviewReason.LOW_PARSE_CONFIDENCE: Severity.MEDIUM,
    ReviewReason.DATA_CONFLICT: Severity.MEDIUM,
    ReviewReason.SCORE_OVERRIDE: Severity.MEDIUM,
    ReviewReason.LLM_FAILURE: Severity.MEDIUM,
    ReviewReason.BUDGET_EXCEEDED: Severity.MEDIUM,
    ReviewReason.INCOMPLETE_RESUME: Severity.LOW,
    ReviewReason.POSSIBLE_DUPLICATE: Severity.LOW,
}

_SEVERITY_ORDER = {
    Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2,
    Severity.HIGH: 3, Severity.CRITICAL: 4,
}

#: Acciones que un revisor puede tomar.
DECISIONS = ("approve", "reject", "modify", "reevaluate", "escalate")


@dataclass(slots=True)
class ReviewDecision:
    """Resultado de resolver un elemento de la cola."""

    item: HumanReviewItem
    application: Application
    status_changed: bool = False
    new_status: str = ""
    requires_reevaluation: bool = False


class ReviewService:
    def __init__(self, uow) -> None:  # noqa: ANN001 — evita import circular
        self.uow = uow
        self.audit = AuditService(uow.audit)

    # ── Creación ─────────────────────────────────────────────────────────────

    def create_from_evaluation(
        self,
        *,
        application: Application,
        evaluation: Evaluation,
        context: dict[str, Any] | None = None,
    ) -> HumanReviewItem:
        """Crea un elemento a partir de una evaluación que requiere supervisión."""
        reasons = list(evaluation.review_reasons) or [ReviewReason.SCORE_BORDERLINE]
        priority = self._priority(reasons)

        item = HumanReviewItem(
            application_id=application.id,
            evaluation_id=evaluation.id,
            reasons=reasons,
            priority=priority,
            status=ReviewStatus.PENDING,
            sla_hours=self._sla(reasons),
            context={
                "score": float(evaluation.total_score) if evaluation.total_score else None,
                "recommendation": evaluation.recommendation.value,
                "passed_hard_filters": evaluation.passed_hard_filters,
                "evidence_rate": evaluation.evidence_verification_rate,
                "summary": evaluation.summary[:600],
                **(context or {}),
            },
        )
        stored = self.uow.reviews.add(item)

        self.audit.record(
            action="human_review.enqueued",
            actor=Actor.agent(evaluation.agent_version),
            resource_type="application",
            resource_id=application.id,
            new_state={
                "review_id": stored.id,
                "reasons": [r.value for r in reasons],
                "priority": priority.value,
            },
            severity=Severity.INFO if priority != Severity.CRITICAL else Severity.HIGH,
        )
        logger.info(
            "Caso encolado para revisión humana",
            application_id=application.id,
            review_id=stored.id,
            priority=priority.value,
            reasons=[r.value for r in reasons],
            sla_hours=stored.sla_hours,
        )
        return stored

    def request_manual_validation(
        self,
        *,
        application: Application,
        actor: Actor,
        reason: ReviewReason = ReviewReason.CRITERION_UNVERIFIED,
        note: str = "",
    ) -> tuple[HumanReviewItem, bool]:
        """Crea un caso humano explícito o devuelve el que ya está abierto."""
        existing = self.uow.reviews.find_open_for_application(application.id)
        if existing is not None:
            return existing, False

        evaluation = self.uow.evaluations.get_current(application.id)
        item = HumanReviewItem(
            application_id=application.id,
            evaluation_id=evaluation.id if evaluation else None,
            reasons=[reason],
            priority=self._priority([reason]),
            status=ReviewStatus.PENDING,
            sla_hours=self._sla([reason]),
            context={
                "score": float(application.final_score)
                if application.final_score is not None else None,
                "summary": note.strip()[:600],
                "requested_manually": True,
            },
        )
        stored = self.uow.reviews.add(item)

        previous = application.status
        if (
            previous is not ApplicationStatus.HUMAN_REVIEW
            and ApplicationStateMachine.can_transition(
                previous, ApplicationStatus.HUMAN_REVIEW
            )
        ):
            application.move_to(ApplicationStatus.HUMAN_REVIEW)
            self.uow.applications.update(application)
            self.audit.record_status_change(
                actor=actor,
                application_id=application.id,
                previous=previous.value,
                new=ApplicationStatus.HUMAN_REVIEW.value,
                reason="Validación humana solicitada",
                approved_by=actor.actor_id,
            )

        self.audit.record(
            action="human_review.requested_manually",
            actor=actor,
            resource_type="application",
            resource_id=application.id,
            new_state={"review_id": stored.id, "reason": reason.value},
        )
        return stored, True

    @staticmethod
    def _priority(reasons: list[ReviewReason]) -> Severity:
        """La prioridad la marca el motivo más grave, no el promedio."""
        if not reasons:
            return Severity.MEDIUM
        return max(
            (_PRIORITY_BY_REASON.get(r, Severity.MEDIUM) for r in reasons),
            key=lambda s: _SEVERITY_ORDER[s],
        )

    @staticmethod
    def _sla(reasons: list[ReviewReason]) -> int:
        """El plazo más corto de entre los motivos aplicables."""
        if not reasons:
            return 24
        return min(REVIEW_SLA_HOURS.get(r, 24) for r in reasons)

    # ── Asignación ───────────────────────────────────────────────────────────

    def claim(self, item_id: str, *, actor: Actor) -> HumanReviewItem:
        """Un revisor toma un elemento. Evita que dos personas trabajen lo mismo."""
        item = self._get(item_id)
        if item.status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.MODIFIED}:
            raise ValidationError("Ese elemento ya fue resuelto")
        if item.assigned_to and item.assigned_to != actor.actor_id:
            raise ValidationError(
                f"El elemento ya está asignado a {item.assigned_to}"
            )
        item.assigned_to = actor.actor_id
        item.status = ReviewStatus.IN_PROGRESS
        item.touch()
        self.uow.reviews.update(item)

        self.audit.record(
            action="human_review.claimed",
            actor=actor,
            resource_type="application",
            resource_id=item.application_id,
            review_id=item.id,
        )
        return item

    # ── Resolución ───────────────────────────────────────────────────────────

    def decide(
        self,
        *,
        item_id: str,
        decision: str,
        justification: str,
        actor: Actor,
        actor_permissions: frozenset[Permission] = frozenset(),
        score_override: float | None = None,
    ) -> ReviewDecision:
        """Resuelve un elemento de la cola.

        La justificación es obligatoria en todos los casos. Puede parecer
        excesivo para una aprobación rutinaria, pero es lo que convierte el
        historial en algo defendible: cuando alguien pregunte por qué se rechazó
        a una persona, la respuesta no puede ser un campo vacío.
        """
        if decision not in DECISIONS:
            raise ValidationError(
                f"Decisión no admitida: «{decision}». Válidas: {', '.join(DECISIONS)}"
            )
        if len(justification.strip()) < 10:
            raise ValidationError(
                "La justificación es obligatoria y debe explicar el motivo "
                "(al menos 10 caracteres)"
            )
        if Permission.REVIEW_DECIDE not in actor_permissions and actor_permissions:
            from app.core.exceptions import PermissionDenied

            raise PermissionDenied("Falta el permiso review:decide")

        item = self._get(item_id)
        application = self.uow.applications.get(item.application_id)
        if application is None:
            raise NotFoundError(f"No existe la candidatura {item.application_id}")

        previous_score = item.context.get("score")
        result = ReviewDecision(item=item, application=application)

        handlers = {
            "approve": self._approve,
            "reject": self._reject,
            "modify": self._modify,
            "reevaluate": self._reevaluate,
            "escalate": self._escalate,
        }
        handlers[decision](result, actor, score_override)

        item.decided_by = actor.actor_id
        item.decided_at = datetime.now(UTC)
        item.decision_note = justification.strip()
        item.touch()
        self.uow.reviews.update(item)

        self.audit.record_human_decision(
            actor=actor,
            application_id=application.id,
            review_id=item.id,
            decision=decision,
            justification=justification.strip(),
            previous_score=previous_score,
            new_score=score_override if score_override is not None else previous_score,
        )
        logger.info(
            "Elemento de revisión resuelto",
            review_id=item.id,
            decision=decision,
            by=actor.actor_id,
            status_changed=result.status_changed,
        )
        return result

    def _approve(
        self, result: ReviewDecision, actor: Actor, _: float | None
    ) -> None:
        result.item.status = ReviewStatus.APPROVED
        self._transition(result, ApplicationStatus.SHORTLISTED, actor)

    def _reject(self, result: ReviewDecision, actor: Actor, _: float | None) -> None:
        result.item.status = ReviewStatus.REJECTED
        self._transition(result, ApplicationStatus.REJECTED, actor)

    def _modify(
        self, result: ReviewDecision, actor: Actor, score_override: float | None
    ) -> None:
        """Modificar la puntuación de la IA.

        No se altera la evaluación original: es inmutable. Se registra la
        anulación humana y se actualiza la puntuación de la candidatura, de modo
        que el historial conserva ambas cifras y quién decidió cada una.
        """
        if score_override is None:
            raise ValidationError(
                "Para modificar hay que indicar la nueva puntuación"
            )
        if not 0 <= score_override <= 100:
            raise ValidationError("La puntuación debe estar entre 0 y 100")

        result.item.status = ReviewStatus.MODIFIED
        result.item.score_override = score_override
        result.application.final_score = score_override
        self.uow.applications.update(result.application)

        if ReviewReason.SCORE_OVERRIDE not in result.item.reasons:
            result.item.reasons.append(ReviewReason.SCORE_OVERRIDE)

    def _reevaluate(self, result: ReviewDecision, actor: Actor, _: float | None) -> None:
        result.item.status = ReviewStatus.PENDING
        result.requires_reevaluation = True
        self._transition(result, ApplicationStatus.UNDER_EVALUATION, actor)

    def _escalate(self, result: ReviewDecision, actor: Actor, _: float | None) -> None:
        result.item.status = ReviewStatus.ESCALATED
        result.item.assigned_to = None
        result.item.priority = Severity.CRITICAL

    def _transition(
        self, result: ReviewDecision, target: ApplicationStatus, actor: Actor
    ) -> None:
        previous = result.application.status
        if previous == target:
            return
        if not ApplicationStateMachine.can_transition(previous, target):
            logger.warning(
                "La decisión no admite transición desde el estado actual",
                from_status=previous.value,
                to_status=target.value,
            )
            return
        result.application.move_to(target)
        self.uow.applications.update(result.application)
        result.status_changed = True
        result.new_status = target.value

        self.audit.record_status_change(
            actor=actor,
            application_id=result.application.id,
            previous=previous.value,
            new=target.value,
            reason="Decisión de revisión humana",
            approved_by=actor.actor_id,
        )

    # ── Vencimiento de plazos ────────────────────────────────────────────────

    def expire_overdue(self) -> list[HumanReviewItem]:
        """Marca como vencidos los elementos fuera de plazo.

        **No los resuelve.** Se liberan, suben de prioridad y vuelven a la cola.
        Resolver automáticamente por vencimiento convertiría el plazo en una vía
        para decidir sin decidir.
        """
        expired: list[HumanReviewItem] = []
        for item in self.uow.reviews.list_queue():
            if not item.is_overdue:
                continue
            item.status = ReviewStatus.PENDING
            item.assigned_to = None
            item.priority = self._escalate_priority(item.priority)
            item.touch()
            self.uow.reviews.update(item)
            expired.append(item)

            self.audit.record(
                action="human_review.sla_expired",
                actor=Actor.system(),
                resource_type="application",
                resource_id=item.application_id,
                severity=Severity.MEDIUM,
                review_id=item.id,
                sla_hours=item.sla_hours,
            )
        if expired:
            logger.warning("Elementos de revisión fuera de plazo", count=len(expired))
        return expired

    @staticmethod
    def _escalate_priority(current: Severity) -> Severity:
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        index = order.index(current) if current in order else 1
        return order[min(index + 1, len(order) - 1)]

    # ── Consulta ─────────────────────────────────────────────────────────────

    def queue(
        self, *, status: str | None = None, assigned_to: str | None = None
    ) -> list[HumanReviewItem]:
        return self.uow.reviews.list_queue(status=status, assigned_to=assigned_to)

    def statistics(self) -> dict[str, Any]:
        items = self.uow.reviews.list_queue()
        overdue = [i for i in items if i.is_overdue]
        by_reason: dict[str, int] = {}
        for item in items:
            for reason in item.reasons:
                by_reason[reason.value] = by_reason.get(reason.value, 0) + 1
        return {
            "pending": len(items),
            "overdue": len(overdue),
            "by_priority": {
                severity.value: sum(1 for i in items if i.priority is severity)
                for severity in Severity
            },
            "by_reason": dict(sorted(by_reason.items(), key=lambda x: -x[1])),
            "counts_by_status": self.uow.reviews.counts_by_status(),
        }

    def _get(self, item_id: str) -> HumanReviewItem:
        item = self.uow.reviews.get(item_id)
        if item is None:
            raise NotFoundError(f"No existe el elemento de revisión {item_id}")
        return item


__all__ = ["DECISIONS", "ReviewDecision", "ReviewService"]
