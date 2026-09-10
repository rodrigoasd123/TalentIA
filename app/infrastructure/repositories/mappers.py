"""Traducción entre entidades de dominio y modelos de persistencia.

Existe esta capa porque el dominio y la base de datos responden a preguntas
distintas. Las entidades expresan reglas de negocio; los modelos expresan cómo se
guardan las filas. Cuando se fusionan, cualquier cambio en el esquema se propaga
al núcleo del negocio y la migración a otro motor deja de ser viable.

El coste es este fichero. El beneficio es que ``app/domain`` no importa
SQLAlchemy en ninguna parte, algo que un test de arquitectura comprueba.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.domain.entities import (
    Application,
    AuditEvent,
    BiasAuditResult,
    Candidate,
    DimensionScore,
    EmailMessage,
    EmailTemplate,
    Evaluation,
    HumanReviewItem,
    Job,
    JobRequirements,
    ResumeDocument,
    ResumeExtraction,
    User,
    WorkflowRun,
)
from app.domain.enums import (
    ActorType,
    ApplicationStatus,
    DocumentType,
    EmailStatus,
    EmailTemplateKind,
    JobStatus,
    Recommendation,
    ReviewReason,
    ReviewStatus,
    Role,
    ScoringDimension,
    Severity,
    WorkflowStatus,
)
from app.domain.value_objects import (
    ConsentRecord,
    EmailAddress,
    EvidenceSpan,
    FilterResult,
    Score,
)
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


def _aware(value: datetime | None) -> datetime | None:
    """Devuelve la fecha con zona horaria explícita.

    SQLite no almacena el huso, así que al releer una fecha viene sin él. Restaurar
    UTC aquí evita errores de comparación entre fechas con y sin zona, que es una
    fuente clásica de cálculos de plazo equivocados.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _base_fields(model: Any) -> dict[str, Any]:
    return {
        "id": model.id,
        "created_at": _aware(model.created_at),
        "updated_at": _aware(model.updated_at),
        "version": model.version,
    }


# ── Usuarios ─────────────────────────────────────────────────────────────────


def user_to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        email=str(user.email),
        full_name=user.full_name,
        role=user.role.value,
        password_hash=user.password_hash,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        created_at=user.created_at,
        updated_at=user.updated_at,
        version=user.version,
    )


def user_to_entity(model: UserModel) -> User:
    return User(
        **_base_fields(model),
        email=EmailAddress(value=model.email),
        full_name=model.full_name,
        role=Role(model.role),
        password_hash=model.password_hash,
        is_active=model.is_active,
        mfa_enabled=model.mfa_enabled,
        failed_login_attempts=model.failed_login_attempts,
        locked_until=_aware(model.locked_until),
    )


def apply_user(model: UserModel, user: User) -> UserModel:
    model.full_name = user.full_name
    model.role = user.role.value
    model.password_hash = user.password_hash
    model.is_active = user.is_active
    model.mfa_enabled = user.mfa_enabled
    model.failed_login_attempts = user.failed_login_attempts
    model.locked_until = user.locked_until
    model.version = user.version
    return model


# ── Vacantes ─────────────────────────────────────────────────────────────────


def job_to_model(job: Job) -> JobModel:
    return JobModel(
        id=job.id,
        tenant_id=job.tenant_id,
        code=job.code,
        title=job.title,
        description=job.description,
        department=job.department,
        location=job.location,
        employment_type=job.employment_type,
        status=job.status.value,
        requirements=job.requirements.model_dump(mode="json"),
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        currency=job.currency,
        opening_date=_iso(job.opening_date),
        closing_date=_iso(job.closing_date),
        recruiter_id=job.recruiter_id,
        hiring_manager_id=job.hiring_manager_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        version=job.version,
    )


def job_to_entity(model: JobModel) -> Job:
    return Job(
        **_base_fields(model),
        tenant_id=model.tenant_id,
        code=model.code,
        title=model.title,
        description=model.description,
        department=model.department,
        location=model.location,
        employment_type=model.employment_type,
        status=JobStatus(model.status),
        requirements=JobRequirements.model_validate(model.requirements or {}),
        salary_min=model.salary_min,
        salary_max=model.salary_max,
        currency=model.currency,
        opening_date=_parse_date(model.opening_date),
        closing_date=_parse_date(model.closing_date),
        recruiter_id=model.recruiter_id,
        hiring_manager_id=model.hiring_manager_id,
    )


