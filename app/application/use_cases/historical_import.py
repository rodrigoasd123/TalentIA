"""Casos de uso de SPEC-005: staging, validación y confirmación humana."""

from __future__ import annotations

import hashlib
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.application.services.audit_service import Actor, AuditService
from app.application.unit_of_work import UnitOfWork
from app.core.config import get_settings
from app.core.exceptions import InvalidStateTransition, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.entities import Application, Candidate
from app.domain.enums import ApplicationStatus, JobStatus
from app.domain.imports import (
    ImportBatch,
    ImportRow,
    ImportStatus,
    MappingTemplate,
    RowClassification,
)
from app.domain.value_objects import EmailAddress
from app.infrastructure.imports.tabular_reader import CANONICAL_FIELDS, TabularReader

logger = get_logger(__name__)


def _digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


class HistoricalImportUseCase:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.audit = AuditService(uow.audit)
        settings = get_settings()
        self.reader = TabularReader(
            max_bytes=settings.import_max_file_mb * 1024 * 1024,
            max_rows=settings.import_max_rows,
        )
        self.storage = settings.import_storage_path

    def upload(
        self, *, content: bytes, filename: str, source: str, actor: Actor,
        sheet_name: str = "",
    ) -> tuple[ImportBatch, bool]:
        started_at = time.perf_counter()
        checksum = hashlib.sha256(content).hexdigest()
        existing = self.uow.imports.find_by_checksum(checksum)
        if existing:
            logger.info(
                "Lote de importación reutilizado",
                batch_id=existing.id,
                row_count=existing.row_count,
                status=existing.status.value,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
            return existing, True
        parsed = self.reader.read(content, filename, sheet_name=sheet_name)
        safe_suffix = Path(filename).suffix.lower()
        batch = ImportBatch(
            filename=Path(filename).name[:255], storage_path="", checksum=checksum,
            source=(source.strip() or "historical")[:120], sheet_name=parsed.sheet_name,
            created_by=actor.actor_id, row_count=len(parsed.rows),
            suggested_mapping=self.reader.suggest_mapping(parsed.headers),
            summary={"headers": parsed.headers, "sheet_names": parsed.sheet_names or []},
        )
        target = self.storage / f"{batch.id}{safe_suffix}"
        target.write_bytes(content)
        batch.storage_path = str(target)
        self.uow.imports.add_batch(batch)
        self.uow.imports.replace_rows(batch.id, [
            ImportRow(batch_id=batch.id, row_number=index, raw_data=row)
            for index, row in enumerate(parsed.rows, start=2)
        ])
        self.audit.record(
            action="import.uploaded", actor=actor, resource_type="import_batch",
            resource_id=batch.id, new_state={"status": batch.status.value},
            row_count=batch.row_count, source=batch.source,
        )
        logger.info(
            "Lote de importación cargado",
            batch_id=batch.id,
            row_count=batch.row_count,
            status=batch.status.value,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return batch, False

    def validate(
        self, *, batch_id: str, mapping: dict[str, str], actor: Actor,
        expected_version: int | None = None, template_name: str = "",
    ) -> ImportBatch:
        started_at = time.perf_counter()
        batch = self._batch(batch_id)
        self._version(batch, expected_version)
        if batch.status in {ImportStatus.IMPORTED, ImportStatus.CANCELLED}:
            raise ValidationError("El lote ya no admite validación")
        unknown = set(mapping) - CANONICAL_FIELDS
        if unknown:
            raise ValidationError(f"Campos canónicos desconocidos: {', '.join(sorted(unknown))}")
        if "full_name" not in mapping or "job_code" not in mapping:
            raise ValidationError("El mapeo debe incluir full_name y job_code")
        if len(set(mapping.values())) != len(mapping):
            raise ValidationError("Una columna de origen no puede mapearse a varios campos")
        rows = self.uow.imports.list_rows(batch_id, limit=batch.row_count + 1)
        available = set(rows[0].raw_data) if rows else set()
        if not set(mapping.values()).issubset(available):
            raise ValidationError("El mapeo referencia columnas que no existen")

        batch.status = ImportStatus.VALIDATING
        batch.column_mapping = mapping
        for row in rows:
            self._classify(row, mapping)
            self.uow.imports.update_row(row)

        counts = Counter(row.classification.value for row in rows)
        batch.summary = {**batch.summary, "total": len(rows), **dict(counts)}
        blockers = (
            counts[RowClassification.INVALID.value]
            + counts[RowClassification.MANUAL_REVIEW_REQUIRED.value]
            + counts[RowClassification.POSSIBLE_DUPLICATE.value]
        )
        actionable = (
            counts[RowClassification.NEW.value]
            + counts[RowClassification.EXACT_DUPLICATE.value]
        )
        if actionable == 0 and blockers:
            batch.status = ImportStatus.REJECTED
        elif blockers:
            batch.status = ImportStatus.PARTIALLY_VALID
        else:
            batch.status = ImportStatus.READY_FOR_REVIEW
        batch.version += 1
        batch.updated_at = datetime.now(UTC)
        self.uow.imports.update_batch(batch)
        if template_name.strip():
            self.uow.imports.save_template(MappingTemplate(
                name=template_name.strip()[:120], source=batch.source,
                column_mapping=mapping, created_by=actor.actor_id,
            ))
        self.audit.record(
            action="import.validated", actor=actor, resource_type="import_batch",
            resource_id=batch.id, new_state={"status": batch.status.value},
            counts=dict(counts),
        )
        logger.info(
            "Lote de importación validado",
            batch_id=batch.id,
            row_count=batch.row_count,
            status=batch.status.value,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return batch

    def select_sheet(
        self,
        *,
        batch_id: str,
        sheet_name: str,
        actor: Actor,
        expected_version: int | None = None,
    ) -> ImportBatch:
        batch = self._batch(batch_id)
        self._version(batch, expected_version)
        if batch.status in {ImportStatus.IMPORTED, ImportStatus.CANCELLED}:
            raise ValidationError("El lote ya no admite cambiar de hoja")
        try:
            content = Path(batch.storage_path).read_bytes()
        except OSError as exc:
            raise ValidationError("No se pudo recuperar el archivo del lote") from exc
        parsed = self.reader.read(content, batch.filename, sheet_name=sheet_name)
        self.uow.imports.replace_rows(
            batch.id,
            [
                ImportRow(batch_id=batch.id, row_number=index, raw_data=row)
                for index, row in enumerate(parsed.rows, start=2)
            ],
        )
        batch.sheet_name = parsed.sheet_name
        batch.row_count = len(parsed.rows)
        batch.status = ImportStatus.UPLOADED
        batch.column_mapping = {}
        batch.suggested_mapping = self.reader.suggest_mapping(parsed.headers)
        batch.summary = {
            "headers": parsed.headers,
            "sheet_names": parsed.sheet_names or [],
        }
        batch.version += 1
        batch.updated_at = datetime.now(UTC)
        self.uow.imports.update_batch(batch)
        self.audit.record(
            action="import.sheet_selected",
            actor=actor,
            resource_type="import_batch",
            resource_id=batch.id,
            new_state={"status": batch.status.value},
            sheet_name=batch.sheet_name,
            row_count=batch.row_count,
        )
        return batch

    def confirm(
        self, *, batch_id: str, confirmation_key: str, actor: Actor,
        expected_version: int | None = None,
    ) -> ImportBatch:
        started_at = time.perf_counter()
        if not confirmation_key.strip():
            raise ValidationError("La clave de idempotencia es obligatoria")
        prior = self.uow.imports.find_by_confirmation_key(confirmation_key.strip())
        if prior:
            return prior
        batch = self._batch(batch_id)
        self._version(batch, expected_version)
        if batch.status not in {ImportStatus.READY_FOR_REVIEW, ImportStatus.PARTIALLY_VALID}:
            raise ValidationError("El lote no está listo para confirmación")
        rows = self.uow.imports.list_rows(
            batch_id, limit=batch.row_count + 1,
            classifications={RowClassification.NEW, RowClassification.EXACT_DUPLICATE},
        )
        created_candidates = created_applications = reused_candidates = 0
        for row in rows:
            data = row.normalized_data
            job = self.uow.jobs.get_by_code(data["job_code"])
            if job is None or job.status is not JobStatus.OPEN:
                raise ValidationError(
                    "Una vacante dejó de estar disponible durante la confirmación"
                )
            candidate = self.uow.candidates.get(row.candidate_id) if row.candidate_id else None
            if candidate:
                reused_candidates += 1
            else:
                email = EmailAddress(value=data["email"]) if data.get("email") else None
                candidate = Candidate(
                    full_name=data["full_name"], email=email, phone=data.get("phone", ""),
                    national_id=data.get("national_id", ""), location=data.get("location", ""),
                    source=data.get("source") or batch.source,
                    processing_status="restricted_review", legal_basis_status="unknown",
                    tags=["historical_import", "restricted_review"],
                )
                self.uow.candidates.add(candidate)
                created_candidates += 1
            key = hashlib.sha256(f"{candidate.id}:{job.id}".encode()).hexdigest()[:40]
            existing_app = self.uow.applications.get_by_idempotency_key(key)
            if existing_app:
                row.application_id = existing_app.id
            else:
                application = Application(
                    candidate_id=candidate.id, job_id=job.id, resume_id=None,
                    status=ApplicationStatus.NEW, source=data.get("source") or batch.source,
                    idempotency_key=key, requirements_version=job.requirements.version,
                )
                self.uow.applications.add(application)
                row.application_id = application.id
                created_applications += 1
            row.candidate_id = candidate.id
            self.uow.imports.update_row(row)

        batch.status = ImportStatus.IMPORTED
        batch.confirmed_by = actor.actor_id
        batch.confirmed_at = datetime.now(UTC)
        batch.confirmation_key = confirmation_key.strip()[:80]
        batch.version += 1
        batch.updated_at = datetime.now(UTC)
        batch.summary = {
            **batch.summary, "created_candidates": created_candidates,
            "reused_candidates": reused_candidates,
            "created_applications": created_applications,
        }
        self.uow.imports.update_batch(batch)
        self.audit.record(
            action="import.confirmed", actor=actor, resource_type="import_batch",
            resource_id=batch.id, new_state={"status": batch.status.value},
            human_approval_by=actor.actor_id, created_candidates=created_candidates,
            reused_candidates=reused_candidates, created_applications=created_applications,
        )
        logger.info(
            "Lote de importación confirmado",
            batch_id=batch.id,
            row_count=batch.row_count,
            status=batch.status.value,
            created_candidates=created_candidates,
            created_applications=created_applications,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return batch

    def cancel(self, *, batch_id: str, reason: str, actor: Actor) -> ImportBatch:
        batch = self._batch(batch_id)
        if batch.status is ImportStatus.IMPORTED:
            raise ValidationError("Un lote importado no puede cancelarse")
        if not reason.strip():
            raise ValidationError("La justificación de cancelación es obligatoria")
        previous = batch.status
        batch.status = ImportStatus.CANCELLED
        batch.cancellation_reason = reason.strip()[:500]
        batch.version += 1
        batch.updated_at = datetime.now(UTC)
        self.uow.imports.update_batch(batch)
        self.audit.record(
            action="import.cancelled", actor=actor, resource_type="import_batch",
            resource_id=batch.id, previous_state={"status": previous.value},
            new_state={"status": batch.status.value}, reason=batch.cancellation_reason,
        )
        return batch

    def _classify(  # noqa: C901 - la secuencia explícita mantiene explicables las reglas
        self, row: ImportRow, mapping: dict[str, str]
    ) -> None:
        data = {
            canonical: row.raw_data.get(source, "").strip()
            for canonical, source in mapping.items()
        }
        data["full_name"] = _normalize_name(data.get("full_name", ""))
        data["email"] = _normalize_email(data.get("email", ""))
        data["phone"] = _digits(data.get("phone", ""))
        data["national_id"] = re.sub(r"\W+", "", data.get("national_id", "")).upper()
        data["job_code"] = data.get("job_code", "").strip().upper()
        row.normalized_data = data
        row.errors = []
        row.signals = []
        if len(data["full_name"]) < 2:
            row.errors.append({"field": "full_name", "message": "Nombre obligatorio"})
        job = self.uow.jobs.get_by_code(data["job_code"]) if data["job_code"] else None
        if job is None:
            row.errors.append({"field": "job_code", "message": "Vacante inexistente"})
        elif job.status is not JobStatus.OPEN:
            row.errors.append({"field": "job_code", "message": "Vacante no abierta"})
        if data["email"]:
            try:
                EmailAddress(value=data["email"])
            except Exception:
                row.errors.append({"field": "email", "message": "Correo inválido"})
        if row.errors:
            row.classification = RowClassification.INVALID
            return
        strong = bool(data["national_id"] or data["email"] or len(data["phone"]) >= 8)
        if not strong:
            row.classification = RowClassification.MANUAL_REVIEW_REQUIRED
            row.signals = ["identity:name_only"]
            return
        matches = self.uow.candidates.find_by_strong_identifiers(
            email=data["email"], phone=data["phone"], national_id=data["national_id"]
        )
        if len(matches) > 1:
            row.classification = RowClassification.POSSIBLE_DUPLICATE
            row.signals = ["multiple_strong_identifier_matches"]
            return
        if matches:
            candidate = matches[0]
            row.candidate_id = candidate.id
            row.signals = ["strong_identifier_match"]
            candidate_applications = self.uow.applications.list_for_candidate(candidate.id)
            if any(app.job_id == job.id for app in candidate_applications):
                row.classification = RowClassification.ALREADY_IN_PROCESS
            else:
                row.classification = RowClassification.EXACT_DUPLICATE
            return
        if self.uow.candidates.find_by_normalized_name(data["full_name"]):
            row.classification = RowClassification.POSSIBLE_DUPLICATE
            row.signals = ["normalized_name_match"]
            return
        row.classification = RowClassification.NEW
        row.signals = ["strong_identifier_present"]

    def _batch(self, batch_id: str) -> ImportBatch:
        batch = self.uow.imports.get_batch(batch_id)
        if batch is None:
            raise NotFoundError(f"No existe el lote {batch_id}")
        return batch

    @staticmethod
    def _version(batch: ImportBatch, expected: int | None) -> None:
        if expected is not None and batch.version != expected:
            raise InvalidStateTransition(
                "El lote cambió; actualiza la vista antes de continuar"
            )


__all__ = ["HistoricalImportUseCase"]
