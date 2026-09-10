"""Circuito completo: alta, evaluación, revisión humana, comunicación y traza.

Estas pruebas ejercitan el sistema tal como se usa, no sus piezas por separado.
Es donde se comprueban los invariantes que ningún módulo garantiza por su cuenta:
que una evaluación que exige supervisión siempre genera un elemento en la cola,
que una decisión humana queda registrada con su justificación, y que la traza
final permite reconstruir lo ocurrido.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.agent import VeraAgent
from app.application.services.audit_service import Actor
from app.application.services.decision_trail import DecisionTrailService
from app.application.services.email_service import EmailService
from app.application.services.ranking_service import RankingService
from app.application.services.review_service import ReviewService
from app.application.unit_of_work import UnitOfWork
from app.application.use_cases.evaluate_application import EvaluateApplicationUseCase
from app.application.use_cases.intake import (
    CreateApplicationUseCase,
    RegisterCandidateUseCase,
)
from app.core.exceptions import (
    ConsentMissingOrExpired,
    DuplicateApplication,
    EmailAlreadySent,
    HumanApprovalRequired,
    ValidationError,
)
from app.domain.entities import EmailTemplate, Job, ResumeDocument
from app.domain.enums import (
    ApplicationStatus,
    DocumentType,
    EmailTemplateKind,
    JobStatus,
    Permission,
    ReviewStatus,
)
from app.infrastructure.database.models import Base
from app.infrastructure.llm.mock_adapter import MockLLMAdapter

pytestmark = pytest.mark.integration

CV = """
# Ana Ramírez

Correo: ana@ejemplo.test

Ingeniera de software con 7 años de experiencia en desarrollo backend.

Senior Backend Engineer en Fintech (2021 - actualidad)
Desarrollé microservicios en Python con FastAPI sobre PostgreSQL.
Implementé pipelines de CI/CD con Docker desplegados en AWS.