def apply_job(model: JobModel, job: Job) -> JobModel:
    model.title = job.title
    model.description = job.description
    model.department = job.department
    model.location = job.location
    model.employment_type = job.employment_type
    model.status = job.status.value
    model.requirements = job.requirements.model_dump(mode="json")
    model.salary_min = job.salary_min
    model.salary_max = job.salary_max
    model.currency = job.currency
    model.opening_date = _iso(job.opening_date)
    model.closing_date = _iso(job.closing_date)
    model.recruiter_id = job.recruiter_id
    model.hiring_manager_id = job.hiring_manager_id
    model.version = job.version
    return model


# ── Candidatos ───────────────────────────────────────────────────────────────


def candidate_to_model(candidate: Candidate) -> CandidateModel:
    return CandidateModel(
        id=candidate.id,
        tenant_id=candidate.tenant_id,
        full_name=candidate.full_name,
        email=str(candidate.email) if candidate.email else None,
        phone=candidate.phone,
        national_id=candidate.national_id,
        location=candidate.location,
        source=candidate.source,
        consent=candidate.consent.model_dump(mode="json") if candidate.consent else None,
        tags=list(candidate.tags),
        processing_status=candidate.processing_status,
        legal_basis_status=candidate.legal_basis_status,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
        version=candidate.version,
    )


def candidate_to_entity(model: CandidateModel) -> Candidate:
    return Candidate(
        **_base_fields(model),
        tenant_id=model.tenant_id,
        full_name=model.full_name,
        email=EmailAddress(value=model.email) if model.email else None,
        phone=model.phone,
        national_id=model.national_id,
        location=model.location,
        source=model.source,
        consent=ConsentRecord.model_validate(model.consent) if model.consent else None,
        tags=list(model.tags or []),
        processing_status=model.processing_status,
        legal_basis_status=model.legal_basis_status,
    )


def apply_candidate(model: CandidateModel, candidate: Candidate) -> CandidateModel:
    model.full_name = candidate.full_name
    model.email = str(candidate.email) if candidate.email else None
    model.phone = candidate.phone
    model.national_id = candidate.national_id
    model.location = candidate.location
    model.source = candidate.source
    model.consent = candidate.consent.model_dump(mode="json") if candidate.consent else None
    model.tags = list(candidate.tags)
    model.processing_status = candidate.processing_status
    model.legal_basis_status = candidate.legal_basis_status
    model.version = candidate.version
    return model


# ── Documentos ───────────────────────────────────────────────────────────────


def resume_to_model(resume: ResumeDocument) -> ResumeModel:
    return ResumeModel(
        id=resume.id,
        candidate_id=resume.candidate_id,
        filename=resume.filename,
        document_type=resume.document_type.value,
        storage_path=resume.storage_path,
        content_hash=resume.content_hash,
        raw_text=resume.raw_text,
        char_count=resume.char_count,
        resume_version=resume.resume_version,
        extraction=resume.extraction.model_dump(mode="json") if resume.extraction else None,
        is_suspicious=resume.is_suspicious,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
        version=resume.version,
    )


def resume_to_entity(model: ResumeModel) -> ResumeDocument:
    return ResumeDocument(
        **_base_fields(model),
        candidate_id=model.candidate_id,
        filename=model.filename,
        document_type=DocumentType(model.document_type),
        storage_path=model.storage_path,
        content_hash=model.content_hash,
        raw_text=model.raw_text,
        char_count=model.char_count,
        resume_version=model.resume_version,
        extraction=(
            ResumeExtraction.model_validate(model.extraction) if model.extraction else None
        ),
        is_suspicious=model.is_suspicious,
    )


def apply_resume(model: ResumeModel, resume: ResumeDocument) -> ResumeModel:
    model.extraction = resume.extraction.model_dump(mode="json") if resume.extraction else None
    model.is_suspicious = resume.is_suspicious
    model.raw_text = resume.raw_text
    model.char_count = resume.char_count
    model.version = resume.version
    return model


# ── Candidaturas ─────────────────────────────────────────────────────────────


def application_to_model(application: Application) -> ApplicationModel:
    return ApplicationModel(
        id=application.id,
        tenant_id=application.tenant_id,
        candidate_id=application.candidate_id,
        job_id=application.job_id,
        resume_id=application.resume_id,
        status=application.status.value,
        source=application.source,
        applied_at=application.applied_at,
        entered_stage_at=application.entered_stage_at,
        final_score=application.final_score,
        assigned_to=application.assigned_to,
        idempotency_key=application.idempotency_key,
        requirements_version=application.requirements_version,
        created_at=application.created_at,
        updated_at=application.updated_at,
        version=application.version,
    )


