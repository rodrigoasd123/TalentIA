"""Siembra la base de datos con los datos ficticios del laboratorio.

Crea usuarios de los cinco roles, las convocatorias, los candidatos con su
consentimiento, los CVs y las candidaturas, además de las plantillas de correo
aprobadas.

Uso:

    python scripts/seed.py              # siembra (no borra lo existente)
    python scripts/seed.py --reset      # borra y vuelve a crear
    python scripts/seed.py --evaluate   # siembra y evalúa todas las candidaturas
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.application.services.audit_service import Actor  # noqa: E402
from app.application.unit_of_work import UnitOfWork  # noqa: E402
from app.application.use_cases.evaluate_application import (  # noqa: E402
    EvaluateApplicationUseCase,
)
from app.application.use_cases.intake import (  # noqa: E402
    CreateApplicationUseCase,
    RegisterCandidateUseCase,
)
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.domain.entities import EmailTemplate, ResumeDocument, User  # noqa: E402
from app.domain.enums import DocumentType, EmailTemplateKind, JobStatus, Role  # noqa: E402
from app.domain.value_objects import EmailAddress  # noqa: E402
from app.infrastructure.database.session import init_database  # noqa: E402
from app.infrastructure.fixtures_loader import load_all_jobs, load_all_resumes  # noqa: E402
from app.infrastructure.security.passwords import hash_password  # noqa: E402

logger = get_logger(__name__)

#: Usuarios de laboratorio. La contraseña es la misma para todos a propósito:
#: es un entorno de pruebas y así se documenta en el README. En cualquier otro
#: entorno, sembrar usuarios con contraseña conocida sería inadmisible.
LAB_PASSWORD = "Laboratorio-TalentIA-2026!"

SEED_USERS = [
    ("admin@talentia-lab.test", "Administración del sistema", Role.ADMIN),
    ("recruiter@talentia-lab.test", "Equipo de selección", Role.RECRUITER),
    ("manager@talentia-lab.test", "Jefatura de contratación", Role.HIRING_MANAGER),
    ("interviewer@talentia-lab.test", "Panel de entrevistas", Role.INTERVIEWER),
    ("auditor@talentia-lab.test", "Auditoría interna", Role.AUDITOR),
]

#: Plantillas aprobadas. El modelo solo rellena las variables declaradas en
#: `allowed_variables`; el resto del texto es fijo y lo aprueba una persona.
SEED_TEMPLATES = [
    EmailTemplate(
        code="acuse_recibo",
        kind=EmailTemplateKind.RECEIPT_CONFIRMATION,
        subject_template="Hemos recibido tu candidatura — {job_title}",
        body_template=(
            "Hola:\n\n"
            "Confirmamos la recepción de tu candidatura para el puesto de "
            "{job_title}.\n\n"
            "{mensaje_personalizado}\n\n"
            "Te escribiremos en cuanto tengamos novedades sobre el proceso.\n\n"
            "Un saludo,\n"
            "Equipo de Selección"
        ),
        allowed_variables=["mensaje_personalizado"],
        approved=True,
        requires_human_approval=False,
    ),
    EmailTemplate(
        code="preseleccionado",
        kind=EmailTemplateKind.SHORTLISTED,
        subject_template="Tu candidatura avanza — {job_title}",
        body_template=(
            "Hola:\n\n"
            "Tu candidatura para {job_title} ha pasado a la siguiente fase del "
            "proceso.\n\n"
            "{mensaje_personalizado}\n\n"
            "Nos pondremos en contacto contigo para coordinar los siguientes pasos.\n\n"
            "Un saludo,\n"
            "Equipo de Selección"
        ),
        allowed_variables=["mensaje_personalizado"],
        approved=True,
        requires_human_approval=True,
    ),
    EmailTemplate(
        code="rechazo",
        kind=EmailTemplateKind.REJECTION,
        subject_template="Resolución de tu candidatura — {job_title}",
        body_template=(
            "Hola:\n\n"
            "Gracias por tu interés en el puesto de {job_title} y por el tiempo "
            "que has dedicado a este proceso.\n\n"
            "En esta ocasión hemos decidido continuar con otras candidaturas cuyo "
            "perfil se ajusta más a los requisitos de la posición.\n\n"
            "{mensaje_personalizado}\n\n"
            "Si lo deseas, podemos conservar tu candidatura para futuras "
            "convocatorias. Puedes solicitar información sobre esta decisión "
            "respondiendo a este correo.\n\n"
            "Un saludo,\n"
            "Equipo de Selección"
        ),
        allowed_variables=["mensaje_personalizado"],
        approved=True,
        requires_human_approval=True,
    ),
    EmailTemplate(
        code="invitacion_entrevista",
        kind=EmailTemplateKind.INTERVIEW_INVITATION,
        subject_template="Invitación a entrevista — {job_title}",
        body_template=(
            "Hola:\n\n"
            "Nos gustaría avanzar contigo en el proceso para {job_title} e "
            "invitarte a una entrevista.\n\n"
            "{detalles_entrevista}\n\n"
            "{mensaje_personalizado}\n\n"
            "Confírmanos tu disponibilidad respondiendo a este correo.\n\n"
            "Un saludo,\n"
            "Equipo de Selección"
        ),
        allowed_variables=["detalles_entrevista", "mensaje_personalizado"],
        approved=True,
        requires_human_approval=True,
    ),
]


def seed_users(uow: UnitOfWork) -> int:
    created = 0
    password_hash = hash_password(LAB_PASSWORD)
    for email, name, role in SEED_USERS:
        if uow.users.get_by_email(email) is not None:
            continue
        uow.users.add(
            User(
                email=EmailAddress(value=email),
                full_name=name,
                role=role,
                password_hash=password_hash,
            )
        )
        created += 1
    return created


def seed_templates(uow: UnitOfWork) -> int:
    created = 0
    for template in SEED_TEMPLATES:
        if uow.templates.get_by_code(template.code) is not None:
            continue
        uow.templates.add(template)
        created += 1
    return created


def seed_jobs(uow: UnitOfWork) -> list:
    jobs = []
    for job in load_all_jobs():
        existing = uow.jobs.get_by_code(job.code)
        if existing is not None:
            jobs.append(existing)
            continue
        job.status = JobStatus.OPEN
        jobs.append(uow.jobs.add(job))
    return jobs


def seed_candidates(uow: UnitOfWork, jobs: list, actor: Actor) -> dict[str, int]:
    """Registra candidatos y crea candidaturas repartidas entre las vacantes.

    El reparto no es aleatorio: cada CV se asigna a la vacante para la que fue
    diseñado, más una vacante secundaria para poder comparar cómo puntúa el mismo
    perfil en contextos distintos.
    """
    register = RegisterCandidateUseCase(uow)
    create = CreateApplicationUseCase(uow)
    by_code = {j.code: j for j in jobs}

    #: CV → vacantes a las que se presenta.
    assignments: dict[str, list[str]] = {
        "CV-001": ["VAC-001"],
        "CV-002": ["VAC-001"],
        "CV-003": ["VAC-002", "VAC-001"],
        "CV-004": ["VAC-004"],
        "CV-005": ["VAC-003"],
        "CV-006": ["VAC-001"],
        "CV-007": ["VAC-001"],
        "CV-008": ["VAC-002"],
        "CV-009": ["VAC-001"],
    }

    stats = {"candidates": 0, "resumes": 0, "applications": 0}

    for fixture in load_all_resumes():
        prefix = fixture.code.split("-")[0] + "-" + fixture.code.split("-")[1]
        targets = assignments.get(prefix, ["VAC-001"])

        result = register.execute(
            full_name=fixture.full_name,
            email=fixture.email,
            source="fixture",
            consent_granted=True,
            actor=actor,
        )
        if not result.was_existing:
            stats["candidates"] += 1

        resumes = uow.resumes.list_for_candidate(result.candidate.id)
        if resumes:
            resume = resumes[0]
        else:
            # Las fixtures son Markdown y ya vienen como texto, así que se
            # registran directamente sin pasar por el extractor de ficheros.
            resume = uow.resumes.add(
                ResumeDocument(
                    candidate_id=result.candidate.id,
                    filename=f"{fixture.code}.md",
                    document_type=DocumentType.MARKDOWN,
                    content_hash=f"fixture:{fixture.code}",
                    raw_text=fixture.text,
                    char_count=len(fixture.text),
                    resume_version=1,
                )
            )
            stats["resumes"] += 1

        for code in targets:
            job = by_code.get(code)
            if job is None:
                continue
            try:
                create.execute(
                    candidate_id=result.candidate.id,
                    job_id=job.id,
                    resume_id=resume.id,
                    source="fixture",
                    actor=actor,
                )
                stats["applications"] += 1
            except Exception as exc:  # noqa: BLE001 — duplicado esperado al resembrar
                logger.debug("Candidatura omitida", reason=str(exc)[:120])
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Siembra el laboratorio de TalentIA")
    parser.add_argument("--reset", action="store_true", help="Borra y recrea el esquema")
    parser.add_argument("--evaluate", action="store_true", help="Evalúa las candidaturas")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    configure_logging("INFO" if args.verbose else "WARNING", as_json=False)
    init_database(drop_all=args.reset)

    actor = Actor.system()

    with UnitOfWork() as uow:
        users = seed_users(uow)
        templates = seed_templates(uow)
        jobs = seed_jobs(uow)
        stats = seed_candidates(uow, jobs, actor)

    print("\n  Siembra completada")
    print(f"  {'Usuarios':<16} {users} creados")
    print(f"  {'Plantillas':<16} {templates} creadas")
    print(f"  {'Vacantes':<16} {len(jobs)}")
    print(f"  {'Candidatos':<16} {stats['candidates']} nuevos")
    print(f"  {'CVs':<16} {stats['resumes']}")
    print(f"  {'Candidaturas':<16} {stats['applications']}")
    print(f"\n  Acceso de laboratorio: recruiter@talentia-lab.test / {LAB_PASSWORD}")

    if args.evaluate:
        print("\n  Evaluando candidaturas…")
        evaluated = failed = 0
        with UnitOfWork() as uow:
            pending = uow.applications.list_all()
        for application in pending:
            try:
                with UnitOfWork() as uow:
                    use_case = EvaluateApplicationUseCase(uow)
                    outcome = use_case.execute(
                        application_id=application.id, actor=actor, dry_run=False
                    )
                evaluated += 1
                score = outcome.summary["score"]
                print(
                    f"    {application.id[:8]}  {score:6.2f}  "
                    f"{outcome.summary['recommendation']:<10} → "
                    f"{outcome.summary['status']}"
                )
            except Exception as exc:  # noqa: BLE001 — se informa y se continúa
                failed += 1
                print(f"    {application.id[:8]}  ERROR: {str(exc)[:80]}")
        print(f"\n  {evaluated} evaluadas, {failed} con error")

        with UnitOfWork() as uow:
            ok, broken = uow.audit.verify_chain()
            print(f"  Cadena de auditoría íntegra: {ok}" + (f" (roto en {broken})" if broken else ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
