"""Carga de las bases de convocatoria y los CVs ficticios del laboratorio.

Las convocatorias se declaran en YAML y se traducen a entidades de dominio. Es el
mismo camino que seguiría una vacante creada desde la interfaz, así que sirve
también como comprobación de que la estructura declarativa de criterios es
suficientemente expresiva.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import FIXTURES_DIR
from app.core.logging import get_logger
from app.domain.entities import Job, JobRequirements
from app.domain.enums import (
    FilterOperator,
    JobStatus,
    LanguageLevel,
    ScoringDimension,
)
from app.domain.value_objects import HardFilter, LanguageSkill, ScoringWeights

logger = get_logger(__name__)

CONVOCATORIAS_DIR = FIXTURES_DIR / "convocatorias"
CVS_DIR = FIXTURES_DIR / "cvs"

#: Los ficheros de fixtures llevan un comentario HTML de cabecera que explica su
#: propósito. Es documentación para quien lee el repositorio, no contenido del CV,
#: así que se retira antes de procesarlo.
_HEADER_COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)


@dataclass(slots=True)
class ResumeFixture:
    """Un CV ficticio, con los datos de contacto ya identificados."""

    code: str
    path: Path
    full_name: str
    email: str
    text: str
    purpose: str = ""

    @property
    def is_security_fixture(self) -> bool:
        return "INYECCION" in self.code.upper() or "PII" in self.code.upper()


def load_job_from_yaml(path: Path) -> Job:
    """Construye una vacante de dominio a partir de su fichero de criterios."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw = data.get("requirements", {})

    weights = ScoringWeights(
        weights={
            ScoringDimension(name): float(value)
            for name, value in raw.get("weights", {}).items()
        }
    )

    hard_filters = [
        HardFilter(
            field=item["field"],
            operator=FilterOperator(item["operator"]),
            value=item["value"],
            label=item["label"],
            mandatory=bool(item.get("mandatory", True)),
            legal_basis=item["legal_basis"],
        )
        for item in raw.get("hard_filters", [])
    ]

    languages = [
        LanguageSkill(language=item["language"], level=LanguageLevel(item["level"]))
        for item in raw.get("languages", [])
    ]

    requirements = JobRequirements(
        version=int(raw.get("version", 1)),
        hard_filters=hard_filters,
        weights=weights,
        minimum_score=float(raw.get("minimum_score", 70.0)),
        review_threshold=float(raw.get("review_threshold", 5.0)),
        mandatory_skills=list(raw.get("mandatory_skills", [])),
        optional_skills=list(raw.get("optional_skills", [])),
        min_years_experience=float(raw.get("min_years_experience", 0.0)),
        education_level=str(raw.get("education_level", "")),
        languages=languages,
        certifications=list(raw.get("certifications", [])),
    )

    return Job(
        code=data["code"],
        title=data["title"],
        description=str(data.get("description", "")).strip(),
        department=str(data.get("department", "")),
        location=str(data.get("location", "")),
        employment_type=str(data.get("employment_type", "full_time")),
        status=JobStatus(str(data.get("status", "draft"))),
        requirements=requirements,
        salary_min=data.get("salary_min"),
        salary_max=data.get("salary_max"),
        currency=str(data.get("currency", "USD")),
    )


def load_all_jobs() -> list[Job]:
    """Todas las convocatorias del laboratorio, ordenadas por código."""
    if not CONVOCATORIAS_DIR.exists():
        logger.warning("No existe el directorio de convocatorias", path=str(CONVOCATORIAS_DIR))
        return []
    jobs = [load_job_from_yaml(path) for path in sorted(CONVOCATORIAS_DIR.glob("*.yaml"))]
    logger.info("Convocatorias cargadas", count=len(jobs))
    return jobs


def job_brief_markdown(code: str) -> str:
    """Devuelve las bases de convocatoria en su versión legible."""
    matches = list(CONVOCATORIAS_DIR.glob(f"{code}*.md"))
    return matches[0].read_text(encoding="utf-8") if matches else ""


def load_resume_fixture(path: Path) -> ResumeFixture:
    """Lee un CV ficticio y extrae de él el nombre y el correo.

    El nombre y el correo se necesitan por separado porque el sanitizador de PII
    los usa para verificar que no sobrevivieron a la anonimización.
    """
    raw = path.read_text(encoding="utf-8")

    purpose = ""
    header = _HEADER_COMMENT.search(raw)
    if header:
        purpose = _extract_purpose(header.group(0))
    body = _HEADER_COMMENT.sub("", raw, count=1).strip()

    name_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    full_name = name_match.group(1).strip() if name_match else path.stem

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]{2,}", body)
    email = email_match.group(0) if email_match else f"{path.stem}@ejemplo-correo.pe"

    return ResumeFixture(
        code=path.stem,
        path=path,
        full_name=full_name,
        email=email,
        text=body,
        purpose=purpose,
    )


def load_all_resumes() -> list[ResumeFixture]:
    if not CVS_DIR.exists():
        logger.warning("No existe el directorio de CVs", path=str(CVS_DIR))
        return []
    resumes = [load_resume_fixture(path) for path in sorted(CVS_DIR.glob("*.md"))]
    logger.info("CVs ficticios cargados", count=len(resumes))
    return resumes


def _extract_purpose(comment: str) -> str:
    match = re.search(r"Propósito de esta pieza:\s*(.+?)(?:\n\n|-->)", comment, re.DOTALL)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    if "PRUEBA DE SEGURIDAD" in comment:
        return "Pieza de prueba de seguridad: contiene intentos de manipulación del sistema."
    if "PRUEBA DE PRIVACIDAD" in comment:
        return "Pieza de prueba de privacidad: contiene abundante información personal."
    return ""


__all__ = [
    "CONVOCATORIAS_DIR", "CVS_DIR", "ResumeFixture", "job_brief_markdown",
    "load_all_jobs", "load_all_resumes", "load_job_from_yaml", "load_resume_fixture",
]