def application_to_entity(model: ApplicationModel) -> Application:
    return Application(
        **_base_fields(model),
        tenant_id=model.tenant_id,
        candidate_id=model.candidate_id,
        job_id=model.job_id,
        resume_id=model.resume_id,
        status=ApplicationStatus(model.status),
        source=model.source,
        applied_at=_aware(model.applied_at) or model.applied_at,
        entered_stage_at=_aware(model.entered_stage_at) or model.entered_stage_at,
        final_score=model.final_score,
        assigned_to=model.assigned_to,
        idempotency_key=model.idempotency_key,
        requirements_version=model.requirements_version,
    )


def apply_application(model: ApplicationModel, application: Application) -> ApplicationModel:
    model.status = application.status.value
    model.resume_id = application.resume_id
    model.entered_stage_at = application.entered_stage_at
    model.final_score = application.final_score
    model.assigned_to = application.assigned_to
    model.requirements_version = application.requirements_version
    model.version = application.version
    return model


# ── Evaluaciones ─────────────────────────────────────────────────────────────


def evaluation_to_model(evaluation: Evaluation) -> EvaluationModel:
    return EvaluationModel(
        id=evaluation.id,
        application_id=evaluation.application_id,
        evaluation_type=evaluation.evaluation_type,
        passed_hard_filters=evaluation.passed_hard_filters,
        hard_filter_results=[f.model_dump(mode="json") for f in evaluation.hard_filter_results],
        dimension_scores=[d.model_dump(mode="json") for d in evaluation.dimension_scores],
        total_score=float(evaluation.total_score) if evaluation.total_score else None,
        recommendation=evaluation.recommendation.value,
        missing_requirements=list(evaluation.missing_requirements),
        strengths=list(evaluation.strengths),
        gaps=list(evaluation.gaps),
        summary=evaluation.summary,
        bias_audit=evaluation.bias_audit.model_dump(mode="json") if evaluation.bias_audit else None,
        evidence_verification_rate=evaluation.evidence_verification_rate,
        requires_human_review=evaluation.requires_human_review,
        review_reasons=[r.value for r in evaluation.review_reasons],
        model_name=evaluation.model_name,
        model_version=evaluation.model_version,
        prompt_versions=dict(evaluation.prompt_versions),
        temperature=evaluation.temperature,
        token_usage=dict(evaluation.token_usage),
        cost_usd=evaluation.cost_usd,
        requirements_version=evaluation.requirements_version,
        agent_version=evaluation.agent_version,
        trace_id=evaluation.trace_id,
        workflow_run_id=evaluation.workflow_run_id,
        superseded_by_id=evaluation.superseded_by_id,
        created_by=evaluation.created_by,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
        version=evaluation.version,
    )


def evaluation_to_entity(model: EvaluationModel) -> Evaluation:
    return Evaluation(
        **_base_fields(model),
        application_id=model.application_id,
        evaluation_type=model.evaluation_type,
        passed_hard_filters=model.passed_hard_filters,
        hard_filter_results=[
            FilterResult.model_validate(f) for f in (model.hard_filter_results or [])
        ],
        dimension_scores=[
            _dimension_to_entity(d) for d in (model.dimension_scores or [])
        ],
        total_score=Score(value=model.total_score) if model.total_score is not None else None,
        recommendation=Recommendation(model.recommendation),
        missing_requirements=list(model.missing_requirements or []),
        strengths=list(model.strengths or []),
        gaps=list(model.gaps or []),
        summary=model.summary,
        bias_audit=(
            BiasAuditResult.model_validate(model.bias_audit) if model.bias_audit else None
        ),
        evidence_verification_rate=model.evidence_verification_rate,
        requires_human_review=model.requires_human_review,
        review_reasons=[ReviewReason(r) for r in (model.review_reasons or [])],
        model_name=model.model_name,
        model_version=model.model_version,
        prompt_versions=dict(model.prompt_versions or {}),
        temperature=model.temperature,
        token_usage=dict(model.token_usage or {}),
        cost_usd=model.cost_usd,
        requirements_version=model.requirements_version,
        agent_version=model.agent_version,
        trace_id=model.trace_id,
        workflow_run_id=model.workflow_run_id,
        superseded_by_id=model.superseded_by_id,
        created_by=model.created_by,
    )