Ingeniería de Sistemas, graduación 2018.
Español nativo, inglés C1.
"""


@pytest.fixture
def uow() -> UnitOfWork:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield UnitOfWork(session)


@pytest.fixture
def actor() -> Actor:
    return Actor.user("recruiter-test")


@pytest.fixture
def job(uow: UnitOfWork, requisitos) -> Job:
    return uow.jobs.add(
        Job(code="VAC-T", title="Backend Senior", status=JobStatus.OPEN,
            requirements=requisitos, description="Backend en Python")
    )


@pytest.fixture
def application(uow: UnitOfWork, job: Job, actor: Actor):  # noqa: ANN201
    result = RegisterCandidateUseCase(uow).execute(
        full_name="Ana Ramírez", email="ana@ejemplo.test",
        consent_granted=True, actor=actor,
    )
    resume = uow.resumes.add(
        ResumeDocument(
            candidate_id=result.candidate.id, filename="cv.md",
            document_type=DocumentType.MARKDOWN, raw_text=CV,
            char_count=len(CV), content_hash="hash-test",
        )
    )
    return CreateApplicationUseCase(uow).execute(
        candidate_id=result.candidate.id, job_id=job.id,
        resume_id=resume.id, actor=actor,
    )


@pytest.fixture
def use_case(uow: UnitOfWork) -> EvaluateApplicationUseCase:
    return EvaluateApplicationUseCase(
        uow, agent=VeraAgent(MockLLMAdapter(), prefer_langgraph=False)
    )


# ── Alta ─────────────────────────────────────────────────────────────────────


def test_no_se_registra_un_candidato_sin_consentimiento(uow: UnitOfWork, actor: Actor) -> None:
    """Un candidato registrado sin base legal ya es un incumplimiento.

    La comprobación va en el alta y no en el momento de evaluar: si se hiciera
    después, el dato ya estaría almacenado.
    """
    with pytest.raises(ValidationError, match="consentimiento"):
        RegisterCandidateUseCase(uow).execute(
            full_name="Sin Consentimiento", email="x@ejemplo.test",
            consent_granted=False, actor=actor,
        )


def test_un_candidato_existente_se_reutiliza(uow: UnitOfWork, actor: Actor) -> None:
    """Quien aplica a una segunda vacante es la misma persona, no un registro nuevo."""
    use_case = RegisterCandidateUseCase(uow)
    primera = use_case.execute(
        full_name="Ana", email="ana@ejemplo.test", consent_granted=True, actor=actor
    )
    segunda = use_case.execute(
        full_name="Ana", email="ana@ejemplo.test", consent_granted=True, actor=actor
    )
    assert segunda.was_existing
    assert segunda.candidate.id == primera.candidate.id


def test_no_se_permite_una_segunda_candidatura_en_la_misma_vacante(
    uow: UnitOfWork, job: Job, application, actor: Actor
) -> None:
    with pytest.raises(DuplicateApplication):
        CreateApplicationUseCase(uow).execute(
            candidate_id=application.candidate_id, job_id=job.id,
            resume_id=application.resume_id, actor=actor,
        )


def test_la_clave_de_idempotencia_es_determinista() -> None:
    a = CreateApplicationUseCase.idempotency_key("cand-1", "job-1")
    b = CreateApplicationUseCase.idempotency_key("cand-1", "job-1")
    assert a == b
    assert a != CreateApplicationUseCase.idempotency_key("cand-1", "job-2")


def test_no_se_evalua_a_quien_perdio_el_consentimiento(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    candidate = uow.candidates.get(application.candidate_id)
    candidate.consent.revoked = True
    uow.candidates.update(candidate)

    with pytest.raises(ConsentMissingOrExpired):
        use_case.execute(application_id=application.id, actor=actor)


# ── Evaluación ───────────────────────────────────────────────────────────────


def test_la_evaluacion_recorre_el_ciclo_de_vida(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    """La candidatura avanza por su ciclo, no salta de estado.

    Si el estado no reflejara el progreso, el pipeline mostraría todo en
    «nuevo» mientras el sistema trabaja.
    """
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)

    assert outcome.evaluation.id
    assert outcome.application.status is not ApplicationStatus.NEW

    acciones = [
        e.new_state["status"]
        for e in uow.audit.list(action="application.status_changed", limit=20)
        if e.new_state
    ]
    assert "resume_processed" in acciones
    assert "under_evaluation" in acciones


def test_toda_evaluacion_que_exige_supervision_genera_un_elemento_en_la_cola(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    """Invariante del sistema.

    Un estado que anuncia trabajo pendiente sin que nadie lo tenga asignado es
    peor que no tenerlo: el pipeline muestra actividad que no existe.
    """
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)

    if outcome.evaluation.requires_human_review:
        assert outcome.review_item_id is not None
        item = uow.reviews.get(outcome.review_item_id)
        assert item is not None
        assert item.application_id == application.id
        assert item.reasons or item.context


def test_la_evaluacion_queda_registrada_con_su_procedencia(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    use_case.execute(application_id=application.id, actor=actor, dry_run=False)

    evaluacion = uow.evaluations.get_current(application.id)
    assert evaluacion is not None
    assert evaluacion.agent_version
    assert evaluacion.model_name
    assert evaluacion.prompt_versions
    assert evaluacion.trace_id
    assert evaluacion.workflow_run_id

    ejecuciones = uow.workflows.list_for_application(application.id)
    assert ejecuciones, "La ejecución del grafo debe persistirse"
    assert ejecuciones[0].node_timings


def test_reevaluar_conserva_la_evaluacion_previa(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    aplicacion = uow.applications.get(application.id)
    aplicacion.status = ApplicationStatus.HUMAN_REVIEW
    uow.applications.update(aplicacion)

    use_case.execute(application_id=application.id, actor=actor, dry_run=False)

    historial = uow.evaluations.list_for_application(application.id)
    assert len(historial) == 2
    assert sum(1 for e in historial if e.is_current) == 1


def test_el_modo_simulacion_no_cambia_el_estado_final(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    """En dry-run la política deniega toda acción con efecto."""
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=True)

    denegadas = {a["rule"] for a in outcome.rejected_actions}
    assert "change_status→shortlisted" not in outcome.executed_actions
    assert outcome.evaluation.id, "La evaluación sí se registra: es información, no acción"


# ── Revisión humana ──────────────────────────────────────────────────────────


def test_una_decision_sin_justificacion_se_rechaza(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    """Sin justificación no hay decisión.

    Es lo que convierte el historial en algo defendible cuando alguien pregunte
    por qué se rechazó a una persona.
    """
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    assert outcome.review_item_id

    with pytest.raises(ValidationError, match="justificación"):
        ReviewService(uow).decide(
            item_id=outcome.review_item_id, decision="approve",
            justification="ok", actor=actor,
            actor_permissions=frozenset({Permission.REVIEW_DECIDE}),
        )


def test_una_decision_no_admitida_se_rechaza(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    with pytest.raises(ValidationError, match="no admitida"):
        ReviewService(uow).decide(
            item_id=outcome.review_item_id, decision="contratar_ya",
            justification="Una justificación suficientemente larga", actor=actor,
            actor_permissions=frozenset({Permission.REVIEW_DECIDE}),
        )


def test_aprobar_avanza_la_candidatura_y_queda_auditado(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    justificacion = "He verificado la evidencia de FastAPI y PostgreSQL contra el CV."

    resultado = ReviewService(uow).decide(
        item_id=outcome.review_item_id, decision="approve",
        justification=justificacion, actor=actor,
        actor_permissions=frozenset({Permission.REVIEW_DECIDE}),
    )
    assert resultado.item.status is ReviewStatus.APPROVED

    decisiones = uow.audit.list(action="human_review.decided")
    assert decisiones
    assert decisiones[0].metadata["justification"] == justificacion
    assert decisiones[0].human_approval_by == actor.actor_id


def test_modificar_exige_una_puntuacion(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    with pytest.raises(ValidationError, match="puntuación"):
        ReviewService(uow).decide(
            item_id=outcome.review_item_id, decision="modify",
            justification="La puntuación automática no refleja su experiencia real.",
            actor=actor, actor_permissions=frozenset({Permission.REVIEW_DECIDE}),
        )


def test_modificar_no_altera_la_evaluacion_original(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    """La anulación humana se registra junto a la evaluación, no encima de ella."""
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    original = float(outcome.evaluation.total_score)

    ReviewService(uow).decide(
        item_id=outcome.review_item_id, decision="modify", score_override=42.0,
        justification="Ajuste manual tras revisar la evidencia con el equipo técnico.",
        actor=actor, actor_permissions=frozenset({Permission.REVIEW_DECIDE}),
    )

    evaluacion = uow.evaluations.get(outcome.evaluation.id)
    assert float(evaluacion.total_score) == original, (
        "La evaluación de la IA es inmutable"
    )
    aplicacion = uow.applications.get(application.id)
    assert aplicacion.final_score == 42.0


def test_el_plazo_vencido_no_resuelve_el_caso(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    """Al vencer, el elemento se libera y sube de prioridad; nunca se decide solo."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    item = uow.reviews.get(outcome.review_item_id)

    # La fecha de creación se modifica directamente en la fila: el mapeador no
    # la propaga a propósito, porque una fecha de alta que se puede reescribir
    # desde el dominio no sirve para medir plazos.
    uow.session.execute(
        text("UPDATE human_reviews SET created_at = :fecha WHERE id = :id"),
        {
            # Como cadena ISO: pasar un `datetime` al conector de SQLite está
            # obsoleto desde Python 3.12.
            "fecha": (
                datetime.now(UTC) - timedelta(hours=item.sla_hours + 5)
            ).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "id": item.id,
        },
    )
    uow.session.expire_all()

    vencidos = ReviewService(uow).expire_overdue()
    assert vencidos

    revisado = uow.reviews.get(item.id)
    assert revisado.status is ReviewStatus.PENDING, "No debe resolverse solo"
    assert revisado.decided_by is None
    assert revisado.assigned_to is None


