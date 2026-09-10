"""Fixtures compartidas de la suite de pruebas."""

from __future__ import annotations

import os

import pytest

# La configuración se lee al importar, así que el entorno debe fijarse antes.
os.environ.setdefault("VERA_ENVIRONMENT", "testing")
os.environ.setdefault("VERA_SECRET_KEY", "clave-de-pruebas-no-usar-en-produccion-0123456789")
# Al menos 32 bytes: la validación de configuración lo exige fuera de desarrollo,
# y el entorno de pruebas no es una excepción. Un secreto corto en los tests
# acabaría normalizando la práctica.
os.environ.setdefault(
    "VERA_JWT_SECRET", "jwt-de-pruebas-no-usar-en-produccion-0123456789abcdef"
)
os.environ.setdefault("VERA_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VERA_LOG_LEVEL", "ERROR")

from app.ai.agent import EvaluationRequest, VeraAgent  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.domain.entities import JobRequirements, ResumeExtraction  # noqa: E402
from app.domain.enums import FilterOperator, LanguageLevel, ScoringDimension  # noqa: E402
from app.domain.value_objects import HardFilter, LanguageSkill, ScoringWeights  # noqa: E402
from app.infrastructure.llm.mock_adapter import MockLLMAdapter  # noqa: E402

configure_logging("ERROR", as_json=False)


CV_LIMPIO = """
# Ana Lucía Ramírez Ochoa

Correo: ana.ramirez@example.test
Teléfono: +00 000 000 000

Ingeniera de software con 7 años de experiencia en desarrollo backend.

## Experiencia

Senior Backend Engineer en Fintech Andina (2021 - actualidad)
Desarrollé microservicios en Python con FastAPI sobre PostgreSQL.
Implementé pipelines de CI/CD con Docker desplegados en AWS.

Backend Developer en Retail Digital (2019 - 2021)
Desarrollo de APIs REST en Python con Django sobre PostgreSQL.

## Formación

Ingeniería de Sistemas, graduación 2018.

## Idiomas

Español nativo, inglés C1.
"""


@pytest.fixture
def cv_limpio() -> str:
    return CV_LIMPIO


@pytest.fixture
def requisitos() -> JobRequirements:
    return JobRequirements(
        hard_filters=[
            HardFilter(
                field="years_experience", operator=FilterOperator.GTE, value=5,
                label="Mínimo 5 años", legal_basis="El puesto exige autonomía técnica",
            ),
            HardFilter(
                field="skills", operator=FilterOperator.CONTAINS_ALL,
                value=["python", "postgresql"], label="Python y PostgreSQL",
                legal_basis="Stack de la plataforma",
            ),
        ],
        weights=ScoringWeights(
            weights={
                ScoringDimension.TECHNICAL: 40.0,
                ScoringDimension.EXPERIENCE: 30.0,
                ScoringDimension.SEMANTIC: 30.0,
            }
        ),
        minimum_score=70.0,
        review_threshold=5.0,
        mandatory_skills=["python", "postgresql", "fastapi"],
        min_years_experience=5.0,
        languages=[LanguageSkill(language="english", level=LanguageLevel.B2)],
    )


@pytest.fixture
def extraccion() -> ResumeExtraction:
    return ResumeExtraction(
        total_years_experience=7.0,
        seniority="senior",
        skills=["python", "fastapi", "postgresql", "docker"],
        technologies=["aws", "redis"],
        languages=[LanguageSkill(language="english", level=LanguageLevel.C1)],
        certifications=["AWS Certified Solutions Architect"],
        field_confidence={"skills": 0.9, "total_years_experience": 0.9},
    )


@pytest.fixture
def agente() -> VeraAgent:
    return VeraAgent(MockLLMAdapter(), prefer_langgraph=False)


@pytest.fixture
def peticion(cv_limpio: str, requisitos: JobRequirements) -> EvaluationRequest:
    return EvaluationRequest(
        application_id="test-app",
        candidate_id="test-cand",
        job_id="test-job",
        resume_id="test-resume",
        resume_text=cv_limpio,
        candidate_name="Ana Lucía Ramírez Ochoa",
        candidate_email="ana.ramirez@example.test",
        requirements=requisitos,
        job_title="Backend Senior",
        job_description="Desarrollo backend en Python",
    )