def _dimension_to_entity(raw: dict[str, Any]) -> DimensionScore:
    return DimensionScore(
        dimension=ScoringDimension(raw["dimension"]),
        score=raw["score"],
        weight=raw["weight"],
        reasoning=raw.get("reasoning", ""),
        evidence=[
            EvidenceSpan(
                quote=e["quote"],
                dimension=ScoringDimension(e["dimension"]),
                verified=e.get("verified", False),
                match_ratio=e.get("match_ratio", 0.0),
                source_offset=e.get("source_offset"),
            )
            for e in raw.get("evidence", [])
        ],
    )


# ── Revisión humana ──────────────────────────────────────────────────────────


def review_to_model(item: HumanReviewItem) -> HumanReviewModel:
    return HumanReviewModel(
        id=item.id,
        application_id=item.application_id,
        evaluation_id=item.evaluation_id,
        reasons=[r.value for r in item.reasons],
        priority=item.priority.value,
        status=item.status.value,
        sla_hours=item.sla_hours,
        assigned_to=item.assigned_to,
        decided_by=item.decided_by,
        decided_at=item.decided_at,
        decision_note=item.decision_note,
        score_override=item.score_override,
        context=dict(item.context),
        created_at=item.created_at,
        updated_at=item.updated_at,
        version=item.version,
    )


def review_to_entity(model: HumanReviewModel) -> HumanReviewItem:
    return HumanReviewItem(
        **_base_fields(model),
        application_id=model.application_id,
        evaluation_id=model.evaluation_id,
        reasons=[ReviewReason(r) for r in (model.reasons or [])],
        priority=Severity(model.priority),
        status=ReviewStatus(model.status),
        sla_hours=model.sla_hours,
        assigned_to=model.assigned_to,
        decided_by=model.decided_by,
        decided_at=_aware(model.decided_at),
        decision_note=model.decision_note,
        score_override=model.score_override,
        context=dict(model.context or {}),
    )


def apply_review(model: HumanReviewModel, item: HumanReviewItem) -> HumanReviewModel:
    model.status = item.status.value
    model.assigned_to = item.assigned_to
    model.decided_by = item.decided_by
    model.decided_at = item.decided_at
    model.decision_note = item.decision_note
    model.score_override = item.score_override
    model.context = dict(item.context)
    model.version = item.version
    return model


# ── Comunicaciones ───────────────────────────────────────────────────────────


def template_to_model(template: EmailTemplate) -> EmailTemplateModel:
    return EmailTemplateModel(
        id=template.id,
        code=template.code,
        kind=template.kind.value,
        subject_template=template.subject_template,
        body_template=template.body_template,
        template_version=template.template_version,
        approved=template.approved,
        allowed_variables=list(template.allowed_variables),
        requires_human_approval=template.requires_human_approval,
        created_at=template.created_at,
        updated_at=template.updated_at,
        version=template.version,
    )


def template_to_entity(model: EmailTemplateModel) -> EmailTemplate:
    return EmailTemplate(
        **_base_fields(model),
        code=model.code,
        kind=EmailTemplateKind(model.kind),
        subject_template=model.subject_template,
        body_template=model.body_template,
        template_version=model.template_version,
        approved=model.approved,
        allowed_variables=list(model.allowed_variables or []),
        requires_human_approval=model.requires_human_approval,
    )


def email_to_model(email: EmailMessage) -> EmailModel:
    return EmailModel(
        id=email.id,
        application_id=email.application_id,
        candidate_id=email.candidate_id,
        job_id=email.job_id,
        template_id=email.template_id,
        template_version=email.template_version,
        recipient=str(email.recipient),
        subject=email.subject,
        body=email.body,
        status=email.status.value,
        idempotency_key=email.idempotency_key,
        gmail_message_id=email.gmail_message_id,
        gmail_thread_id=email.gmail_thread_id,
        initiated_by=email.initiated_by,
        approved_by=email.approved_by,
        approved_at=email.approved_at,
        sent_at=email.sent_at,
        retry_count=email.retry_count,
        error_message=email.error_message,
        created_at=email.created_at,
        updated_at=email.updated_at,
        version=email.version,
    )