# ── Comunicaciones ───────────────────────────────────────────────────────────


@pytest.fixture
def plantilla(uow: UnitOfWork) -> EmailTemplate:
    return uow.templates.add(
        EmailTemplate(
            code="acuse", kind=EmailTemplateKind.RECEIPT_CONFIRMATION,
            subject_template="Recibimos tu candidatura — {job_title}",
            body_template="Hola:\n\n{mensaje}\n\nUn saludo.",
            allowed_variables=["mensaje"], approved=True,
            requires_human_approval=False,
        )
    )


@pytest.fixture
def plantilla_sensible(uow: UnitOfWork) -> EmailTemplate:
    return uow.templates.add(
        EmailTemplate(
            code="rechazo", kind=EmailTemplateKind.REJECTION,
            subject_template="Resolución — {job_title}",
            body_template="Hola:\n\n{mensaje}\n\nUn saludo.",
            allowed_variables=["mensaje"], approved=True,
            requires_human_approval=True,
        )
    )


def test_el_destinatario_es_siempre_el_correo_registrado(
    uow: UnitOfWork, application, plantilla: EmailTemplate, actor: Actor
) -> None:
    """Ninguna dirección externa puede colarse como destinatario."""
    prepared = EmailService(uow).prepare(
        application_id=application.id, template_code="acuse",
        actor=actor, use_ai=False,
    )
    candidato = uow.candidates.get(application.candidate_id)
    assert str(prepared.message.recipient) == str(candidato.email)


