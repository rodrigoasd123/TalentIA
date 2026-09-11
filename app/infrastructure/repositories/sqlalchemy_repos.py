"""Implementaciones SQLAlchemy de los puertos de repositorio.

Todas comparten la misma forma: reciben una sesión, traducen con los mapeadores y
devuelven entidades de dominio. Ningún repositorio confirma la transacción — de
eso se encarga la unidad de trabajo, para que un caso de uso completo sea atómico.

**El repositorio de auditoría es distinto** y merece leerse aparte: solo permite
insertar, encadena cada evento con el hash del anterior y sabe verificar si la
cadena fue alterada.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateApplication
from app.core.logging import get_logger
from app.domain.entities import (
    Application,
    AuditEvent,
    Candidate,
    EmailMessage,
    EmailTemplate,
    Evaluation,
    HumanReviewItem,
    Job,
    ResumeDocument,
    User,
    WorkflowRun,
)
from app.domain.enums import ApplicationStatus, EmailStatus, ReviewStatus
from app.infrastructure.database.models import (
    ApplicationModel,
    AuditEventModel,
    CandidateModel,
    EmailModel,
    EmailTemplateModel,
    EvaluationModel,
    HumanReviewModel,
    JobModel,
    ResumeModel,
    UserModel,
    WorkflowRunModel,
)
from app.infrastructure.repositories import mappers as m

logger = get_logger(__name__)

#: Valor con el que arranca la cadena de hash. Que sea constante y conocido
#: permite verificar la cadena desde el primer evento sin excepciones.
GENESIS_HASH = "0" * 64


class BaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session


# ── Usuarios ─────────────────────────────────────────────────────────────────


class SqlUserRepository(BaseRepository):
    def add(self, user: User) -> User:
        self.session.add(m.user_to_model(user))
        self.session.flush()
        return user

    def get(self, user_id: str) -> User | None:
        model = self.session.get(UserModel, user_id)
        return m.user_to_entity(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        model = self.session.scalar(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )
        return m.user_to_entity(model) if model else None

    def update(self, user: User) -> User:
        model = self.session.get(UserModel, user.id)
        if model is None:
            raise ValueError(f"Usuario no encontrado: {user.id}")
        m.apply_user(model, user)
        self.session.flush()
        return user

    def list(self) -> list[User]:
        return [m.user_to_entity(x) for x in self.session.scalars(select(UserModel))]


# ── Vacantes ─────────────────────────────────────────────────────────────────


class SqlJobRepository(BaseRepository):
    def add(self, job: Job) -> Job:
        self.session.add(m.job_to_model(job))
        self.session.flush()
        return job

    def get(self, job_id: str) -> Job | None:
        model = self.session.get(JobModel, job_id)
        return m.job_to_entity(model) if model else None

    def get_by_code(self, code: str) -> Job | None:
        model = self.session.scalar(select(JobModel).where(JobModel.code == code))
        return m.job_to_entity(model) if model else None

    def update(self, job: Job) -> Job:
        model = self.session.get(JobModel, job.id)
        if model is None:
            raise ValueError(f"Vacante no encontrada: {job.id}")
        m.apply_job(model, job)
        self.session.flush()
        return job

    def list(
        self, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> list[Job]:
        stmt = select(JobModel).order_by(JobModel.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(JobModel.status == status)
        if cursor:
            stmt = stmt.where(JobModel.id > cursor)
        return [m.job_to_entity(x) for x in self.session.scalars(stmt)]


# ── Candidatos ───────────────────────────────────────────────────────────────


class SqlCandidateRepository(BaseRepository):
    def add(self, candidate: Candidate) -> Candidate:
        self.session.add(m.candidate_to_model(candidate))
        self.session.flush()
        return candidate

    def get(self, candidate_id: str) -> Candidate | None:
        model = self.session.get(CandidateModel, candidate_id)
        return m.candidate_to_entity(model) if model else None

    def get_by_email(self, email: str) -> Candidate | None:
        model = self.session.scalar(
            select(CandidateModel).where(CandidateModel.email == email.strip().lower())
        )
        return m.candidate_to_entity(model) if model else None

    def find_by_strong_identifiers(
        self, *, email: str = "", phone: str = "", national_id: str = ""
    ) -> list[Candidate]:
        from sqlalchemy import or_

        conditions = []
        if email:
            conditions.append(CandidateModel.email == email.strip().lower())
        digits = _digits(phone)
        if national_id:
            conditions.append(CandidateModel.national_id == national_id.strip())
        if not conditions and len(digits) < 8:
            return []
        matches: dict[str, CandidateModel] = {}
        if conditions:
            for row in self.session.scalars(
                select(CandidateModel).where(or_(*conditions))
            ):
                matches[row.id] = row
        if len(digits) >= 8:
            phone_suffix = digits[-8:]
            for row in self.session.scalars(select(CandidateModel)):
                if _digits(row.phone).endswith(phone_suffix):
                    matches[row.id] = row
        return [m.candidate_to_entity(row) for row in matches.values()]

    def find_by_normalized_name(self, name: str) -> list[Candidate]:
        normalized = " ".join(name.lower().split())
        rows = self.session.scalars(select(CandidateModel)).all()
        return [
            m.candidate_to_entity(row)
            for row in rows
            if " ".join(row.full_name.lower().split()) == normalized
        ]

    def update(self, candidate: Candidate) -> Candidate:
        model = self.session.get(CandidateModel, candidate.id)
        if model is None:
            raise ValueError(f"Candidato no encontrado: {candidate.id}")
        m.apply_candidate(model, candidate)
        self.session.flush()
        return candidate

    def list(self, *, limit: int = 50, cursor: str | None = None) -> list[Candidate]:
        stmt = select(CandidateModel).order_by(CandidateModel.created_at.desc()).limit(limit)
        if cursor:
            stmt = stmt.where(CandidateModel.id > cursor)
        return [m.candidate_to_entity(x) for x in self.session.scalars(stmt)]

    def find_potential_duplicates(self, candidate: Candidate) -> list[Candidate]:
        """Busca coincidencias por correo, teléfono o documento.

        Devuelve candidatos, **no fusiona nada**. Fusionar automáticamente dos
        personas por una coincidencia de teléfono es un error difícil de deshacer:
        la decisión es de una persona.
        """
        conditions = []
        if candidate.email:
            conditions.append(CandidateModel.email == str(candidate.email))
        if candidate.phone:
            normalized = _digits(candidate.phone)
            if len(normalized) >= 8:
                conditions.append(CandidateModel.phone.contains(normalized[-8:]))
        if candidate.national_id:
            conditions.append(CandidateModel.national_id == candidate.national_id)

        from sqlalchemy import or_

        if not conditions:
            return []
        stmt = select(CandidateModel).where(
            or_(*conditions), CandidateModel.id != candidate.id
        )
        return [m.candidate_to_entity(x) for x in self.session.scalars(stmt)]


def _digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


# ── Documentos ───────────────────────────────────────────────────────────────


class SqlResumeRepository(BaseRepository):
    def add(self, resume: ResumeDocument) -> ResumeDocument:
        self.session.add(m.resume_to_model(resume))
        self.session.flush()
        return resume

    def get(self, resume_id: str) -> ResumeDocument | None:
        model = self.session.get(ResumeModel, resume_id)
        return m.resume_to_entity(model) if model else None

    def get_by_hash(self, content_hash: str) -> ResumeDocument | None:
        model = self.session.scalar(
            select(ResumeModel).where(ResumeModel.content_hash == content_hash)
        )
        return m.resume_to_entity(model) if model else None

    def update(self, resume: ResumeDocument) -> ResumeDocument:
        model = self.session.get(ResumeModel, resume.id)
        if model is None:
            raise ValueError(f"Documento no encontrado: {resume.id}")
        m.apply_resume(model, resume)
        self.session.flush()
        return resume

    def list_for_candidate(self, candidate_id: str) -> list[ResumeDocument]:
        stmt = (
            select(ResumeModel)
            .where(ResumeModel.candidate_id == candidate_id)
            .order_by(ResumeModel.resume_version.desc())
        )
        return [m.resume_to_entity(x) for x in self.session.scalars(stmt)]

    def next_version(self, candidate_id: str) -> int:
        current = self.session.scalar(
            select(func.max(ResumeModel.resume_version)).where(
                ResumeModel.candidate_id == candidate_id
            )
        )
        return (current or 0) + 1


# ── Candidaturas ─────────────────────────────────────────────────────────────


class SqlApplicationRepository(BaseRepository):
    def add(self, application: Application) -> Application:
        self.session.add(m.application_to_model(application))
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            # La unicidad la garantiza el motor, no la aplicación: es la única
            # defensa que sobrevive a dos peticiones simultáneas.
            raise DuplicateApplication(
                "El candidato ya tiene una candidatura registrada en esta vacante"
            ) from exc
        return application

    def get(self, application_id: str) -> Application | None:
        model = self.session.get(ApplicationModel, application_id)
        return m.application_to_entity(model) if model else None

    def get_by_idempotency_key(self, key: str) -> Application | None:
        model = self.session.scalar(
            select(ApplicationModel).where(ApplicationModel.idempotency_key == key)
        )
        return m.application_to_entity(model) if model else None

    def update(self, application: Application) -> Application:
        model = self.session.get(ApplicationModel, application.id)
        if model is None:
            raise ValueError(f"Candidatura no encontrada: {application.id}")
        m.apply_application(model, application)
        self.session.flush()
        return application

    def list_for_job(
        self, job_id: str, *, status: ApplicationStatus | None = None
    ) -> list[Application]:
        stmt = select(ApplicationModel).where(ApplicationModel.job_id == job_id)
        if status:
            stmt = stmt.where(ApplicationModel.status == status.value)
        stmt = stmt.order_by(ApplicationModel.final_score.desc().nullslast())
        return [m.application_to_entity(x) for x in self.session.scalars(stmt)]

    def list_for_candidate(self, candidate_id: str) -> list[Application]:
        stmt = (
            select(ApplicationModel)
            .where(ApplicationModel.candidate_id == candidate_id)
            .order_by(ApplicationModel.applied_at.desc())
        )
        return [m.application_to_entity(x) for x in self.session.scalars(stmt)]

    def list_all(self, *, limit: int = 500) -> list[Application]:
        stmt = select(ApplicationModel).order_by(
            ApplicationModel.applied_at.desc()
        ).limit(limit)
        return [m.application_to_entity(x) for x in self.session.scalars(stmt)]

    def count_by_status(self, job_id: str | None = None) -> dict[str, int]:
        stmt = select(ApplicationModel.status, func.count()).group_by(ApplicationModel.status)
        if job_id:
            stmt = stmt.where(ApplicationModel.job_id == job_id)
        return {status: count for status, count in self.session.execute(stmt)}

    def stale_applications(self, hours: int) -> list[Application]:
        """Candidaturas estancadas más tiempo del admitido en su etapa."""
        limit = datetime.now(UTC) - timedelta(hours=hours)
        stmt = select(ApplicationModel).where(
            ApplicationModel.entered_stage_at < limit,
            ApplicationModel.status.notin_(["rejected", "hired", "withdrawn"]),
        )
        return [m.application_to_entity(x) for x in self.session.scalars(stmt)]


# ── Evaluaciones ─────────────────────────────────────────────────────────────


class SqlEvaluationRepository(BaseRepository):
    """Las evaluaciones son inmutables: reevaluar crea una fila nueva.

    Sin esta propiedad, la pregunta «¿con qué criterios se rechazó a esta persona
    en marzo?» no tiene respuesta.
    """

    def add(self, evaluation: Evaluation) -> Evaluation:
        self.session.add(m.evaluation_to_model(evaluation))
        self.session.flush()
        return evaluation

    def get(self, evaluation_id: str) -> Evaluation | None:
        model = self.session.get(EvaluationModel, evaluation_id)
        return m.evaluation_to_entity(model) if model else None

    def list_for_application(self, application_id: str) -> list[Evaluation]:
        stmt = (
            select(EvaluationModel)
            .where(EvaluationModel.application_id == application_id)
            .order_by(EvaluationModel.created_at.desc())
        )
        return [m.evaluation_to_entity(x) for x in self.session.scalars(stmt)]

    def get_current(self, application_id: str) -> Evaluation | None:
        stmt = (
            select(EvaluationModel)
            .where(
                EvaluationModel.application_id == application_id,
                EvaluationModel.superseded_by_id.is_(None),
            )
            .order_by(EvaluationModel.created_at.desc())
        )
        model = self.session.scalars(stmt).first()
        return m.evaluation_to_entity(model) if model else None

    def supersede(self, evaluation_id: str, new_evaluation_id: str) -> None:
        """Marca una evaluación como sustituida. No la borra ni la modifica."""
        model = self.session.get(EvaluationModel, evaluation_id)
        if model is not None:
            model.superseded_by_id = new_evaluation_id
            self.session.flush()

    def list_for_job(self, job_id: str) -> list[Evaluation]:
        """Evaluaciones vigentes de una vacante, para analítica de equidad."""
        stmt = (
            select(EvaluationModel)
            .join(ApplicationModel, ApplicationModel.id == EvaluationModel.application_id)
            .where(
                ApplicationModel.job_id == job_id,
                EvaluationModel.superseded_by_id.is_(None),
            )
        )
        return [m.evaluation_to_entity(x) for x in self.session.scalars(stmt)]


# ── Revisión humana ──────────────────────────────────────────────────────────


class SqlReviewRepository(BaseRepository):
    def add(self, item: HumanReviewItem) -> HumanReviewItem:
        self.session.add(m.review_to_model(item))
        self.session.flush()
        return item

    def get(self, item_id: str) -> HumanReviewItem | None:
        model = self.session.get(HumanReviewModel, item_id)
        return m.review_to_entity(model) if model else None

    def update(self, item: HumanReviewItem) -> HumanReviewItem:
        model = self.session.get(HumanReviewModel, item.id)
        if model is None:
            raise ValueError(f"Elemento de revisión no encontrado: {item.id}")
        m.apply_review(model, item)
        self.session.flush()
        return item

    def list_queue(
        self, *, status: str | None = None, assigned_to: str | None = None
    ) -> list[HumanReviewItem]:
        """Cola ordenada por prioridad y antigüedad.

        Lo crítico primero y, dentro de cada prioridad, lo más antiguo: así nada
        se queda olvidado al fondo por el simple hecho de no ser urgente.
        """
        stmt = select(HumanReviewModel)
        if status:
            stmt = stmt.where(HumanReviewModel.status == status)
        else:
            stmt = stmt.where(
                HumanReviewModel.status.in_(["pending", "assigned", "in_progress"])
            )
        if assigned_to:
            stmt = stmt.where(HumanReviewModel.assigned_to == assigned_to)

        items = [m.review_to_entity(x) for x in self.session.scalars(stmt)]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        return sorted(items, key=lambda i: (order.get(i.priority.value, 9), i.created_at))

    def find_open_for_application(self, application_id: str) -> HumanReviewItem | None:
        stmt = select(HumanReviewModel).where(
            HumanReviewModel.application_id == application_id,
            HumanReviewModel.status.in_(["pending", "assigned", "in_progress"]),
        )
        model = self.session.scalars(stmt).first()
        return m.review_to_entity(model) if model else None

    def counts_by_status(self) -> dict[str, int]:
        stmt = select(HumanReviewModel.status, func.count()).group_by(HumanReviewModel.status)
        return {status: count for status, count in self.session.execute(stmt)}


# ── Comunicaciones ───────────────────────────────────────────────────────────


class SqlEmailRepository(BaseRepository):
    def add(self, message: EmailMessage) -> EmailMessage:
        self.session.add(m.email_to_model(message))
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            from app.core.exceptions import EmailAlreadySent

            raise EmailAlreadySent(
                "Ya existe una comunicación con esa clave de idempotencia"
            ) from exc
        return message

    def get(self, message_id: str) -> EmailMessage | None:
        model = self.session.get(EmailModel, message_id)
        return m.email_to_entity(model) if model else None

    def get_by_idempotency_key(self, key: str) -> EmailMessage | None:
        model = self.session.scalar(
            select(EmailModel).where(EmailModel.idempotency_key == key)
        )
        return m.email_to_entity(model) if model else None

    def update(self, message: EmailMessage) -> EmailMessage:
        model = self.session.get(EmailModel, message.id)
        if model is None:
            raise ValueError(f"Comunicación no encontrada: {message.id}")
        m.apply_email(model, message)
        self.session.flush()
        return message

    def list_for_application(self, application_id: str) -> list[EmailMessage]:
        stmt = (
            select(EmailModel)
            .where(EmailModel.application_id == application_id)
            .order_by(EmailModel.created_at.desc())
        )
        return [m.email_to_entity(x) for x in self.session.scalars(stmt)]

    def list_pending_approval(self) -> list[EmailMessage]:
        stmt = select(EmailModel).where(
            EmailModel.status == EmailStatus.PENDING_APPROVAL.value
        )
        return [m.email_to_entity(x) for x in self.session.scalars(stmt)]

    def count_sent_since(self, job_id: str, hours: int) -> int:
        limit = datetime.now(UTC) - timedelta(hours=hours)
        return self.session.scalar(
            select(func.count())
            .select_from(EmailModel)
            .where(
                EmailModel.job_id == job_id,
                EmailModel.status == EmailStatus.SENT.value,
                EmailModel.sent_at >= limit,
            )
        ) or 0


class SqlTemplateRepository(BaseRepository):
    def add(self, template: EmailTemplate) -> EmailTemplate:
        self.session.add(m.template_to_model(template))
        self.session.flush()
        return template

    def get(self, template_id: str) -> EmailTemplate | None:
        model = self.session.get(EmailTemplateModel, template_id)
        return m.template_to_entity(model) if model else None

    def get_by_code(self, code: str) -> EmailTemplate | None:
        model = self.session.scalar(
            select(EmailTemplateModel).where(EmailTemplateModel.code == code)
        )
        return m.template_to_entity(model) if model else None

    def list(self) -> list[EmailTemplate]:
        return [
            m.template_to_entity(x) for x in self.session.scalars(select(EmailTemplateModel))
        ]


# ── Auditoría ────────────────────────────────────────────────────────────────


class SqlAuditRepository(BaseRepository):
    """Registro de solo inserción con cadena de hash.

    No expone ``update`` ni ``delete``: lo que no se puede llamar no se puede usar
    por error. En producción se refuerza además con permisos de rol de base de
    datos que impiden esas operaciones incluso por SQL directo.

    Cada evento incorpora el hash del anterior. Alterar un evento pasado invalida
    todos los posteriores, y ``verify_chain`` lo detecta señalando exactamente
    dónde se rompió.
    """

    def append(self, event: AuditEvent) -> AuditEvent:
        last = self.session.scalar(
            select(AuditEventModel).order_by(
                AuditEventModel.timestamp.desc(), AuditEventModel.event_id.desc()
            ).limit(1)
        )
        if last is not None:
            last_timestamp = last.timestamp
            if last_timestamp.tzinfo is None:
                last_timestamp = last_timestamp.replace(tzinfo=UTC)
            if event.timestamp <= last_timestamp:
                event.timestamp = last_timestamp + timedelta(microseconds=1)
            event.previous_hash = last.event_hash
        else:
            event.previous_hash = GENESIS_HASH
        event.event_hash = self.compute_hash(event)
        self.session.add(m.audit_to_model(event))
        self.session.flush()
        return event

    def last_hash(self) -> str:
        stmt = (
            select(AuditEventModel.event_hash)
            .order_by(AuditEventModel.timestamp.desc(), AuditEventModel.event_id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt) or GENESIS_HASH

    @staticmethod
    def compute_hash(event: AuditEvent) -> str:
        """Hash del contenido relevante más el hash del evento anterior.

        Se serializa con claves ordenadas para que el hash sea estable: un mismo
        evento debe producir siempre el mismo resultado, hoy y al verificar la
        cadena dentro de un año.
        """
        payload = json.dumps(
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "actor_type": event.actor_type.value,
                "actor_id": event.actor_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "policy_result": event.policy_result,
                "severity": event.severity.value,
                "previous_hash": event.previous_hash,
            },
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_chain(self) -> tuple[bool, str | None]:
        """Recorre la cadena y devuelve el primer evento inconsistente.

        Detecta tanto la modificación de un evento como su eliminación: al borrar
        una fila, el enlace del siguiente evento deja de apuntar a nada válido.
        """
        stmt = select(AuditEventModel).order_by(
            AuditEventModel.timestamp.asc(), AuditEventModel.event_id.asc()
        )
        expected_previous = GENESIS_HASH
        for model in self.session.scalars(stmt):
            event = m.audit_to_entity(model)
            if event.previous_hash != expected_previous:
                return False, event.event_id
            if self.compute_hash(event) != event.event_hash:
                return False, event.event_id
            expected_previous = event.event_hash
        return True, None

    def list(
        self,
        *,
        resource_id: str | None = None,
        trace_id: str | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        stmt = select(AuditEventModel).order_by(AuditEventModel.timestamp.desc()).limit(limit)
        if resource_id:
            stmt = stmt.where(AuditEventModel.resource_id == resource_id)
        if trace_id:
            stmt = stmt.where(AuditEventModel.trace_id == trace_id)
        if action:
            stmt = stmt.where(AuditEventModel.action == action)
        if actor_id:
            stmt = stmt.where(AuditEventModel.actor_id == actor_id)
        if severity:
            stmt = stmt.where(AuditEventModel.severity == severity)
        return [m.audit_to_entity(x) for x in self.session.scalars(stmt)]

    def decision_trail(self, application_id: str) -> list[AuditEvent]:
        """Todos los eventos de una candidatura, en orden cronológico.

        Es la consulta que responde a «¿por qué se rechazó a esta persona?».
        """
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.resource_id == application_id)
            .order_by(AuditEventModel.timestamp.asc())
        )
        return [m.audit_to_entity(x) for x in self.session.scalars(stmt)]

    def count_by_severity(self) -> dict[str, int]:
        stmt = select(AuditEventModel.severity, func.count()).group_by(
            AuditEventModel.severity
        )
        return {severity: count for severity, count in self.session.execute(stmt)}


class SqlWorkflowRepository(BaseRepository):
    def add(self, run: WorkflowRun) -> WorkflowRun:
        self.session.add(m.workflow_to_model(run))
        self.session.flush()
        return run

    def get(self, run_id: str) -> WorkflowRun | None:
        model = self.session.get(WorkflowRunModel, run_id)
        return m.workflow_to_entity(model) if model else None

    def update(self, run: WorkflowRun) -> WorkflowRun:
        model = self.session.get(WorkflowRunModel, run.id)
        if model is None:
            raise ValueError(f"Ejecución no encontrada: {run.id}")
        model.status = run.status.value
        model.finished_at = run.finished_at
        model.node_timings = dict(run.node_timings)
        model.token_usage = dict(run.token_usage)
        model.cost_usd = run.cost_usd
        model.error = run.error
        self.session.flush()
        return run

    def list_for_application(self, application_id: str) -> list[WorkflowRun]:
        stmt = (
            select(WorkflowRunModel)
            .where(WorkflowRunModel.application_id == application_id)
            .order_by(WorkflowRunModel.started_at.desc())
        )
        return [m.workflow_to_entity(x) for x in self.session.scalars(stmt)]

    def total_cost_for_job(self, job_id: str) -> float:
        """Coste acumulado de IA en una vacante, para el control de presupuesto."""
        stmt = (
            select(func.sum(WorkflowRunModel.cost_usd))
            .join(
                ApplicationModel,
                ApplicationModel.id == WorkflowRunModel.application_id,
            )
            .where(ApplicationModel.job_id == job_id)
        )
        return float(self.session.scalar(stmt) or 0.0)


__all__ = [
    "GENESIS_HASH", "SqlApplicationRepository", "SqlAuditRepository",
    "SqlCandidateRepository", "SqlEmailRepository", "SqlEvaluationRepository",
    "SqlJobRepository", "SqlResumeRepository", "SqlReviewRepository",
    "SqlTemplateRepository", "SqlUserRepository", "SqlWorkflowRepository",
]