def email_to_entity(model: EmailModel) -> EmailMessage:
    return EmailMessage(
        **_base_fields(model),
        application_id=model.application_id,
        candidate_id=model.candidate_id,
        job_id=model.job_id,
        template_id=model.template_id,
        template_version=model.template_version,
        recipient=EmailAddress(value=model.recipient),
        subject=model.subject,
        body=model.body,
        status=EmailStatus(model.status),
        idempotency_key=model.idempotency_key,
        gmail_message_id=model.gmail_message_id,
        gmail_thread_id=model.gmail_thread_id,
        initiated_by=model.initiated_by,
        approved_by=model.approved_by,
        approved_at=_aware(model.approved_at),
        sent_at=_aware(model.sent_at),
        retry_count=model.retry_count,
        error_message=model.error_message,
    )


def apply_email(model: EmailModel, email: EmailMessage) -> EmailModel:
    model.status = email.status.value
    model.subject = email.subject
    model.body = email.body
    model.gmail_message_id = email.gmail_message_id
    model.gmail_thread_id = email.gmail_thread_id
    model.approved_by = email.approved_by
    model.approved_at = email.approved_at
    model.sent_at = email.sent_at
    model.retry_count = email.retry_count
    model.error_message = email.error_message
    model.version = email.version
    return model


# ── Trazabilidad ─────────────────────────────────────────────────────────────


def audit_to_model(event: AuditEvent) -> AuditEventModel:
    return AuditEventModel(
        event_id=event.event_id,
        timestamp=event.timestamp,
        trace_id=event.trace_id,
        actor_type=event.actor_type.value,
        actor_id=event.actor_id,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        previous_state=event.previous_state,
        new_state=event.new_state,
        agent_version=event.agent_version,
        prompt_version=event.prompt_version,
        model=event.model,
        policy_result=event.policy_result,
        human_approval_by=event.human_approval_by,
        severity=event.severity.value,
        event_metadata=dict(event.metadata),
        previous_hash=event.previous_hash,
        event_hash=event.event_hash,
    )


def audit_to_entity(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        event_id=model.event_id,
        timestamp=_aware(model.timestamp) or model.timestamp,
        trace_id=model.trace_id,
        actor_type=ActorType(model.actor_type),
        actor_id=model.actor_id,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        action=model.action,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        previous_state=model.previous_state,
        new_state=model.new_state,
        agent_version=model.agent_version,
        prompt_version=model.prompt_version,
        model=model.model,
        policy_result=model.policy_result,
        human_approval_by=model.human_approval_by,
        severity=Severity(model.severity),
        metadata=dict(model.event_metadata or {}),
        previous_hash=model.previous_hash,
        event_hash=model.event_hash,
    )


def workflow_to_model(run: WorkflowRun) -> WorkflowRunModel:
    return WorkflowRunModel(
        id=run.id,
        application_id=run.application_id,
        graph_name=run.graph_name,
        agent_version=run.agent_version,
        status=run.status.value,
        trace_id=run.trace_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        node_timings=dict(run.node_timings),
        token_usage=dict(run.token_usage),
        cost_usd=run.cost_usd,
        error=run.error,
        dry_run=run.dry_run,
        created_at=run.created_at,
        updated_at=run.updated_at,
        version=run.version,
    )


def workflow_to_entity(model: WorkflowRunModel) -> WorkflowRun:
    return WorkflowRun(
        **_base_fields(model),
        application_id=model.application_id,
        graph_name=model.graph_name,
        agent_version=model.agent_version,
        status=WorkflowStatus(model.status),
        trace_id=model.trace_id,
        started_at=_aware(model.started_at) or model.started_at,
        finished_at=_aware(model.finished_at),
        node_timings=dict(model.node_timings or {}),
        token_usage=dict(model.token_usage or {}),
        cost_usd=model.cost_usd,
        error=model.error,
        dry_run=model.dry_run,
    )


__all__ = [
    "apply_application", "apply_candidate", "apply_email", "apply_job",
    "apply_resume", "apply_review", "apply_user", "application_to_entity",
    "application_to_model", "audit_to_entity", "audit_to_model",
    "candidate_to_entity", "candidate_to_model", "email_to_entity",
    "email_to_model", "evaluation_to_entity", "evaluation_to_model",
    "job_to_entity", "job_to_model", "resume_to_entity", "resume_to_model",
    "review_to_entity", "review_to_model", "template_to_entity",
    "template_to_model", "user_to_entity", "user_to_model",
    "workflow_to_entity", "workflow_to_model",
]