def test_no_se_prepara_dos_veces_la_misma_comunicacion(
    uow: UnitOfWork, application, plantilla: EmailTemplate, actor: Actor
) -> None:
    servicio = EmailService(uow)
    servicio.prepare(
        application_id=application.id, template_code="acuse", actor=actor, use_ai=False
    )
    with pytest.raises(EmailAlreadySent):
        servicio.prepare(
            application_id=application.id, template_code="acuse",
            actor=actor, use_ai=False,
        )


def test_una_categoria_sensible_no_se_envia_sin_aprobacion(
    uow: UnitOfWork, application, plantilla_sensible: EmailTemplate, actor: Actor
) -> None:
    servicio = EmailService(uow)
    prepared = servicio.prepare(
        application_id=application.id, template_code="rechazo",
        actor=actor, use_ai=False,
    )
    with pytest.raises(HumanApprovalRequired):
        servicio.send(
            email_id=prepared.message.id, actor=actor,
            actor_permissions=frozenset({Permission.EMAIL_SEND}),
            force_dry_run=False,
        )


def test_reenviar_lo_ya_enviado_no_tiene_efecto(
    uow: UnitOfWork, application, plantilla: EmailTemplate, actor: Actor
) -> None:
    """Idempotencia observable: repetir la operación no duplica el envío."""
    servicio = EmailService(uow)
    prepared = servicio.prepare(
        application_id=application.id, template_code="acuse", actor=actor, use_ai=False
    )
    permisos = frozenset({Permission.EMAIL_SEND})
    primero = servicio.send(
        email_id=prepared.message.id, actor=actor,
        actor_permissions=permisos, force_dry_run=False,
    )
    segundo = servicio.send(
        email_id=prepared.message.id, actor=actor,
        actor_permissions=permisos, force_dry_run=False,
    )
    assert primero.gmail_message_id == segundo.gmail_message_id
    assert len(uow.emails.list_for_application(application.id)) == 1


def test_los_marcadores_sin_valor_no_quedan_visibles(plantilla: EmailTemplate) -> None:
    """Un correo con «{mensaje}» literal delataría el fallo ante el candidato."""
    subject, body = EmailService.render(
        plantilla, job_title="Backend Senior", variables={"mensaje": ""}
    )
    assert "{" not in subject and "}" not in subject
    assert "{" not in body and "}" not in body
    assert "Backend Senior" in subject


# ── Traza y ranking ──────────────────────────────────────────────────────────


def test_la_traza_reconstruye_la_historia_completa(
    uow: UnitOfWork, application, use_case: EvaluateApplicationUseCase, actor: Actor
) -> None:
    outcome = use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    ReviewService(uow).decide(
        item_id=outcome.review_item_id, decision="approve",
        justification="Evidencia verificada contra el documento original.",
        actor=actor, actor_permissions=frozenset({Permission.REVIEW_DECIDE}),
    )

    trail = DecisionTrailService(uow).build(application.id)

    assert trail.chain_verified
    assert trail.was_reviewed_by_human
    assert trail.evaluations
    assert len(trail.steps) >= 4
    assert "con revisión humana documentada" in trail.summary_line

    markdown = trail.to_markdown()
    assert "Traza de decisión" in markdown
    assert "Decisiones humanas" in markdown
    assert "Evidencia verificada" in markdown


def test_no_se_comparan_candidaturas_de_vacantes_distintas(
    uow: UnitOfWork, application, requisitos, actor: Actor
) -> None:
    """Las puntuaciones son relativas a cada convocatoria.

    Compararlas entre vacantes daría un resultado aparentemente riguroso y sin
    significado, que es peor que no ofrecer la comparación.
    """
    otra = uow.jobs.add(
        Job(code="VAC-OTRA", title="Otra", status=JobStatus.OPEN, requirements=requisitos)
    )
    segunda = CreateApplicationUseCase(uow).execute(
        candidate_id=application.candidate_id, job_id=otra.id,
        resume_id=application.resume_id, actor=actor,
    )
    with pytest.raises(ValidationError, match="misma vacante"):
        RankingService(uow).compare(application.id, segunda.id)


def test_quien_no_supera_los_filtros_queda_al_final_del_ranking(
    uow: UnitOfWork, job: Job, application, use_case: EvaluateApplicationUseCase,
    actor: Actor,
) -> None:
    """Un requisito excluyente no se compensa con buenas notas en el resto."""
    use_case.execute(application_id=application.id, actor=actor, dry_run=False)
    ranking = RankingService(uow).rank_job(job.id, include_rejected=True)

    superan = [r for r in ranking if r.passed_hard_filters]
    fallan = [r for r in ranking if not r.passed_hard_filters]
    if superan and fallan:
        assert max(r.position for r in superan) < min(r.position for r in fallan)
