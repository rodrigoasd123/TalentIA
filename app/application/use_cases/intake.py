"""Casos de uso de ingesta: alta de candidato, carga de CV y candidatura.

Es la puerta de entrada de datos personales al sistema, así que las
comprobaciones se hacen **antes** de guardar nada:

* El consentimiento se exige en el alta, no después. Un candidato registrado sin
  base legal ya es un incumplimiento aunque nunca se le evalúe.
* Los duplicados se detectan y se reportan, pero **no se fusionan solos**: unir
  dos personas por una coincidencia de teléfono es difícil de deshacer.
* La candidatura usa una clave de idempotencia determinista, de modo que pulsar
  dos veces «enviar» no crea dos procesos para la misma persona.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.application.services.audit_service import Actor, AuditService
from app.application.unit_of_work import UnitOfWork
from app.core.config import get_settings
from app.core.exceptions import (
    CandidateNotFound,
    DuplicateApplication,
    JobNotFound,
    ResumeParsingError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domain.entities import Application, Candidate, ResumeDocument
from app.domain.enums import ApplicationStatus, DocumentType, JobStatus, Severity
from app.domain.value_objects import ConsentRecord, EmailAddress
from app.infrastructure.documents.text_extractor import TextExtractor

logger = get_logger(__name__)

#: Retención por defecto de los datos de un candidato no contratado.
DEFAULT_CONSENT_MONTHS = 12


def normalize_recruitment_source(value: str) -> str:
    """Normaliza fuentes conocidas sin impedir nuevas fuentes operativas."""
    cleaned = " ".join((value or "manual").strip().split()) or "manual"
    aliases = {
        "adecco": "Adecco",
        "adecco peru": "Adecco",
        "adecco perú": "Adecco",
        "linkedin": "LinkedIn",
        "linkedin_manual": "LinkedIn",
        "portal tcs": "Portal TCS",
        "referido": "Referido",
        "manual": "Manual",
        "historico": "Importación histórica",
        "histórico": "Importación histórica",
    }
    return aliases.get(cleaned.casefold(), cleaned[:80])


def synchronize_candidate_source(
    uow: UnitOfWork,
    *,
    candidate: Candidate,
    source: str,
    actor: Actor,
) -> int:
    """Sincroniza la fuente maestra y las postulaciones vinculadas."""
    normalized = normalize_recruitment_source(source)
    linked = uow.applications.list_for_candidate(candidate.id)
    changed_applications = 0
    for application in linked:
        if application.source == normalized:
            continue
        application.source = normalized
        application.touch()
        uow.applications.update(application)
        changed_applications += 1
    candidate_changed = candidate.source != normalized
    if candidate_changed:
        candidate.source = normalized
        candidate.touch()
        uow.candidates.update(candidate)
    if candidate_changed or changed_applications:
        AuditService(uow.audit).record(
            action="candidate.source_synchronized",
            actor=actor,
            resource_type="candidate",
            resource_id=candidate.id,
            new_state={
                "source": normalized,
                "applications_updated": changed_applications,
            },
        )
    return changed_applications


@dataclass(slots=True)
class IntakeResult:
    candidate: Candidate
    resume: ResumeDocument | None = None
    application: Application | None = None
    duplicates: list[dict[str, str]] = field(default_factory=list)
    was_existing: bool = False
    warnings: list[str] = field(default_factory=list)


class RegisterCandidateUseCase:
    """Alta de candidato con consentimiento y detección de duplicados."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.audit = AuditService(uow.audit)

    def execute(
        self,
        *,
        full_name: str,
        email: str,
        actor: Actor,
        phone: str = "",
        national_id: str = "",
        location: str = "",
        source: str = "direct",
        consent_granted: bool = False,
        consent_months: int = DEFAULT_CONSENT_MONTHS,
        tags: list[str] | None = None,
    ) -> IntakeResult:
        if not consent_granted:
            raise ValidationError(
                "No se puede registrar a un candidato sin consentimiento explícito "
                "para el tratamiento de sus datos"
            )

        source = normalize_recruitment_source(source)
        address = EmailAddress(value=email)
        existing = self.uow.candidates.get_by_email(str(address))
        if existing is not None:
            # Reutilizar en vez de duplicar. Una persona que aplica a una segunda
            # vacante es la misma persona, no un registro nuevo.
            synchronize_candidate_source(self.uow, candidate=existing, source=source, actor=actor)
            logger.info("Candidato ya registrado; se reutiliza", candidate_id=existing.id)
            return IntakeResult(candidate=existing, was_existing=True)

        candidate = Candidate(
            full_name=full_name.strip(),
            email=address,
            phone=phone.strip(),
            national_id=national_id.strip(),
            location=location.strip(),
            source=source,
            tags=tags or [],
            consent=ConsentRecord(
                purpose="proceso de selección de personal",
                granted_at=date.today(),
                expires_at=date.today() + timedelta(days=30 * consent_months),
            ),
            processing_status="allowed",
            legal_basis_status="consent",
        )

        duplicates = self.uow.candidates.find_potential_duplicates(candidate)
        stored = self.uow.candidates.add(candidate)

        self.audit.record(
            action="candidate.registered",
            actor=actor,
            resource_type="candidate",
            resource_id=stored.id,
            new_state={
                "source": source,
                "consent_expires": stored.consent.expires_at.isoformat()
                if stored.consent
                else None,
            },
            duplicates_found=len(duplicates),
        )

        result = IntakeResult(
            candidate=stored,
            duplicates=[
                {"id": d.id, "name": d.full_name, "email": d.email.masked() if d.email else ""}
                for d in duplicates
            ],
        )
        if duplicates:
            result.warnings.append(
                f"Se encontraron {len(duplicates)} posibles duplicados. "
                "Revísalos antes de continuar; el sistema no los fusiona por su cuenta."
            )
            self.audit.record(
                action="candidate.possible_duplicate",
                actor=actor,
                resource_type="candidate",
                resource_id=stored.id,
                severity=Severity.LOW,
                matches=[d.id for d in duplicates],
            )
        return result


