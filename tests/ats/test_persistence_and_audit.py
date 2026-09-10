"""Persistencia, cadena de auditoría e inmutabilidad de las evaluaciones."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.application.services.audit_service import Actor, AuditService
from app.application.unit_of_work import UnitOfWork
from app.domain.entities import AuditEvent, Candidate, Evaluation, Job
from app.domain.enums import ActorType, JobStatus, Recommendation, Severity
from app.domain.value_objects import EmailAddress, Score
from app.infrastructure.database.models import Base
from app.infrastructure.repositories.sqlalchemy_repos import GENESIS_HASH

pytestmark = pytest.mark.integration


@pytest.fixture
def uow() -> UnitOfWork:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield UnitOfWork(session)


# ── Ida y vuelta dominio ↔ base de datos ─────────────────────────────────────


def test_una_vacante_sobrevive_al_viaje_de_ida_y_vuelta(uow: UnitOfWork, requisitos) -> None:
    """Los criterios deben conservarse íntegros al persistirse y releerse.

    Es el test que protege la migración a PostgreSQL: si el mapeo pierde algo,
    se detecta aquí y no en el despliegue.
    """
    job = Job(
        code="VAC-TEST", title="Puesto de prueba", status=JobStatus.OPEN,
        requirements=requisitos, description="Descripción",
    )
    uow.jobs.add(job)
    uow.flush()

    recuperada = uow.jobs.get_by_code("VAC-TEST")
    assert recuperada is not None
    assert recuperada.title == job.title
    assert recuperada.status is JobStatus.OPEN
    assert len(recuperada.requirements.hard_filters) == len(requisitos.hard_filters)
    assert recuperada.requirements.minimum_score == requisitos.minimum_score
    assert recuperada.requirements.weights.weights == requisitos.weights.weights
    # La base legal de cada filtro debe persistirse: sin ella el criterio no se
    # puede justificar ante nadie.
    for filtro in recuperada.requirements.hard_filters:
        assert filtro.legal_basis


def test_el_correo_del_candidato_es_unico_por_tenant(uow: UnitOfWork) -> None:
    """La unicidad la garantiza el motor, no la aplicación."""
    from sqlalchemy.exc import IntegrityError

    uow.candidates.add(Candidate(full_name="Prueba", email=EmailAddress(value="a@example.test")))
    # El repositorio confirma en cada alta, así que el conflicto salta en la
    # segunda inserción y no al confirmar la transacción.
    with pytest.raises(IntegrityError):
        uow.candidates.add(
            Candidate(full_name="Otra persona", email=EmailAddress(value="a@example.test"))
        )


# ── Inmutabilidad de las evaluaciones ────────────────────────────────────────


def test_reevaluar_no_borra_la_evaluacion_anterior(uow: UnitOfWork) -> None:
    """La pregunta «¿con qué criterios se rechazó en marzo?» debe tener respuesta."""
    primera = uow.evaluations.add(
        Evaluation(
            application_id="app-1", total_score=Score(value=60.0),
            recommendation=Recommendation.REJECT,
        )
    )
    segunda = uow.evaluations.add(
        Evaluation(
            application_id="app-1", total_score=Score(value=85.0),
            recommendation=Recommendation.SHORTLIST,
        )
    )
    uow.evaluations.supersede(primera.id, segunda.id)
    uow.flush()

    historial = uow.evaluations.list_for_application("app-1")
    assert len(historial) == 2, "La evaluación anterior debe conservarse"

    vigente = uow.evaluations.get_current("app-1")
    assert vigente is not None
    assert vigente.id == segunda.id

    anterior = uow.evaluations.get(primera.id)
    assert anterior is not None
    assert anterior.superseded_by_id == segunda.id
    assert not anterior.is_current
    # El valor original permanece intacto, no se sobrescribe con el nuevo.
    assert float(anterior.total_score) == 60.0


# ── Cadena de auditoría ──────────────────────────────────────────────────────


def _evento(action: str, resource_id: str = "app-1") -> AuditEvent:
    return AuditEvent(
        action=action, resource_type="application", resource_id=resource_id,
        actor_type=ActorType.SYSTEM,
    )


def test_la_cadena_arranca_desde_el_hash_genesis(uow: UnitOfWork) -> None:
    assert uow.audit.last_hash() == GENESIS_HASH
    evento = uow.audit.append(_evento("primero"))
    assert evento.previous_hash == GENESIS_HASH
    assert evento.event_hash


def test_cada_evento_enlaza_con_el_anterior(uow: UnitOfWork) -> None:
    eventos = [uow.audit.append(_evento(f"accion_{i}")) for i in range(5)]
    for anterior, siguiente in zip(eventos, eventos[1:]):
        assert siguiente.previous_hash == anterior.event_hash


def test_una_cadena_intacta_se_verifica(uow: UnitOfWork) -> None:
    for i in range(10):
        uow.audit.append(_evento(f"accion_{i}"))
    uow.flush()

    ok, roto = uow.audit.verify_chain()
    assert ok
    assert roto is None


def test_modificar_un_evento_rompe_la_cadena(uow: UnitOfWork) -> None:
    """La detección de manipulación es la razón de ser del encadenamiento.

    Se altera la fila directamente por SQL, saltándose la aplicación, que es
    exactamente el escenario contra el que protege.
    """
    eventos = [uow.audit.append(_evento(f"accion_{i}")) for i in range(5)]
    uow.flush()

    objetivo = eventos[2]
    uow.session.execute(
        text("UPDATE audit_events SET action = :nuevo WHERE event_id = :id"),
        {"nuevo": "accion_manipulada", "id": objetivo.event_id},
    )
    uow.flush()

    ok, roto = uow.audit.verify_chain()
    assert not ok, "La manipulación debería detectarse"
    assert roto == objetivo.event_id, "Debe señalarse el evento exacto"


def test_eliminar_un_evento_rompe_la_cadena(uow: UnitOfWork) -> None:
    """Borrar una fila deja al siguiente evento apuntando a un hash inexistente."""
    eventos = [uow.audit.append(_evento(f"accion_{i}")) for i in range(5)]
    uow.flush()

    uow.session.execute(
        text("DELETE FROM audit_events WHERE event_id = :id"),
        {"id": eventos[1].event_id},
    )
    uow.flush()

    ok, roto = uow.audit.verify_chain()
    assert not ok
    assert roto == eventos[2].event_id


def test_el_repositorio_de_auditoria_no_expone_modificacion(uow: UnitOfWork) -> None:
    """Lo que no se puede llamar no se puede usar por error."""
    for metodo in ("update", "delete", "remove", "save"):
        assert not hasattr(uow.audit, metodo), (
            f"El repositorio de auditoría expone «{metodo}», que no debería existir"
        )


def test_el_hash_es_estable_entre_calculos(uow: UnitOfWork) -> None:
    """Un mismo evento debe producir siempre el mismo hash.

    Si no lo fuera, la verificación fallaría al azar y la garantía sería inútil.
    """
    evento = uow.audit.append(_evento("estable"))
    assert uow.audit.compute_hash(evento) == evento.event_hash
    assert uow.audit.compute_hash(evento) == uow.audit.compute_hash(evento)


# ── Servicio de auditoría ────────────────────────────────────────────────────


def test_las_decisiones_de_ia_registran_su_procedencia(uow: UnitOfWork) -> None:
    """Sin modelo, agente y versión de prompt, una decisión no es explicable."""
    servicio = AuditService(uow.audit)
    servicio.record_evaluation(
        actor=Actor.agent("VERA/1.0.0"),
        application_id="app-1",
        evaluation_id="eval-1",
        score=85.0,
        recommendation="shortlist",
        model="gemini-2.5-flash",
        agent_version="VERA/1.0.0",
        prompt_versions={"candidate_evaluation": "1.0.0"},
        requires_review=True,
        review_reasons=["score_borderline"],
        cost_usd=0.002,
    )
    uow.flush()

    evento = uow.audit.list(action="evaluation.completed")[0]
    assert evento.model == "gemini-2.5-flash"
    assert evento.agent_version == "VERA/1.0.0"
    assert "candidate_evaluation@1.0.0" in evento.prompt_version
    assert evento.actor_type is ActorType.AI_AGENT


def test_los_incidentes_de_seguridad_se_marcan_aparte(uow: UnitOfWork) -> None:
    servicio = AuditService(uow.audit)
    servicio.record_security_incident(
        actor=Actor.agent(),
        resource_id="app-1",
        incident="prompt_injection_detected",
        severity=Severity.CRITICAL,
    )
    uow.flush()

    criticos = uow.audit.list(severity="critical")
    assert len(criticos) == 1
    assert criticos[0].action == "security.prompt_injection_detected"


def test_la_traza_de_decision_va_en_orden_cronologico(uow: UnitOfWork) -> None:
    for accion in ("application.created", "evaluation.completed", "human_review.decided"):
        uow.audit.append(_evento(accion))
    uow.flush()

    traza = uow.audit.decision_trail("app-1")
    assert [e.action for e in traza] == [
        "application.created", "evaluation.completed", "human_review.decided"
    ]


def test_los_eventos_de_otra_candidatura_no_se_mezclan(uow: UnitOfWork) -> None:
    uow.audit.append(_evento("a", resource_id="app-1"))
    uow.audit.append(_evento("b", resource_id="app-2"))
    uow.flush()

    assert len(uow.audit.decision_trail("app-1")) == 1
    assert len(uow.audit.decision_trail("app-2")) == 1
