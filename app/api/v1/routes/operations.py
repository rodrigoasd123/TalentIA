"""Rutas de operación: autenticación, pipeline, revisión, comunicaciones,
analítica y auditoría.

Todas declaran explícitamente el permiso que exigen. Un endpoint sin declaración
sería un endpoint sin control de acceso, y el arranque de la aplicación lo
detecta.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, Query, Response, UploadFile, status

from app.application.services.analytics_service import AnalyticsService
from app.application.services.audit_service import Actor, AuditService
from app.application.services.decision_trail import DecisionTrailService
from app.application.services.email_service import EmailService
from app.application.services.ranking_service import RankingService
from app.application.services.review_service import ReviewService
from app.application.use_cases.evaluate_application import EvaluateApplicationUseCase
from app.application.use_cases.intake import IntakePipelineUseCase
from app.api.dependencies import ActorDep, CurrentUserDep, UowDep, requires
from app.api.schemas import IntakeResponse, JobCreateRequest, JobUpdateRequest
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.entities import Job, JobRequirements
from app.domain.enums import JobStatus, Permission
from app.infrastructure.llm.factory import build_llm_from_settings
from app.infrastructure.security.passwords import dummy_verify, verify_password
from app.infrastructure.security.tokens import TokenService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")


# ── Autenticación ────────────────────────────────────────────────────────────


@router.post("/auth/login", tags=["autenticación"])
def login(
    uow: UowDep,
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
) -> dict[str, Any]:
    """Inicio de sesión.

    El mensaje de error es idéntico tanto si el usuario no existe como si la
    contraseña es incorrecta, y el tiempo de respuesta también: de lo contrario
    se podría enumerar qué correos están registrados.
    """
    user = uow.users.get_by_email(email)
    if user is None:
        dummy_verify()
        raise AuthenticationError("Credenciales inválidas")

    if user.is_locked:
        raise AuthenticationError(
            "La cuenta está bloqueada temporalmente por intentos fallidos"
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            from datetime import UTC, datetime, timedelta

            user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
        uow.users.update(user)
        uow.audit.append(
            _security_event("auth.login_failed", user.id, user.failed_login_attempts)
        )
        raise AuthenticationError("Credenciales inválidas")

    if not user.is_active:
        raise AuthenticationError("La cuenta está desactivada")

    user.failed_login_attempts = 0
    user.locked_until = None
    uow.users.update(user)

    pair = TokenService().issue_pair(
        user_id=user.id, email=str(user.email), role=user.role
    )
    uow.audit.append(_security_event("auth.login_success", user.id, 0, severity="info"))

    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": pair.token_type,
        "expires_in": pair.expires_in,
        "user": {
            "id": user.id,
            "email": str(user.email),
            "full_name": user.full_name,
            "role": user.role.value,
        },
    }


def _security_event(action: str, user_id: str, attempts: int, severity: str = "warning"):  # noqa: ANN202
    from app.domain.entities import AuditEvent
    from app.domain.enums import ActorType, Severity

    return AuditEvent(
        actor_type=ActorType.USER,
        actor_id=user_id,
        action=action,
        resource_type="user",
        resource_id=user_id,
        severity=Severity.MEDIUM if severity == "warning" else Severity.INFO,
        metadata={"failed_attempts": attempts},
    )


@router.post("/auth/refresh", tags=["autenticación"])
def refresh(refresh_token: str = Body(..., embed=True)) -> dict[str, Any]:
    """Rota el token de refresco. Detecta reutilización y revoca la sesión."""
    pair = TokenService().rotate(refresh_token)
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": pair.token_type,
        "expires_in": pair.expires_in,
    }


@router.post("/auth/logout", tags=["autenticación"])
def logout(refresh_token: str = Body(..., embed=True)) -> dict[str, str]:
    TokenService().revoke_session(refresh_token)
    return {"status": "sesión cerrada"}


@router.get("/auth/me", tags=["autenticación"])
def me(user: CurrentUserDep) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role.value,
        "permissions": sorted(p.value for p in user.permissions),
        "is_lab_session": user.is_lab_session,
    }


# ── Vacantes e ingesta ───────────────────────────────────────────────────────


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "code": job.code,
        "title": job.title,
        "description": job.description,
        "department": job.department,
        "location": job.location,
        "status": job.status.value,
        "minimum_score": job.requirements.minimum_score,
        "review_threshold": job.requirements.review_threshold,
        "min_years_experience": job.requirements.min_years_experience,
        "mandatory_skills": job.requirements.mandatory_skills,
        "hard_filter_count": len(job.requirements.hard_filters),
        "weights": {d.value: w for d, w in job.requirements.weights.weights.items()},
        "requirements_version": job.requirements.version,
    }


@router.post(
    "/jobs",
    status_code=status.HTTP_201_CREATED,
    tags=["vacantes"],
    dependencies=[Depends(requires(Permission.JOB_WRITE))],
)
def create_job(payload: JobCreateRequest, uow: UowDep, actor: ActorDep) -> dict[str, Any]:
    if uow.jobs.get_by_code(payload.code.strip().upper()) is not None:
        raise ValidationError(f"Ya existe una vacante con código {payload.code}")
    job = Job(
        code=payload.code.strip().upper(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        department=payload.department.strip(),
        location=payload.location.strip(),
        status=JobStatus.OPEN if payload.criteria_approved else JobStatus.DRAFT,
        requirements=JobRequirements(
            mandatory_skills=sorted({s.strip().lower() for s in payload.mandatory_skills if s.strip()}),
            minimum_score=payload.minimum_score,
            review_threshold=payload.review_threshold,
            min_years_experience=payload.min_years_experience,
        ),
    )
    stored = uow.jobs.add(job)
    AuditService(uow.audit).record(
        action="job.created",
        actor=actor,
        resource_type="job",
        resource_id=stored.id,
        new_state={"code": stored.code, "status": stored.status.value, "criteria_approved": payload.criteria_approved},
    )
    return _job_payload(stored)


@router.patch(
    "/jobs/{job_id}",
    tags=["vacantes"],
    dependencies=[Depends(requires(Permission.JOB_WRITE))],
)
def update_job(job_id: str, payload: JobUpdateRequest, uow: UowDep, actor: ActorDep) -> dict[str, Any]:
    job = uow.jobs.get(job_id)
    if job is None:
        raise NotFoundError(f"No existe la vacante {job_id}")
    previous = {"title": job.title, "status": job.status.value, "requirements_version": job.requirements.version}
    changed_criteria = False
    for field_name in ("title", "description", "department", "location"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(job, field_name, value.strip())
    for field_name in ("minimum_score", "review_threshold", "min_years_experience"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(job.requirements, field_name, value)
            changed_criteria = True
    if payload.mandatory_skills is not None:
        job.requirements.mandatory_skills = sorted(
            {s.strip().lower() for s in payload.mandatory_skills if s.strip()}
        )
        changed_criteria = True
    if changed_criteria:
        job.requirements.version += 1
        job.status = JobStatus.DRAFT
    if payload.criteria_approved is not None:
        job.status = JobStatus.OPEN if payload.criteria_approved else JobStatus.DRAFT
    job.touch()
    stored = uow.jobs.update(job)
    AuditService(uow.audit).record(
        action="job.updated",
        actor=actor,
        resource_type="job",
        resource_id=stored.id,
        previous_state=previous,
        new_state={"title": stored.title, "status": stored.status.value, "requirements_version": stored.requirements.version},
    )
    return _job_payload(stored)


@router.get(
    "/jobs/{job_id}/sourcing-query",
    tags=["vacantes"],
    dependencies=[Depends(requires(Permission.JOB_READ))],
)
def sourcing_query(job_id: str, uow: UowDep) -> dict[str, Any]:
    """Prepara una búsqueda Boolean para ejecución manual en LinkedIn."""
    job = uow.jobs.get(job_id)
    if job is None:
        raise NotFoundError(f"No existe la vacante {job_id}")
    terms = [job.title, *job.requirements.mandatory_skills]
    normalized = list(dict.fromkeys(term.strip() for term in terms if term.strip()))
    boolean = " AND ".join(f'"{term}"' for term in normalized)
    if job.location:
        boolean += f' AND "{job.location.strip()}"'
    return {
        "keywords": normalized,
        "boolean_query": boolean,
        "execution": "manual",
        "opens_linkedin": False,
        "notice": "Copia esta consulta y ejecútala manualmente en LinkedIn Recruiter.",
    }


@router.post(
    "/intake",
    response_model=IntakeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["candidaturas"],
    dependencies=[Depends(requires(Permission.CANDIDATE_WRITE))],
)
async def intake_application(
    uow: UowDep,
    actor: ActorDep,
    full_name: str = Form(..., min_length=2, max_length=160),
    email: str = Form(...),
    job_id: str = Form(...),
    consent_granted: bool = Form(...),
    resume: UploadFile = File(...),
    phone: str = Form(""),
    source: str = Form("direct"),
) -> IntakeResponse:
    content = await resume.read()
    result = IntakePipelineUseCase(uow).execute(
        full_name=full_name,
        email=email,
        phone=phone,
        job_id=job_id,
        content=content,
        filename=resume.filename or "cv",
        source=source,
        consent_granted=consent_granted,
        actor=actor,
    )
    assert result.resume is not None and result.application is not None
    return IntakeResponse(
        candidate_id=result.candidate.id,
        resume_id=result.resume.id,
        application_id=result.application.id,
        was_existing_candidate=result.was_existing,
        duplicates=result.duplicates,
        warnings=result.warnings,
    )


# ── Pipeline y candidaturas ──────────────────────────────────────────────────


@router.get(
    "/pipeline",
    tags=["pipeline"],
    dependencies=[Depends(requires(Permission.APPLICATION_READ))],
)
def pipeline(uow: UowDep, job_id: str | None = Query(None)) -> dict[str, Any]:
    """Candidaturas agrupadas por etapa."""
    return {"columns": RankingService(uow).pipeline_view(job_id)}


@router.get(
    "/applications",
    tags=["pipeline"],
    dependencies=[Depends(requires(Permission.APPLICATION_READ))],
)
def list_applications(uow: UowDep, job_id: str | None = Query(None)) -> list[dict[str, Any]]:
    applications = (
        uow.applications.list_for_job(job_id) if job_id
        else uow.applications.list_all(limit=1000)
    )
    rows = []
    for application in applications:
        candidate = uow.candidates.get(application.candidate_id)
        job = uow.jobs.get(application.job_id)
        rows.append(
            {
                "id": application.id,
                "candidate_id": application.candidate_id,
                "candidate_name": candidate.full_name if candidate else "—",
                "job_id": application.job_id,
                "job_code": job.code if job else "—",
                "status": application.status.value,
                "score": application.final_score,
                "applied_at": application.applied_at.isoformat(),
                "hours_in_stage": round(application.hours_in_stage, 1),
            }
        )
    return rows


@router.get(
    "/applications/{application_id}/360",
    tags=["pipeline"],
    dependencies=[Depends(requires(Permission.CANDIDATE_PII_READ))],
)
def candidate_360(application_id: str, uow: UowDep, actor: ActorDep) -> dict[str, Any]:
    """Vista consolidada de una candidatura.

    El acceso queda auditado: es información personal y hay que poder responder
    quién la consultó.
    """
    application = uow.applications.get(application_id)
    if application is None:
        raise NotFoundError(f"No existe la candidatura {application_id}")

    candidate = uow.candidates.get(application.candidate_id)
    job = uow.jobs.get(application.job_id)
    resume = uow.resumes.get(application.resume_id) if application.resume_id else None
    evaluations = uow.evaluations.list_for_application(application_id)
    current = uow.evaluations.get_current(application_id)
    emails = uow.emails.list_for_application(application_id)
    review = uow.reviews.find_open_for_application(application_id)
    trail = DecisionTrailService(uow).build(application_id)

    from app.application.services.audit_service import AuditService

    AuditService(uow.audit).record_access(
        actor=actor, resource_type="candidate",
        resource_id=application.candidate_id, purpose="consulta candidate 360",
    )

    return {
        "application": {
            "id": application.id,
            "status": application.status.value,
            "score": application.final_score,
            "applied_at": application.applied_at.isoformat(),
            "source": application.source,
            "hours_in_stage": round(application.hours_in_stage, 1),
        },
        "candidate": {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "email": str(candidate.email),
            "phone": candidate.phone,
            "location": candidate.location,
            "tags": candidate.tags,
            "consent_valid": candidate.can_be_processed,
            "consent_expires": (
                candidate.consent.expires_at.isoformat() if candidate.consent else None
            ),
        } if candidate else None,
        "job": {"code": job.code, "title": job.title} if job else None,
        "resume": {
            "id": resume.id,
            "filename": resume.filename,
            "version": resume.resume_version,
            "chars": resume.char_count,
            "is_suspicious": resume.is_suspicious,
            "extraction": resume.extraction.model_dump(mode="json") if resume.extraction else None,
        } if resume else None,
        "current_evaluation": _evaluation_payload(current) if current else None,
        "evaluation_history": [_evaluation_payload(e) for e in evaluations],
        "emails": [
            {
                "id": e.id, "template_id": e.template_id, "subject": e.subject,
                "status": e.status.value, "sent_at": e.sent_at.isoformat() if e.sent_at else None,
                "recipient": e.recipient.masked(),
            }
            for e in emails
        ],
        "open_review": {
            "id": review.id, "priority": review.priority.value,
            "reasons": [r.value for r in review.reasons],
            "is_overdue": review.is_overdue,
        } if review else None,
        "timeline": [s.to_dict() for s in trail.steps],
    }


def _evaluation_payload(evaluation) -> dict[str, Any]:  # noqa: ANN001
    return {
        "id": evaluation.id,
        "created_at": evaluation.created_at.isoformat(),
        "is_current": evaluation.is_current,
        "score": float(evaluation.total_score) if evaluation.total_score else None,
        "recommendation": evaluation.recommendation.value,
        "passed_hard_filters": evaluation.passed_hard_filters,
        "evidence_rate": evaluation.evidence_verification_rate,
        "requires_human_review": evaluation.requires_human_review,
        "review_reasons": [r.value for r in evaluation.review_reasons],
        "summary": evaluation.summary,
        "strengths": evaluation.strengths,
        "gaps": evaluation.gaps,
        "missing_requirements": evaluation.missing_requirements,
        "model": evaluation.model_name,
        "agent_version": evaluation.agent_version,
        "prompt_versions": evaluation.prompt_versions,
        "cost_usd": evaluation.cost_usd,
        "hard_filters": [
            {"label": f.filter_label, "passed": f.passed, "mandatory": f.mandatory,
             "explanation": f.explanation}
            for f in evaluation.hard_filter_results
        ],
        "dimensions": [
            {
                "dimension": d.dimension.value, "score": d.score, "weight": d.weight,
                "reasoning": d.reasoning,
                "evidence": [
                    {"quote": s.quote, "verified": s.verified, "match_ratio": s.match_ratio}
                    for s in d.evidence
                ],
            }
            for d in evaluation.dimension_scores
        ],
        "bias_audit": (
            evaluation.bias_audit.model_dump(mode="json") if evaluation.bias_audit else None
        ),
    }


@router.post(
    "/applications/{application_id}/evaluate",
    tags=["evaluación"],
    dependencies=[Depends(requires(Permission.EVALUATION_RUN))],
)
def evaluate(
    application_id: str, uow: UowDep, actor: ActorDep, dry_run: bool | None = Query(None)
) -> dict[str, Any]:
    """Ejecuta VERA sobre una candidatura y aplica lo que la política permita."""
    use_case = EvaluateApplicationUseCase(uow)
    outcome = use_case.execute(
        application_id=application_id, actor=actor, dry_run=dry_run
    )
    return {
        **outcome.summary,
        "explanation": outcome.agent_result.explain(),
        "evaluation": _evaluation_payload(outcome.evaluation),
    }


@router.post(
    "/applications/{application_id}/transition",
    tags=["pipeline"],
    dependencies=[Depends(requires(Permission.APPLICATION_TRANSITION))],
)
def transition(
    application_id: str,
    uow: UowDep,
    user: CurrentUserDep,
    target_status: str = Body(..., embed=True),
    reason: str = Body("", embed=True),
) -> dict[str, Any]:
    """Cambio de estado manual, validado por la máquina de estados."""
    from app.application.services.audit_service import AuditService
    from app.domain.enums import ApplicationStatus
    from app.domain.rules.state_machine import ApplicationStateMachine

    application = uow.applications.get(application_id)
    if application is None:
        raise NotFoundError(f"No existe la candidatura {application_id}")

    target = ApplicationStatus(target_status)
    previous = application.status
    ApplicationStateMachine.validate(
        previous, target, actor_permissions=user.permissions, is_human_actor=True
    )
    application.move_to(target)
    uow.applications.update(application)

    AuditService(uow.audit).record_status_change(
        actor=user.as_actor(), application_id=application_id,
        previous=previous.value, new=target.value, reason=reason,
        approved_by=user.user_id,
    )
    return {"application_id": application_id, "from": previous.value, "to": target.value}


@router.get(
    "/jobs/{job_id}/ranking",
    tags=["evaluación"],
    dependencies=[Depends(requires(Permission.APPLICATION_READ))],
)
def ranking(
    job_id: str, uow: UowDep, include_rejected: bool = Query(False)
) -> list[dict[str, Any]]:
    return [r.to_dict() for r in RankingService(uow).rank_job(job_id, include_rejected=include_rejected)]


@router.get(
    "/applications/compare",
    tags=["evaluación"],
    dependencies=[Depends(requires(Permission.APPLICATION_READ))],
)
def compare(a: str, b: str, uow: UowDep) -> dict[str, Any]:
    """Explica por qué una candidatura supera a otra, dimensión a dimensión."""
    return RankingService(uow).compare(a, b).to_dict()


# ── Revisión humana ──────────────────────────────────────────────────────────


@router.get(
    "/reviews/queue",
    tags=["revisión"],
    dependencies=[Depends(requires(Permission.REVIEW_DECIDE))],
)
def review_queue(uow: UowDep, status: str | None = Query(None)) -> list[dict[str, Any]]:
    rows = []
    for item in ReviewService(uow).queue(status=status):
        application = uow.applications.get(item.application_id)
        candidate = (
            uow.candidates.get(application.candidate_id) if application else None
        )
        job = uow.jobs.get(application.job_id) if application else None
        rows.append(
            {
                "id": item.id,
                "application_id": item.application_id,
                "candidate_name": candidate.full_name if candidate else "—",
                "job_code": job.code if job else "—",
                "priority": item.priority.value,
                "status": item.status.value,
                "reasons": [r.value for r in item.reasons],
                "sla_hours": item.sla_hours,
                "due_at": item.due_at.isoformat(),
                "is_overdue": item.is_overdue,
                "assigned_to": item.assigned_to,
                "score": item.context.get("score"),
                "summary": item.context.get("summary", ""),
                "created_at": item.created_at.isoformat(),
            }
        )
    return rows


@router.get(
    "/reviews/statistics",
    tags=["revisión"],
    dependencies=[Depends(requires(Permission.REVIEW_DECIDE))],
)
def review_statistics(uow: UowDep) -> dict[str, Any]:
    return ReviewService(uow).statistics()


@router.post(
    "/reviews/{item_id}/claim",
    tags=["revisión"],
    dependencies=[Depends(requires(Permission.REVIEW_DECIDE))],
)
def claim_review(item_id: str, uow: UowDep, actor: ActorDep) -> dict[str, Any]:
    item = ReviewService(uow).claim(item_id, actor=actor)
    return {"id": item.id, "status": item.status.value, "assigned_to": item.assigned_to}


@router.post(
    "/reviews/{item_id}/decide",
    tags=["revisión"],
    dependencies=[Depends(requires(Permission.REVIEW_DECIDE))],
)
def decide_review(
    item_id: str,
    uow: UowDep,
    user: CurrentUserDep,
    decision: str = Body(..., embed=True),
    justification: str = Body(..., embed=True),
    score_override: float | None = Body(None, embed=True),
) -> dict[str, Any]:
    """Resuelve un elemento de la cola. La justificación es obligatoria."""
    result = ReviewService(uow).decide(
        item_id=item_id,
        decision=decision,
        justification=justification,
        actor=user.as_actor(),
        actor_permissions=user.permissions,
        score_override=score_override,
    )
    return {
        "id": result.item.id,
        "status": result.item.status.value,
        "application_status": result.application.status.value,
        "status_changed": result.status_changed,
        "requires_reevaluation": result.requires_reevaluation,
    }


@router.post(
    "/reviews/expire-overdue",
    tags=["revisión"],
    dependencies=[Depends(requires(Permission.REVIEW_DECIDE))],
)
def expire_overdue(uow: UowDep) -> dict[str, Any]:
    """Marca como vencidos los elementos fuera de plazo. No los resuelve."""
    expired = ReviewService(uow).expire_overdue()
    return {"expired": len(expired), "ids": [i.id for i in expired]}


# ── Comunicaciones ───────────────────────────────────────────────────────────


@router.get("/email-templates", tags=["comunicaciones"], dependencies=[Depends(requires(Permission.EMAIL_PREPARE))])
def list_templates(uow: UowDep) -> list[dict[str, Any]]:
    return [
        {
            "id": t.id, "code": t.code, "kind": t.kind.value,
            "subject": t.subject_template, "approved": t.approved,
            "requires_human_approval": t.requires_human_approval,
            "allowed_variables": t.allowed_variables, "version": t.template_version,
        }
        for t in uow.templates.list()
    ]


@router.get("/emails/provider", tags=["comunicaciones"], dependencies=[Depends(requires(Permission.SETTINGS_READ))])
def email_provider(uow: UowDep) -> dict[str, Any]:
    return EmailService(uow).provider_status()


@router.post(
    "/emails/prepare",
    tags=["comunicaciones"],
    dependencies=[Depends(requires(Permission.EMAIL_PREPARE))],
)
def prepare_email(
    uow: UowDep,
    actor: ActorDep,
    application_id: str = Body(..., embed=True),
    template_code: str = Body(..., embed=True),
    use_ai: bool = Body(True, embed=True),
) -> dict[str, Any]:
    service = EmailService(uow, llm=build_llm_from_settings(uow.settings))
    prepared = service.prepare(
        application_id=application_id, template_code=template_code,
        actor=actor, use_ai=use_ai,
    )
    return {
        "id": prepared.message.id,
        "subject": prepared.message.subject,
        "body": prepared.message.body,
        "recipient": prepared.message.recipient.masked(),
        "status": prepared.message.status.value,
        "requires_approval": prepared.requires_approval,
        "generated_variables": prepared.generated_variables,
    }


@router.get(
    "/emails/pending",
    tags=["comunicaciones"],
    dependencies=[Depends(requires(Permission.EMAIL_APPROVE))],
)
def pending_emails(uow: UowDep) -> list[dict[str, Any]]:
    return [
        {
            "id": e.id, "application_id": e.application_id, "subject": e.subject,
            "body": e.body, "recipient": e.recipient.masked(),
            "created_at": e.created_at.isoformat(),
        }
        for e in EmailService(uow).pending_approval()
    ]


@router.post(
    "/emails/{email_id}/approve",
    tags=["comunicaciones"],
    dependencies=[Depends(requires(Permission.EMAIL_APPROVE))],
)
def approve_email(
    email_id: str, uow: UowDep, user: CurrentUserDep, note: str = Body("", embed=True)
) -> dict[str, Any]:
    message = EmailService(uow).approve(
        email_id=email_id, actor=user.as_actor(),
        actor_permissions=user.permissions, note=note,
    )
    return {"id": message.id, "status": message.status.value, "approved_by": message.approved_by}


@router.post(
    "/emails/{email_id}/send",
    tags=["comunicaciones"],
    dependencies=[Depends(requires(Permission.EMAIL_SEND))],
)
def send_email(
    email_id: str, uow: UowDep, user: CurrentUserDep,
    force_dry_run: bool | None = Body(None, embed=True),
) -> dict[str, Any]:
    message = EmailService(uow).send(
        email_id=email_id, actor=user.as_actor(),
        actor_permissions=user.permissions, force_dry_run=force_dry_run,
    )
    return {
        "id": message.id, "status": message.status.value,
        "gmail_message_id": message.gmail_message_id,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
    }


# ── Analítica ────────────────────────────────────────────────────────────────


@router.get("/dashboard/summary", tags=["analítica"], dependencies=[Depends(requires(Permission.APPLICATION_READ))])
def dashboard(uow: UowDep) -> dict[str, Any]:
    return AnalyticsService(uow).dashboard()


@router.get("/dashboard/funnel", tags=["analítica"], dependencies=[Depends(requires(Permission.APPLICATION_READ))])
def funnel(uow: UowDep, job_id: str | None = Query(None)) -> list[dict[str, Any]]:
    return AnalyticsService(uow).funnel(job_id)


@router.get("/dashboard/sla-alerts", tags=["analítica"], dependencies=[Depends(requires(Permission.APPLICATION_READ))])
def sla_alerts(uow: UowDep, hours: int = Query(72, ge=1, le=2000)) -> list[dict[str, Any]]:
    return AnalyticsService(uow).sla_alerts(hours)


@router.get("/dashboard/sources", tags=["analítica"], dependencies=[Depends(requires(Permission.APPLICATION_READ))])
def sources(uow: UowDep) -> list[dict[str, Any]]:
    return AnalyticsService(uow).source_analytics()


@router.get("/dashboard/stage-durations", tags=["analítica"], dependencies=[Depends(requires(Permission.APPLICATION_READ))])
def stage_durations(uow: UowDep, job_id: str | None = Query(None)) -> dict[str, float]:
    return AnalyticsService(uow).stage_durations(job_id)


@router.get(
    "/equity/report",
    tags=["analítica"],
    dependencies=[Depends(requires(Permission.AUDIT_READ))],
)
def equity(uow: UowDep, job_id: str | None = Query(None)) -> dict[str, Any]:
    """Panel de equidad: patrones agregados en la distribución de puntuaciones."""
    return AnalyticsService(uow).equity_report(job_id).to_dict()


# ── Auditoría ────────────────────────────────────────────────────────────────


@router.get(
    "/audit/events",
    tags=["auditoría"],
    dependencies=[Depends(requires(Permission.AUDIT_READ))],
)
def audit_events(
    uow: UowDep,
    resource_id: str | None = Query(None),
    action: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    events = uow.audit.list(
        resource_id=resource_id, action=action, severity=severity, limit=limit
    )
    return [
        {
            "event_id": e.event_id,
            "timestamp": e.timestamp.isoformat(),
            "trace_id": e.trace_id,
            "actor_type": e.actor_type.value,
            "actor_id": e.actor_id,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "severity": e.severity.value,
            "previous_state": e.previous_state,
            "new_state": e.new_state,
            "policy_result": e.policy_result,
            "metadata": e.metadata,
        }
        for e in events
    ]


@router.get(
    "/audit/verify",
    tags=["auditoría"],
    dependencies=[Depends(requires(Permission.AUDIT_READ))],
)
def verify_audit(uow: UowDep) -> dict[str, Any]:
    """Verifica la cadena de hash del registro de auditoría."""
    ok, broken = uow.audit.verify_chain()
    return {
        "verified": ok,
        "broken_at_event": broken,
        "total_events": len(uow.audit.list(limit=100000)),
        "by_severity": uow.audit.count_by_severity(),
        "message": (
            "La cadena es íntegra: ningún evento ha sido modificado ni eliminado."
            if ok
            else f"Se detectó una inconsistencia a partir del evento {broken}."
        ),
    }


@router.get(
    "/audit/applications/{application_id}/decision-trail",
    tags=["auditoría"],
    dependencies=[Depends(requires(Permission.AUDIT_READ))],
)
def decision_trail(
    application_id: str, uow: UowDep, format: str = Query("json", pattern="^(json|markdown|csv)$")
) -> Any:
    """Traza de decisión completa, exportable.

    Es el documento que responde a «¿por qué se rechazó a esta persona?» con
    todo lo necesario para defenderlo ante el candidato o ante una auditoría.
    """
    trail = DecisionTrailService(uow).build(application_id)
    if format == "markdown":
        return Response(
            content=trail.to_markdown(),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="traza-{application_id[:8]}.md"'
            },
        )
    if format == "csv":
        return Response(
            content=trail.to_csv(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="traza-{application_id[:8]}.csv"'
            },
        )
    return trail.to_dict()


__all__ = ["router"]
