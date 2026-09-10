"""Máquina de estados de una candidatura.

Las transiciones válidas se declaran como datos, no como cadenas de ``if``. Eso
permite dos cosas que un condicional disperso no permite: dibujar el grafo de
estados a partir del propio código y escribir un test exhaustivo que recorra
todas las combinaciones posibles.

Regla no negociable: ninguna transición hacia un estado terminal puede
revertirse. Un candidato rechazado no vuelve a "en evaluación" sin crear una
candidatura nueva, porque de lo contrario el historial deja de ser fiable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import InvalidStateTransition
from app.domain.enums import TERMINAL_STATUSES, ApplicationStatus, Permission

S = ApplicationStatus


@dataclass(frozen=True, slots=True)
class Transition:
    """Arista del grafo de estados con sus condiciones."""

    source: ApplicationStatus
    target: ApplicationStatus
    label: str
    required_permission: Permission = Permission.APPLICATION_TRANSITION
    requires_human: bool = False
    allowed_for_agent_proposal: bool = True


#: Grafo de transiciones permitidas. Es la fuente de verdad del ciclo de vida.
TRANSITIONS: tuple[Transition, ...] = (
    Transition(S.NEW, S.RESUME_PROCESSED, "CV procesado"),
    Transition(S.NEW, S.REJECTED, "Descarte temprano", requires_human=True),
    Transition(S.NEW, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.RESUME_PROCESSED, S.UNDER_EVALUATION, "Inicio de evaluación"),
    Transition(S.RESUME_PROCESSED, S.HUMAN_REVIEW, "Derivado a revisión"),
    Transition(S.RESUME_PROCESSED, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.UNDER_EVALUATION, S.SHORTLISTED, "Preseleccionado"),
    Transition(S.UNDER_EVALUATION, S.HUMAN_REVIEW, "Derivado a revisión"),
    Transition(S.UNDER_EVALUATION, S.REJECTED, "Rechazado tras evaluación", requires_human=True),
    Transition(S.UNDER_EVALUATION, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.HUMAN_REVIEW, S.SHORTLISTED, "Aprobado en revisión",
               required_permission=Permission.REVIEW_DECIDE, requires_human=True,
               allowed_for_agent_proposal=False),
    Transition(S.HUMAN_REVIEW, S.REJECTED, "Rechazado en revisión",
               required_permission=Permission.REVIEW_DECIDE, requires_human=True,
               allowed_for_agent_proposal=False),
    Transition(S.HUMAN_REVIEW, S.UNDER_EVALUATION, "Reevaluación solicitada",
               required_permission=Permission.REVIEW_DECIDE, requires_human=True,
               allowed_for_agent_proposal=False),
    Transition(S.HUMAN_REVIEW, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.SHORTLISTED, S.APPROVED_FOR_INTERVIEW, "Aprobado para entrevista",
               requires_human=True, allowed_for_agent_proposal=False),
    Transition(S.SHORTLISTED, S.HUMAN_REVIEW, "Derivado a revisión"),
    Transition(S.SHORTLISTED, S.REJECTED, "Rechazado", requires_human=True),
    Transition(S.SHORTLISTED, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.APPROVED_FOR_INTERVIEW, S.INTERVIEW_SCHEDULED, "Entrevista agendada",
               required_permission=Permission.INTERVIEW_MANAGE),
    Transition(S.APPROVED_FOR_INTERVIEW, S.REJECTED, "Rechazado", requires_human=True),
    Transition(S.APPROVED_FOR_INTERVIEW, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.INTERVIEW_SCHEDULED, S.INTERVIEWED, "Entrevista realizada",
               required_permission=Permission.INTERVIEW_MANAGE),
    Transition(S.INTERVIEW_SCHEDULED, S.REJECTED, "No asistió o rechazado", requires_human=True),
    Transition(S.INTERVIEW_SCHEDULED, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.INTERVIEWED, S.APPROVED, "Aprobado", requires_human=True,
               allowed_for_agent_proposal=False),
    Transition(S.INTERVIEWED, S.INTERVIEW_SCHEDULED, "Nueva ronda de entrevista",
               required_permission=Permission.INTERVIEW_MANAGE),
    Transition(S.INTERVIEWED, S.REJECTED, "Rechazado tras entrevista", requires_human=True),
    Transition(S.INTERVIEWED, S.WITHDRAWN, "Retirada del candidato"),

    Transition(S.APPROVED, S.HIRED, "Contratado", requires_human=True,
               allowed_for_agent_proposal=False),
    Transition(S.APPROVED, S.REJECTED, "Oferta no aceptada", requires_human=True),
    Transition(S.APPROVED, S.WITHDRAWN, "Retirada del candidato"),
)

_INDEX: dict[tuple[ApplicationStatus, ApplicationStatus], Transition] = {
    (t.source, t.target): t for t in TRANSITIONS
}


class ApplicationStateMachine:
    """Valida y describe los movimientos posibles de una candidatura."""

    @staticmethod
    def allowed_targets(source: ApplicationStatus) -> list[ApplicationStatus]:
        return [t.target for t in TRANSITIONS if t.source is source]

    @staticmethod
    def find(source: ApplicationStatus, target: ApplicationStatus) -> Transition | None:
        return _INDEX.get((source, target))

    @staticmethod
    def is_terminal(status: ApplicationStatus) -> bool:
        return status in TERMINAL_STATUSES

    @classmethod
    def can_transition(cls, source: ApplicationStatus, target: ApplicationStatus) -> bool:
        return cls.find(source, target) is not None

    @classmethod
    def validate(
        cls,
        source: ApplicationStatus,
        target: ApplicationStatus,
        *,
        actor_permissions: frozenset[Permission] | None = None,
        is_human_actor: bool = True,
    ) -> Transition:
        """Comprueba una transición y devuelve su definición.

        Lanza ``InvalidStateTransition`` en lugar de devolver ``False`` porque el
        llamante nunca debe poder ignorar el resultado por descuido.
        """
        if source is target:
            raise InvalidStateTransition(
                f"El estado ya es {source.value}; no hay cambio que aplicar",
                source=source.value, target=target.value,
            )
        if cls.is_terminal(source):
            raise InvalidStateTransition(
                f"{source.value} es un estado terminal y no admite transiciones",
                source=source.value, target=target.value,
            )
        transition = cls.find(source, target)
        if transition is None:
            raise InvalidStateTransition(
                f"No existe transición de {source.value} a {target.value}",
                source=source.value,
                target=target.value,
                allowed=[s.value for s in cls.allowed_targets(source)],
            )
        if transition.requires_human and not is_human_actor:
            raise InvalidStateTransition(
                f"La transición '{transition.label}' requiere una persona; "
                "el agente solo puede proponerla",
                source=source.value, target=target.value,
            )
        if actor_permissions is not None and transition.required_permission not in actor_permissions:
            raise InvalidStateTransition(
                f"Falta el permiso {transition.required_permission.value}",
                source=source.value, target=target.value,
            )
        return transition

    @classmethod
    def agent_may_propose(cls, source: ApplicationStatus, target: ApplicationStatus) -> bool:
        """¿Puede el agente siquiera *proponer* esta transición?

        Distinto de ejecutarla: proponer una transición prohibida ya es señal de
        que algo va mal y merece quedar auditado.
        """
        transition = cls.find(source, target)
        return transition is not None and transition.allowed_for_agent_proposal

    @staticmethod
    def to_mermaid() -> str:
        """Genera el diagrama del ciclo de vida a partir del propio código.

        Documentación que no puede quedar desactualizada, porque se deriva de la
        misma estructura que el sistema usa para decidir.
        """
        lines = ["stateDiagram-v2", "    [*] --> new"]
        for t in TRANSITIONS:
            mark = " 👤" if t.requires_human else ""
            lines.append(f"    {t.source.value} --> {t.target.value}: {t.label}{mark}")
        for terminal in sorted(TERMINAL_STATUSES, key=lambda s: s.value):
            lines.append(f"    {terminal.value} --> [*]")
        return "\n".join(lines)


__all__ = ["TRANSITIONS", "ApplicationStateMachine", "Transition"]
