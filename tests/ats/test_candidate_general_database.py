from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.schemas import CandidateCreateRequest
from app.application.services.analytics_service import AnalyticsService
from app.application.unit_of_work import UnitOfWork
from app.core.config import reset_settings_cache
from app.domain.entities import Application, Candidate, Job
from app.domain.enums import ApplicationStatus, CandidateStatus
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import reset_engine


@pytest.fixture
def uow() -> UnitOfWork:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return UnitOfWork(session)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    monkeypatch.setenv("VERA_DATABASE_URL", f"sqlite:///{tmp_path / 'candidates.db'}")
    monkeypatch.setenv("VERA_ENVIRONMENT", "development")
    reset_settings_cache()
    reset_engine()
    from app.api.main import app

    with TestClient(app) as client:
        yield client
    reset_engine()
    reset_settings_cache()


def test_candidate_general_fields_round_trip_and_age(uow: UnitOfWork) -> None:
    candidate = Candidate(
        full_name="Ana Ejemplo",
        client="Cliente Uno",
        candidate_status=CandidateStatus.APTO,
        record_date=date(2026, 9, 10),
        recruiter="Recruiter A",
        source="Adecco Perú",
        q="Q3",
        birth_date=date(1990, 9, 11),
        national_id="12345678",
        bgc="Conforme",
        technical_knowledge="Python, FastAPI y SQLite",
        equifax_debt=125.5,
        salary_expectation=5000,
        requested="Backend Senior",
        role_ctc=5500,
        ctc_variation_pct=10,
        availability="15 días",
        notes="Seguimiento semanal",
    )
    uow.candidates.add(candidate)
    stored = uow.candidates.get(candidate.id)
    assert stored is not None
    assert stored.client == "Cliente Uno"
    assert stored.candidate_status is CandidateStatus.APTO
    assert stored.age == 35
    assert stored.equifax_debt == 125.5


def test_candidate_status_catalog_is_closed() -> None:
    assert {item.value for item in CandidateStatus} == {
        "apto",
        "no_apto",
        "backup",
        "en_proceso",
        "no_contesta",
        "pendiente_contacto",
        "pendiente_envio",
    }
    with pytest.raises(ValueError):
        CandidateCreateRequest(full_name="Ana Ejemplo", candidate_status="inventado")


def test_disposition_report_combines_adecco_interview_and_discard(uow: UnitOfWork) -> None:
    job = Job(code="DEV-001", title="Backend")
    uow.jobs.add(job)
    interviewed = Candidate(
        full_name="Ana Entrevistada",
        source="Adecco Perú",
        candidate_status=CandidateStatus.EN_PROCESO,
    )
    discarded = Candidate(
        full_name="Luis Descartado",
        source="referido",
        candidate_status=CandidateStatus.NO_APTO,
    )
    uow.candidates.add(interviewed)
    uow.candidates.add(discarded)
    uow.applications.add(
        Application(
            candidate_id=interviewed.id,
            job_id=job.id,
            status=ApplicationStatus.INTERVIEWED,
            source="Adecco Perú",
        )
    )

    rows = AnalyticsService(uow).candidate_disposition_report()
    by_name = {row["candidate"]: row for row in rows}
    assert by_name["Ana Entrevistada"]["categories"] == ["adecco", "entrevistado"]
    assert by_name["Luis Descartado"]["categories"] == ["descartado"]
    assert "national_id" not in by_name["Ana Entrevistada"]
    assert "equifax_debt" not in by_name["Ana Entrevistada"]


def test_candidate_api_create_update_and_csv_report(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/candidates",
        json={
            "full_name": "Persona API",
            "client": "Cliente API",
            "candidate_status": "no_apto",
            "source": "Adecco",
            "birth_date": "1995-02-10",
            "national_id": "87654321",
            "bgc": "Conforme",
            "equifax_debt": 50,
            "technical_knowledge": "FastAPI",
            "salary_expectation": 4000,
            "requested": "Developer",
            "role_ctc": 4500,
            "ctc_variation_pct": 12.5,
            "availability": "Inmediata",
            "notes": "Privado",
        },
    )
    assert created.status_code == 201, created.text
    candidate = created.json()
    assert candidate["candidate_status"] == "no_apto"
    assert candidate["age"] == 31

    updated = api_client.patch(
        f"/api/v1/candidates/{candidate['id']}",
        json={
            "expected_version": candidate["version"],
            "candidate_status": "backup",
            "recruiter": "Recruiter API",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["candidate_status"] == "backup"

    report = api_client.get("/api/v1/reports/candidate-disposition")
    assert report.status_code == 200
    assert report.json()["counts"]["adecco"] == 1
    csv_response = api_client.get("/api/v1/reports/candidate-disposition.csv")
    assert csv_response.status_code == 200
    assert "national_id" not in csv_response.text
    assert "equifax_debt" not in csv_response.text