class UploadResumeUseCase:
    """Carga y procesado inicial de un CV.

    La validación por firma binaria y los límites de tamaño están en el
    extractor; aquí se decide qué hacer con lo que devuelve.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.audit = AuditService(uow.audit)
        settings = get_settings()
        self.extractor = TextExtractor(max_bytes=settings.max_upload_mb * 1024 * 1024)

    def execute(
        self, *, candidate_id: str, content: bytes, filename: str, actor: Actor
    ) -> ResumeDocument:
        candidate = self.uow.candidates.get(candidate_id)
        if candidate is None:
            raise CandidateNotFound(f"No existe el candidato {candidate_id}")
        if not candidate.can_be_processed:
            from app.core.exceptions import ConsentMissingOrExpired

            raise ConsentMissingOrExpired("El candidato no tiene consentimiento vigente")

        extracted = self.extractor.extract(content=content, filename=filename)

        if not extracted.extraction_ok:
            # Distinguir «CV vacío» de «no pudimos leerlo» importa: la primera
            # conclusión perjudica al candidato por un problema técnico nuestro.
            raise ResumeParsingError(
                "No se pudo extraer texto suficiente del documento. " + " ".join(extracted.warnings)
            )

        duplicate = self.uow.resumes.get_by_hash(extracted.content_hash)
        if duplicate is not None and duplicate.candidate_id == candidate_id:
            logger.info("CV idéntico ya cargado; se reutiliza", resume_id=duplicate.id)
            return duplicate

        resume = ResumeDocument(
            candidate_id=candidate_id,
            filename=filename,
            document_type=extracted.document_type,
            content_hash=extracted.content_hash,
            raw_text=extracted.text,
            char_count=extracted.char_count,
            resume_version=self.uow.resumes.next_version(candidate_id),
            is_suspicious=extracted.hidden_text_found,
        )
        stored = self.uow.resumes.add(resume)

        if extracted.hidden_text_found:
            self.audit.record(
                action="security.hidden_text_in_document",
                actor=actor,
                resource_type="candidate",
                resource_id=candidate_id,
                severity=Severity.HIGH,
                resume_id=stored.id,
                filename=filename,
            )
            logger.security(
                "Texto oculto detectado en el documento",
                candidate_id=candidate_id,
                resume_id=stored.id,
            )

        self.audit.record(
            action="resume.uploaded",
            actor=actor,
            resource_type="candidate",
            resource_id=candidate_id,
            new_state={
                "resume_id": stored.id,
                "version": stored.resume_version,
                "chars": stored.char_count,
            },
            warnings=extracted.warnings,
        )
        return stored


class CreateApplicationUseCase:
    """Vincula un candidato con una vacante.

    La clave de idempotencia se deriva de candidato + vacante, así que la
    restricción de unicidad de la base de datos impide dos candidaturas activas
    para la misma combinación aunque lleguen dos peticiones simultáneas.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.audit = AuditService(uow.audit)

    def execute(
        self,
        *,
        candidate_id: str,
        job_id: str,
        resume_id: str,
        actor: Actor,
        source: str = "direct",
    ) -> Application:
        candidate = self.uow.candidates.get(candidate_id)
        if candidate is None:
            raise CandidateNotFound(f"No existe el candidato {candidate_id}")

        job = self.uow.jobs.get(job_id)
        if job is None:
            raise JobNotFound(f"No existe la vacante {job_id}")
        if job.status is not JobStatus.OPEN:
            raise ValidationError(
                f"La vacante está en estado «{job.status.value}» y no admite candidaturas"
            )
        if not job.is_accepting_applications:
            raise ValidationError("El plazo de la convocatoria está cerrado")

        key = self.idempotency_key(candidate_id, job_id)
        existing = self.uow.applications.get_by_idempotency_key(key)
        if existing is not None:
            raise DuplicateApplication(
                f"El candidato ya tiene una candidatura en «{job.code}» "
                f"(estado actual: {existing.status.value})"
            )

        application = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            resume_id=resume_id,
            status=ApplicationStatus.NEW,
            source=source,
            idempotency_key=key,
            requirements_version=job.requirements.version,
        )
        stored = self.uow.applications.add(application)

        self.audit.record(
            action="application.created",
            actor=actor,
            resource_type="application",
            resource_id=stored.id,
            new_state={
                "candidate_id": candidate_id,
                "job_id": job_id,
                "job_code": job.code,
                "status": stored.status.value,
            },
        )
        logger.info(
            "Candidatura creada",
            application_id=stored.id,
            job_code=job.code,
            candidate_id=candidate_id,
        )
        return stored

    @staticmethod
    def idempotency_key(candidate_id: str, job_id: str) -> str:
        """Clave determinista: la misma pareja produce siempre la misma clave."""
        return hashlib.sha256(f"{candidate_id}:{job_id}".encode()).hexdigest()[:40]


