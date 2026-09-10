"""Servicio de auditoría.

Centraliza la emisión de eventos para que registrar sea trivial y omitir sea
difícil. Si cada caso de uso tuviera que construir un ``AuditEvent`` a mano, la
auditoría acabaría siendo desigual: completa donde alguien se acordó y vacía en
el resto, que es justo donde luego hace falta.

Los eventos son de solo inserción y se encadenan por hash en el repositorio.
Aquí solo se decide **qué** se registra y con qué severidad.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger, get_trace_id
from app.domain.entities import AuditEvent
from app.domain.enums import ActorType, Severity
from app.domain.ports import AuditRepository

logger = get_logger(__name__)


class Actor:
    """Quién realiza una acción. Puede ser una persona, el agente o el sistema."""

    def __init__(
        self,
        actor_id: str = "system",
        actor_type: ActorType = ActorType.SYSTEM,
        *,
        ip_address: str = "",
        user_agent: str = "",
    ) -> None:
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.ip_address = ip_address
        self.user_agent = user_agent

    @classmethod
    def system(cls) -> Actor:
        return cls("system", ActorType.SYSTEM)

    @classmethod
    def agent(cls, version: str = "VERA") -> Actor:
        return cls(version, ActorType.AI_AGENT)

    @classmethod
    def user(cls, user_id: str, *, ip: str = "", user_agent: str = "") -> Actor:
        return cls(user_id, ActorType.USER, ip_address=ip, user_agent=user_agent)


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def record(
        self,
        *,
        action: str,
        actor: Actor,
        resource_type: str = "",
        resource_id: str = "",
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        severity: Severity = Severity.INFO,
        policy_result: str = "",
        human_approval_by: str | None = None,
        agent_version: str = "",
        prompt_version: str = "",
        model: str = "",
        **metadata: Any,
    ) -> AuditEvent:
        """Registra un evento. Nunca falla en silencio.

        Si la auditoría no puede escribirse, la operación completa debe fallar:
        una acción sin registro es peor que una acción no realizada, porque nadie
        sabrá que ocurrió.
        """
        event = AuditEvent(
            trace_id=get_trace_id(),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_state=previous_state,
            new_state=new_state,
            severity=severity,
            policy_result=policy_result,
            human_approval_by=human_approval_by,
            agent_version=agent_version,
            prompt_version=prompt_version,
            model=model,
            metadata=metadata,
        )
        stored = self.repository.append(event)

        if severity in {Severity.HIGH, Severity.CRITICAL}:
            logger.security(
                "Evento de auditoría de severidad alta",
                action=action,
                resource_id=resource_id,
                actor=actor.actor_id,
                severity=severity.value,
            )
        return stored

    # ── Atajos para las acciones más frecuentes ──────────────────────────────

    def record_status_change(
        self,
        *,
        actor: Actor,
        application_id: str,
        previous: str,
        new: str,
        reason: str = "",
        policy_result: str = "",
        approved_by: str | None = None,
    ) -> AuditEvent:
        return self.record(
            action="application.status_changed",
            actor=actor,
            resource_type="application",
            resource_id=application_id,
            previous_state={"status": previous},
            new_state={"status": new},
            policy_result=policy_result,
            human_approval_by=approved_by,
            reason=reason,
        )

    def record_evaluation(
        self,
        *,
        actor: Actor,
        application_id: str,
        evaluation_id: str,
        score: float | None,
        recommendation: str,
        model: str,
        agent_version: str,
        prompt_versions: dict[str, str],
        requires_review: bool,
        review_reasons: list[str],
        cost_usd: float,
    ) -> AuditEvent:
        """Registra una evaluación con todo lo necesario para reproducirla.

        Sin modelo, versión de agente y versiones de prompt, una decisión pasada
        no puede explicarse: solo se sabría el número, no cómo se obtuvo.
        """
        return self.record(
            action="evaluation.completed",
            actor=actor,
            resource_type="application",
            resource_id=application_id,
            new_state={
                "evaluation_id": evaluation_id,
                "score": score,
                "recommendation": recommendation,
                "requires_human_review": requires_review,
            },
            agent_version=agent_version,
            prompt_version=",".join(f"{k}@{v}" for k, v in sorted(prompt_versions.items())),
            model=model,
            review_reasons=review_reasons,
            cost_usd=cost_usd,
        )

    def record_security_incident(
        self,
        *,
        actor: Actor,
        resource_id: str,
        incident: str,
        severity: Severity = Severity.HIGH,
        **details: Any,
    ) -> AuditEvent:
        return self.record(
            action=f"security.{incident}",
            actor=actor,
            resource_type="application",
            resource_id=resource_id,
            severity=severity,
            **details,
        )

    def record_human_decision(
        self,
        *,
        actor: Actor,
        application_id: str,
        review_id: str,
        decision: str,
        justification: str,
        previous_score: float | None = None,
        new_score: float | None = None,
    ) -> AuditEvent:
        """Registra una decisión humana sobre una propuesta de la IA.

        La justificación es obligatoria en el caso de uso, no aquí; este método
        solo la persiste. Es el registro que permite responder «¿quién cambió
        esto y por qué?».
        """
        return self.record(
            action="human_review.decided",
            actor=actor,
            resource_type="application",
            resource_id=application_id,
            previous_state={"score": previous_score} if previous_score is not None else None,
            new_state={"decision": decision, "score": new_score},
            human_approval_by=actor.actor_id,
            review_id=review_id,
            justification=justification,
        )

    def record_access(
        self, *, actor: Actor, resource_type: str, resource_id: str, purpose: str = ""
    ) -> AuditEvent:
        """Registra el acceso a datos personales.

        Es un requisito de cumplimiento: hay que poder responder quién consultó
        los datos de un candidato y cuándo.
        """
        return self.record(
            action=f"{resource_type}.accessed",
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            purpose=purpose,
        )


__all__ = ["Actor", "AuditService"]
