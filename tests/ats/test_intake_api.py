from __future__ import annotations

import io

import docx
import pytest
from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.infrastructure.database.session import reset_engine


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("VERA_DATABASE_URL", f"sqlite:///{tmp_path / 'intake.db'}")
    monkeypatch.setenv("VERA_ENVIRONMENT", "development")
    reset_settings_cache()
    reset_engine()
    from app.api.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    reset_settings_cache()


def _docx_bytes() -> bytes:
    document = docx.Document()
    document.add_heading("CV ficticio de prueba", level=1)
    document.add_paragraph(
        "Analista con cinco años de experiencia en Python, SQL, automatización, "
        "integración de datos y elaboración de reportes para equipos de negocio."
    )
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_alta_completa_crea_vacante_candidato_cv_y_candidatura(client: TestClient) -> None:
    job = client.post(
        "/api/v1/jobs",
        json={
            "code": "LAB-001",
            "title": "Analista de datos",
            "description": "Vacante ficticia",
            "mandatory_skills": ["python", "sql"],
            "criteria_approved": True,
        },
    )
    assert job.status_code == 201
    assert job.json()["status"] == "open"

    response = client.post(
        "/api/v1/intake",
        data={
            "full_name": "Persona Ficticia",
            "email": "persona@example.test",
            "job_id": job.json()["id"],
            "consent_granted": "true",
            "source": "manual",
        },
        files={
            "resume": (
                "cv-ficticio.docx",
                _docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["candidate_id"]
    assert payload["resume_id"]
    assert payload["application_id"]

    applications = client.get("/api/v1/applications")
    assert applications.status_code == 200
    assert any(item["id"] == payload["application_id"] for item in applications.json())


def test_ingesta_rechaza_falta_de_consentimiento(client: TestClient) -> None:
    job = client.post(
        "/api/v1/jobs",
        json={"code": "LAB-002", "title": "Vacante ficticia", "criteria_approved": True},
    ).json()
    response = client.post(
        "/api/v1/intake",
        data={
            "full_name": "Persona Sin Consentimiento",
            "email": "sin-consentimiento@example.test",
            "job_id": job["id"],
            "consent_granted": "false",
        },
        files={"resume": ("cv.docx", _docx_bytes(), "application/octet-stream")},
    )
    assert response.status_code == 422, response.text
    assert "consentimiento" in response.text.lower()


def test_editar_criterios_reabre_solo_con_aprobacion_humana(client: TestClient) -> None:
    job = client.post(
        "/api/v1/jobs",
        json={"code": "LAB-003", "title": "Vacante editable", "criteria_approved": True},
    ).json()
    edited = client.patch(
        f"/api/v1/jobs/{job['id']}", json={"mandatory_skills": ["python"]}
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"
    approved = client.patch(
        f"/api/v1/jobs/{job['id']}", json={"criteria_approved": True}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "open"


def test_sourcing_solo_devuelve_una_consulta_para_ejecucion_manual(client: TestClient) -> None:
    job = client.post(
        "/api/v1/jobs",
        json={"code": "LAB-004", "title": "Data Engineer", "mandatory_skills": ["python", "sql"], "criteria_approved": True},
    ).json()
    response = client.get(f"/api/v1/jobs/{job['id']}/sourcing-query")
    assert response.status_code == 200
    assert response.json()["execution"] == "manual"
    assert response.json()["opens_linkedin"] is False
    assert '"python"' in response.json()["boolean_query"]