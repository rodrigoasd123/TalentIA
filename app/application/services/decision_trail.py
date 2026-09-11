"""Traza de decisión: por qué el sistema hizo lo que hizo con una candidatura.

Es la funcionalidad que diferencia a TalentIA de un ATS sin trazabilidad. Cuando un
candidato reclame, o llegue una auditoría, o simplemente alguien del equipo
pregunte «¿por qué se descartó a esta persona?», la respuesta se genera en un
clic y contiene todo lo necesario para defenderla:

* Qué filtros se aplicaron y con qué resultado.
* Qué evidencia sostiene cada puntuación, y si esa evidencia se verificó.
* Qué versión del agente, del modelo y de los prompts intervino.
* Quién aprobó qué, cuándo y con qué justificación.
* Qué controles de seguridad se activaron.

El documento se construye **solo desde la auditoría y las entidades
persistidas**, nunca reconstruyendo nada a posteriori. Si un dato no se registró
en su momento, aquí aparece como ausente en lugar de inventado.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.application.unit_of_work import UnitOfWork
from app.core.exceptions import ApplicationNotFound
from app.domain.entities import AuditEvent, Evaluation
from app.domain.enums import ActorType

#: Acciones que se destacan en el resumen ejecutivo del documento.
_KEY_ACTIONS = {
    "application.created": "Candidatura registrada",
    "application.status_changed": "Cambio de estado",
    "evaluation.completed": "Evaluación automática",
    "human_review.enqueued": "Derivado a revisión humana",
    "human_review.claimed": "Revisor asignado",
    "human_review.decided": "Decisión humana",
    "human_review.sla_expired": "Plazo de revisión vencido",
    "email.sent": "Comunicación enviada",
    "security.prompt_injection_detected": "Intento de manipulación detectado",
    "security.bias_detected": "Posible sesgo detectado",
    "security.evidence_unverifiable": "Evidencia no verificable",
}


@dataclass(slots=True)
class TrailStep:
    """Un paso del historial, ya traducido a lenguaje comprensible."""

    timestamp: datetime
    actor: str
    actor_type: str
    action: str
    description: str
    detail: str = ""
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "actor_type": self.actor_type,
            "action": self.action,
            "description": self.description,
            "detail": self.detail,
            "severity": self.severity,
        }


@dataclass(slots=True)
class DecisionTrail:
    """Documento completo de trazabilidad de una candidatura."""

    application_id: str
    candidate_name: str
    candidate_email: str
    job_code: str
    job_title: str
    current_status: str
    final_score: float | None
    generated_at: datetime
    steps: list[TrailStep] = field(default_factory=list)
    evaluations: list[dict[str, Any]] = field(default_factory=list)
    human_decisions: list[dict[str, Any]] = field(default_factory=list)
    security_events: list[dict[str, Any]] = field(default_factory=list)
    chain_verified: bool = True
    chain_broken_at: str | None = None

    @property
    def was_reviewed_by_human(self) -> bool:
        return bool(self.human_decisions)

    @property
    def summary_line(self) -> str:
        estado = f"estado actual «{self.current_status}»"
        puntuacion = (
            f"puntuación final {self.final_score:.1f}"
            if self.final_score is not None
            else "sin puntuación registrada"
        )
        supervision = (
            "con revisión humana documentada"
            if self.was_reviewed_by_human
            else "sin decisión humana registrada"
        )
        return f"{self.candidate_name} — {self.job_code}: {estado}, {puntuacion}, {supervision}."

    def to_dict(self) -> dict[str, Any]:
        return {
            "application_id": self.application_id,
            "candidate": {"name": self.candidate_name, "email": self.candidate_email},
            "job": {"code": self.job_code, "title": self.job_title},
            "current_status": self.current_status,
            "final_score": self.final_score,
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary_line,
            "integrity": {
                "audit_chain_verified": self.chain_verified,
                "broken_at_event": self.chain_broken_at,
            },
            "steps": [s.to_dict() for s in self.steps],
            "evaluations": self.evaluations,
            "human_decisions": self.human_decisions,
            "security_events": self.security_events,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)

    def to_csv(self) -> str:
        """Historial en CSV, para quien prefiera abrirlo en una hoja de cálculo."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(["Fecha", "Actor", "Tipo", "Acción", "Descripción", "Detalle", "Severidad"])
        for step in self.steps:
            writer.writerow([
                step.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                step.actor, step.actor_type, step.action,
                step.description, step.detail, step.severity,
            ])
        return buffer.getvalue()

    def to_markdown(self) -> str:
        """Informe legible, pensado para adjuntar a una reclamación o auditoría."""
        lines = [
            f"# Traza de decisión — {self.candidate_name}",
            "",
            f"**Candidatura:** `{self.application_id}`  ",
            f"**Vacante:** {self.job_code} — {self.job_title}  ",
            f"**Estado actual:** {self.current_status}  ",
            f"**Puntuación final:** "
            + (f"{self.final_score:.1f}/100" if self.final_score is not None else "no registrada")
            + "  ",
            f"**Documento generado:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
            "> " + self.summary_line,
            "",
            "## Integridad del registro",
            "",
        ]
        if self.chain_verified:
            lines.append(
                "La cadena de auditoría se ha verificado y es íntegra: ningún evento "
                "ha sido modificado ni eliminado desde su registro."
            )
        else:
            lines.append(
                f"⚠️ **La cadena de auditoría presenta una inconsistencia** a partir del "
                f"evento `{self.chain_broken_at}`. El historial posterior a ese punto "
                "no puede considerarse fiable."
            )

        lines += ["", "## Historial cronológico", "",
                  "| Fecha | Actor | Acción | Detalle |", "|---|---|---|---|"]
        for step in self.steps:
            marca = "🔒 " if step.severity in {"high", "critical"} else ""
            lines.append(
                f"| {step.timestamp.strftime('%Y-%m-%d %H:%M')} | {step.actor_type} | "
                f"{marca}{step.description} | {step.detail or '—'} |"
            )

        if self.evaluations:
            lines += ["", "## Evaluaciones realizadas", ""]
            for index, evaluation in enumerate(self.evaluations, start=1):
                lines += [
                    f"### Evaluación {index}"
                    + (" (vigente)" if evaluation["is_current"] else " (sustituida)"),
                    "",
                    f"- **Puntuación:** {evaluation['score']}",
                    f"- **Recomendación:** {evaluation['recommendation']}",
                    f"- **Filtros obligatorios:** "
                    + ("superados" if evaluation["passed_hard_filters"] else "no superados"),
                    f"- **Evidencia verificada:** {evaluation['evidence_rate']}",
                    f"- **Modelo:** `{evaluation['model']}`",
                    f"- **Versión del agente:** `{evaluation['agent_version']}`",
                    f"- **Prompts:** {evaluation['prompt_versions']}",
                    "",
                ]
                if evaluation["failed_filters"]:
                    lines.append("**Requisitos no cumplidos:**")
                    lines += [f"- {f}" for f in evaluation["failed_filters"]]
                    lines.append("")
                if evaluation["evidence"]:
                    lines.append("**Evidencia citada del CV:**")
                    for span in evaluation["evidence"]:
                        marca = "✅" if span["verified"] else "❌"
                        lines.append(f"- {marca} _«{span['quote']}»_ ({span['dimension']})")
                    lines.append("")

        if self.human_decisions:
            lines += ["", "## Decisiones humanas", ""]
            for decision in self.human_decisions:
                lines += [
                    f"- **{decision['timestamp']}** — {decision['decision']} "
                    f"por `{decision['actor']}`",
                    f"  - Justificación: {decision['justification']}",
                ]
        else:
            lines += [
                "", "## Decisiones humanas", "",
                "No consta ninguna decisión humana sobre esta candidatura.",
            ]

        if self.security_events:
            lines += ["", "## Controles de seguridad activados", ""]
            for event in self.security_events:
                lines.append(
                    f"- **{event['timestamp']}** — {event['description']} "
                    f"(severidad {event['severity']})"
                )

        lines += [
            "", "---", "",
            "Este documento se ha generado automáticamente a partir del registro de "
            "auditoría del sistema, que es de solo inserción y está encadenado por "
            "hash. No incluye información reconstruida ni inferida.",
        ]
        return "\n".join(lines)


