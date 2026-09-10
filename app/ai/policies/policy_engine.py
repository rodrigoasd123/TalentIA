"""Guardrail G7 — motor de políticas.

Es la última puerta antes de que algo ocurra. Todo lo que el agente propone pasa
por aquí, y aquí se decide entre tres resultados: permitir, denegar o exigir
aprobación humana.

Dos propiedades que hacen que este módulo sea confiable:

* **No conoce al modelo.** Recibe una acción propuesta y un contexto, y aplica
  reglas escritas en Python. Nada de lo que diga un CV o un LLM puede alterar
  una regla.
* **Deniega por defecto.** Una acción sin regla asociada se deniega. Añadir una
  capacidad nueva exige escribir su política explícitamente, lo que convierte el
  olvido en un fallo cerrado en vez de un agujero abierto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.domain.enums import (
    SENSITIVE_EMAIL_KINDS,
    ActionType,
    ApplicationStatus,
    EmailTemplateKind,
    Permission,
    PolicyDecision,
    Severity,
)
from app.domain.rules.state_machine import ApplicationStateMachine


@dataclass(slots=True)
class PolicyContext:
    """Todo lo que una política necesita saber para decidir.

    Se construye en la capa de aplicación, con datos ya cargados de la base de
    datos. El motor no consulta nada por su cuenta: así es determinista y
    testeable sin infraestructura.
    """

    action: ActionType
    actor_id: str = ""
    actor_permissions: frozenset[Permission] = frozenset()
    is_human_actor: bool = False
    application_id: str = ""
    application_status: ApplicationStatus | None = None
    target_status: ApplicationStatus | None = None
    candidate_email: str = ""
    recipient: str = ""
    template_kind: EmailTemplateKind | None = None
    template_approved: bool = False
    already_sent: bool = False
    emails_sent_last_hour: int = 0
    rate_limit_per_hour: int = 50
    injection_detected: bool = False
    bias_detected: bool = False
    evidence_verification_rate: float = 1.0
    budget_exhausted: bool = False
    dry_run: bool = False
    feature_flags: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def flag(self, name: str) -> bool:
        return bool(self.feature_flags.get(name, False))


@dataclass(slots=True)
class PolicyResult:
    """Veredicto de una política, con el porqué siempre presente."""

    decision: PolicyDecision
    rule: str
    reason: str
    severity: Severity = Severity.INFO
    required_permission: Permission | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is PolicyDecision.ALLOW

    @property
    def needs_human(self) -> bool:
        return self.decision is PolicyDecision.REQUIRE_HUMAN_APPROVAL

    def to_dict(self) -> dict[str, str]:
        return {
            "decision": self.decision.value,
            "rule": self.rule,
            "reason": self.reason,
            "severity": self.severity.value,
        }

    def __str__(self) -> str:
        return f"{self.decision.value.upper()} [{self.rule}] {self.reason}"


def _allow(rule: str, reason: str) -> PolicyResult:
    return PolicyResult(PolicyDecision.ALLOW, rule, reason)


def _deny(rule: str, reason: str, severity: Severity = Severity.MEDIUM) -> PolicyResult:
    return PolicyResult(PolicyDecision.DENY, rule, reason, severity)


def _human(rule: str, reason: str) -> PolicyResult:
    return PolicyResult(PolicyDecision.REQUIRE_HUMAN_APPROVAL, rule, reason, Severity.INFO)


class PolicyEngine:
    """Evalúa acciones propuestas contra las políticas del sistema."""

    def __init__(self) -> None:
        self._rules: dict[ActionType, Callable[[PolicyContext], PolicyResult]] = {
            ActionType.READ_CANDIDATE: self._read_candidate,
            ActionType.READ_JOB: self._read_job,
            ActionType.EVALUATE_CANDIDATE: self._evaluate_candidate,
            ActionType.REQUEST_HUMAN_REVIEW: self._request_human_review,
            ActionType.PREPARE_EMAIL: self._prepare_email,
            ActionType.CHANGE_STATUS: self._change_status,
            ActionType.SEND_EMAIL: self._send_email,
        }

    def evaluate(self, context: PolicyContext) -> PolicyResult:
        """Aplica la política correspondiente a la acción.

        Las comprobaciones transversales van primero: una inyección detectada o
        un presupuesto agotado invalidan cualquier acción, sea cual sea.
        """
        transversal = self._transversal_checks(context)
        if transversal is not None:
            return transversal

        rule = self._rules.get(context.action)
        if rule is None:
            # Denegación por defecto. Una acción sin política es una acción
            # que nadie ha pensado, y por tanto no debe ejecutarse.
            return _deny(
                "default_deny",
                f"No existe política para la acción «{context.action.value}»",
                Severity.HIGH,
            )
        return rule(context)

    # ── Comprobaciones transversales ─────────────────────────────────────────

    @staticmethod
    def _transversal_checks(context: PolicyContext) -> PolicyResult | None:
        write_actions = {
            ActionType.CHANGE_STATUS, ActionType.SEND_EMAIL, ActionType.PREPARE_EMAIL,
        }
        if context.dry_run and context.action in write_actions:
            return _deny(
                "dry_run",
                "El sistema está en modo simulación: no se ejecutan acciones con efecto",
                Severity.INFO,
            )
        if context.injection_detected and context.action in write_actions:
            return _human(
                "injection_detected",
                "Se detectó contenido manipulador en el documento del candidato; "
                "toda acción con efecto queda supeditada a revisión humana",
            )
        if context.budget_exhausted and context.action is ActionType.EVALUATE_CANDIDATE:
            return _deny(
                "budget_exhausted",
                "Se agotó el presupuesto de IA asignado a esta vacante",
                Severity.MEDIUM,
            )
        return None

    # ── Políticas por acción ─────────────────────────────────────────────────

    @staticmethod
    def _read_candidate(context: PolicyContext) -> PolicyResult:
        if Permission.CANDIDATE_READ not in context.actor_permissions and context.is_human_actor:
            return _deny("read_candidate.permission", "Falta el permiso candidate:read")
        return _allow("read_candidate", "Lectura de candidato dentro del alcance autorizado")

    @staticmethod
    def _read_job(context: PolicyContext) -> PolicyResult:
        if Permission.JOB_READ not in context.actor_permissions and context.is_human_actor:
            return _deny("read_job.permission", "Falta el permiso job:read")
        return _allow("read_job", "Lectura de vacante permitida")

    @staticmethod
    def _evaluate_candidate(context: PolicyContext) -> PolicyResult:
        if context.application_status is None:
            return _deny("evaluate.no_status", "La aplicación no tiene estado conocido")
        evaluable = {
            ApplicationStatus.NEW,
            ApplicationStatus.RESUME_PROCESSED,
            ApplicationStatus.UNDER_EVALUATION,
            ApplicationStatus.HUMAN_REVIEW,
        }
        if context.application_status not in evaluable:
            return _deny(
                "evaluate.invalid_status",
                f"No se evalúa una aplicación en estado «{context.application_status.value}»",
            )
        return _allow("evaluate_candidate", "La aplicación está en un estado evaluable")

    @staticmethod
    def _request_human_review(_: PolicyContext) -> PolicyResult:
        # Pedir supervisión humana es siempre seguro: en el peor caso genera
        # trabajo, nunca un efecto irreversible.
        return _allow("request_human_review", "Solicitar revisión humana está siempre permitido")

    @staticmethod
    def _prepare_email(context: PolicyContext) -> PolicyResult:
        if not context.template_approved:
            return _deny(
                "prepare_email.template",
                "La plantilla no está aprobada; no se preparan correos con plantillas sin aprobar",
                Severity.HIGH,
            )
        if context.already_sent:
            return _deny(
                "prepare_email.duplicate",
                "Ya existe un envío para esta combinación de candidato, vacante y plantilla",
            )
        return _allow("prepare_email", "Preparación de borrador permitida")

    @staticmethod
    def _change_status(context: PolicyContext) -> PolicyResult:
        if context.application_status is None or context.target_status is None:
            return _deny("change_status.missing", "Falta el estado de origen o de destino")

        transition = ApplicationStateMachine.find(
            context.application_status, context.target_status
        )
        if transition is None:
            return _deny(
                "change_status.invalid_transition",
                f"No existe transición de «{context.application_status.value}» "
                f"a «{context.target_status.value}»",
                Severity.MEDIUM,
            )

        if not context.is_human_actor:
            if not ApplicationStateMachine.agent_may_propose(
                context.application_status, context.target_status
            ):
                return _deny(
                    "change_status.agent_forbidden",
                    f"El agente no puede proponer la transición «{transition.label}»",
                    Severity.HIGH,
                )
            if transition.requires_human:
                return _human(
                    "change_status.requires_human",
                    f"La transición «{transition.label}» requiere decisión de una persona",
                )
            # Transición automatizable: aún depende del feature flag que
            # corresponda. Los flags arrancan apagados a propósito.
            if context.target_status is ApplicationStatus.SHORTLISTED:
                if not context.flag("AI_AUTO_SHORTLIST"):
                    return _human(
                        "change_status.flag_off",
                        "La preselección automática está desactivada (AI_AUTO_SHORTLIST)",
                    )
            if context.target_status is ApplicationStatus.REJECTED:
                if not context.flag("AI_AUTO_REJECTION"):
                    return _human(
                        "change_status.flag_off",
                        "El rechazo automático está desactivado (AI_AUTO_REJECTION)",
                    )
            return _allow("change_status", f"Transición automatizable: {transition.label}")

        if transition.required_permission not in context.actor_permissions:
            return PolicyResult(
                PolicyDecision.DENY,
                "change_status.permission",
                f"Falta el permiso {transition.required_permission.value}",
                Severity.MEDIUM,
                transition.required_permission,
            )
        return _allow("change_status", f"Transición permitida: {transition.label}")

    @staticmethod
    def _send_email(context: PolicyContext) -> PolicyResult:
        """La política más estricta del sistema.

        Enviar un correo es irreversible y afecta a una persona real. Las
        comprobaciones se ordenan de la más grave a la menos: primero lo que
        indicaría un ataque, después lo que indicaría un error.
        """
        # Exfiltración: el destinatario debe ser exactamente el correo registrado
        # del candidato. Nunca un valor que venga del CV o del modelo.
        if not context.recipient:
            return _deny("send_email.no_recipient", "No hay destinatario definido", Severity.HIGH)
        if not context.candidate_email:
            return _deny(
                "send_email.no_candidate_email",
                "El candidato no tiene un correo registrado",
                Severity.HIGH,
            )
        if context.recipient.strip().lower() != context.candidate_email.strip().lower():
            return _deny(
                "send_email.recipient_mismatch",
                "El destinatario no coincide con el correo registrado del candidato. "
                "Posible intento de exfiltración",
                Severity.CRITICAL,
            )

        if not context.template_approved:
            return _deny("send_email.template", "La plantilla no está aprobada", Severity.HIGH)

        if context.already_sent:
            return _deny(
                "send_email.duplicate",
                "Ese correo ya fue enviado; el duplicado se descarta",
                Severity.LOW,
            )

        if context.emails_sent_last_hour >= context.rate_limit_per_hour:
            return _deny(
                "send_email.rate_limit",
                f"Se alcanzó el límite de {context.rate_limit_per_hour} envíos por hora",
                Severity.MEDIUM,
            )

        if context.application_status is None:
            return _deny("send_email.no_status", "La aplicación no tiene estado conocido")

        # Categorías sensibles: siempre pasan por una persona, con independencia
        # de flags y de configuración de la vacante.
        if context.template_kind in SENSITIVE_EMAIL_KINDS:
            if not context.is_human_actor:
                return _human(
                    "send_email.sensitive",
                    f"La comunicación de tipo «{context.template_kind.value}» requiere "
                    "aprobación humana explícita",
                )
            if Permission.EMAIL_APPROVE not in context.actor_permissions:
                return PolicyResult(
                    PolicyDecision.DENY,
                    "send_email.approval_permission",
                    "Falta el permiso email:approve para autorizar una comunicación sensible",
                    Severity.MEDIUM,
                    Permission.EMAIL_APPROVE,
                )

        if not context.is_human_actor and not context.flag("AUTO_EMAIL"):
            return _human(
                "send_email.flag_off",
                "El envío automático está desactivado (AUTO_EMAIL)",
            )

        if context.is_human_actor and Permission.EMAIL_SEND not in context.actor_permissions:
            return PolicyResult(
                PolicyDecision.DENY,
                "send_email.permission",
                "Falta el permiso email:send",
                Severity.MEDIUM,
                Permission.EMAIL_SEND,
            )

        return _allow("send_email", "Envío autorizado: destinatario, plantilla y estado válidos")


# ── Catálogo de herramientas del agente ──────────────────────────────────────
# Registro explícito de lo que el agente puede invocar. Lo que no está aquí, no
# existe para él. La lista de lo prohibido se documenta para dejar constancia de
# que la ausencia es deliberada, no un olvido.

ALLOWED_AGENT_TOOLS: frozenset[str] = frozenset(
    {
        "get_candidate",
        "get_job",
        "get_job_requirements",
        "get_application",
        "evaluate_candidate",
        "request_human_review",
        "prepare_email",
    }
)

FORBIDDEN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "execute_sql", "raw_query", "delete_record", "drop_table",
        "read_environment", "get_secret", "filesystem_read", "filesystem_write",
        "shell_exec", "subprocess", "eval", "exec", "arbitrary_python",
        "http_request", "fetch_url", "send_arbitrary_email", "modify_policy",
        "modify_prompt", "grant_permission", "read_audit_log",
    }
)


def is_tool_allowed(tool_name: str) -> bool:
    """¿Puede el agente invocar esta herramienta?

    Se comprueba contra la lista de permitidos, no contra la de prohibidos: una
    herramienta nueva y desconocida se rechaza por defecto.
    """
    return tool_name in ALLOWED_AGENT_TOOLS


__all__ = [
    "ALLOWED_AGENT_TOOLS", "FORBIDDEN_CAPABILITIES", "PolicyContext",
    "PolicyEngine", "PolicyResult", "is_tool_allowed",
]