class IntakePipelineUseCase:
    """Alta completa en un solo paso: candidato, CV y candidatura.

    Es la operación que usa la interfaz. Al ir toda en la misma transacción, un
    fallo al crear la candidatura no deja un candidato registrado a medias.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.register = RegisterCandidateUseCase(uow)
        self.upload = UploadResumeUseCase(uow)
        self.create = CreateApplicationUseCase(uow)

    def execute(
        self,
        *,
        full_name: str,
        email: str,
        job_id: str,
        content: bytes,
        filename: str,
        actor: Actor,
        phone: str = "",
        national_id: str = "",
        source: str = "direct",
        consent_granted: bool = True,
    ) -> IntakeResult:
        source = normalize_recruitment_source(source)
        result = self.register.execute(
            full_name=full_name,
            email=email,
            phone=phone,
            national_id=national_id,
            source=source,
            consent_granted=consent_granted,
            actor=actor,
        )
        result.resume = self.upload.execute(
            candidate_id=result.candidate.id,
            content=content,
            filename=filename,
            actor=actor,
        )
        result.application = self.create.execute(
            candidate_id=result.candidate.id,
            job_id=job_id,
            resume_id=result.resume.id,
            source=source,
            actor=actor,
        )
        return result


__all__ = [
    "DEFAULT_CONSENT_MONTHS",
    "CreateApplicationUseCase",
    "IntakePipelineUseCase",
    "IntakeResult",
    "RegisterCandidateUseCase",
    "UploadResumeUseCase",
    "normalize_recruitment_source",
    "synchronize_candidate_source",
]