class DecisionTrailService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def build(self, application_id: str) -> DecisionTrail:
        application = self.uow.applications.get(application_id)
        if application is None:
            raise ApplicationNotFound(f"No existe la candidatura {application_id}")

        candidate = self.uow.candidates.get(application.candidate_id)
        job = self.uow.jobs.get(application.job_id)
        events = self.uow.audit.decision_trail(application_id)
        evaluations = self.uow.evaluations.list_for_application(application_id)
        chain_ok, broken = self.uow.audit.verify_chain()

        trail = DecisionTrail(
            application_id=application_id,
            candidate_name=candidate.full_name if candidate else "(candidato eliminado)",
            candidate_email=candidate.email.masked() if candidate and candidate.email else "",
            job_code=job.code if job else "",
            job_title=job.title if job else "",
            current_status=application.status.value,
            final_score=application.final_score,
            generated_at=datetime.now(tz=events[0].timestamp.tzinfo) if events else datetime.now(),
            chain_verified=chain_ok,
            chain_broken_at=broken,
        )

        for event in events:
            trail.steps.append(self._to_step(event))
            if event.action == "human_review.decided":
                trail.human_decisions.append(
                    {
                        "timestamp": event.timestamp.strftime("%Y-%m-%d %H:%M"),
                        "actor": event.actor_id,
                        "decision": (event.new_state or {}).get("decision", ""),
                        "justification": event.metadata.get("justification", ""),
                        "previous_score": (event.previous_state or {}).get("score"),
                        "new_score": (event.new_state or {}).get("score"),
                    }
                )
            if event.action.startswith("security."):
                trail.security_events.append(
                    {
                        "timestamp": event.timestamp.strftime("%Y-%m-%d %H:%M"),
                        "description": _KEY_ACTIONS.get(event.action, event.action),
                        "severity": event.severity.value,
                        "detail": event.metadata,
                    }
                )

        for evaluation in evaluations:
            trail.evaluations.append(self._evaluation_summary(evaluation))

        return trail

    @staticmethod
    def _to_step(event: AuditEvent) -> TrailStep:
        description = _KEY_ACTIONS.get(event.action, event.action)
        detail = ""

        if event.action == "application.status_changed":
            previous = (event.previous_state or {}).get("status", "?")
            new = (event.new_state or {}).get("status", "?")
            detail = f"{previous} → {new}"
            if reason := event.metadata.get("reason"):
                detail += f" · {reason}"
        elif event.action == "evaluation.completed":
            state = event.new_state or {}
            detail = (
                f"puntuación {state.get('score')}, "
                f"recomendación «{state.get('recommendation')}»"
            )
            if event.model:
                detail += f" · modelo {event.model}"
        elif event.action == "human_review.decided":
            detail = event.metadata.get("justification", "")[:160]
        elif event.action == "human_review.enqueued":
            reasons = (event.new_state or {}).get("reasons", [])
            detail = "motivos: " + ", ".join(reasons)

        actor = {
            ActorType.AI_AGENT: "TalentIA",
            ActorType.SYSTEM: "sistema",
        }.get(event.actor_type, event.actor_id)

        return TrailStep(
            timestamp=event.timestamp,
            actor=actor,
            actor_type=event.actor_type.value,
            action=event.action,
            description=description,
            detail=detail,
            severity=event.severity.value,
        )

    @staticmethod
    def _evaluation_summary(evaluation: Evaluation) -> dict[str, Any]:
        return {
            "id": evaluation.id,
            "is_current": evaluation.is_current,
            "created_at": evaluation.created_at.strftime("%Y-%m-%d %H:%M"),
            "score": f"{float(evaluation.total_score):.1f}" if evaluation.total_score else "—",
            "recommendation": evaluation.recommendation.value,
            "passed_hard_filters": evaluation.passed_hard_filters,
            "failed_filters": [
                f.filter_label for f in evaluation.hard_filter_results if not f.passed
            ],
            "evidence_rate": f"{evaluation.evidence_verification_rate:.0%}",
            "model": evaluation.model_name or "—",
            "agent_version": evaluation.agent_version or "—",
            "prompt_versions": ", ".join(
                f"{k}@{v}" for k, v in sorted(evaluation.prompt_versions.items())
            ) or "—",
            "review_reasons": [r.value for r in evaluation.review_reasons],
            "evidence": [
                {
                    "quote": span.quote,
                    "dimension": span.dimension.value,
                    "verified": span.verified,
                }
                for span in evaluation.all_evidence
            ],
            "cost_usd": evaluation.cost_usd,
        }


__all__ = ["DecisionTrail", "DecisionTrailService", "TrailStep"]
