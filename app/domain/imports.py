"""Contratos del dominio para la importación histórica gobernada."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class ImportStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    READY_FOR_REVIEW = "ready_for_review"
    PARTIALLY_VALID = "partially_valid"
    REJECTED = "rejected"
    IMPORTED = "imported"
    CANCELLED = "cancelled"


class RowClassification(StrEnum):
    PENDING = "pending"
    NEW = "new"
    EXACT_DUPLICATE = "exact_duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    ALREADY_IN_PROCESS = "already_in_process"
    RECONTACT_REVIEW = "recontact_review"
    INVALID = "invalid"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class ImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_id)
    tenant_id: str = "default"
    filename: str
    storage_path: str
    checksum: str
    source: str = "historical"
    sheet_name: str = ""
    status: ImportStatus = ImportStatus.UPLOADED
    column_mapping: dict[str, str] = Field(default_factory=dict)
    suggested_mapping: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, int | str | list[str]] = Field(default_factory=dict)
    row_count: int = 0
    created_by: str
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    confirmation_key: str | None = None
    cancellation_reason: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    version: int = 1


class ImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_id)
    batch_id: str
    row_number: int
    raw_data: dict[str, str] = Field(default_factory=dict)
    normalized_data: dict[str, str] = Field(default_factory=dict)
    classification: RowClassification = RowClassification.PENDING
    errors: list[dict[str, str]] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    candidate_id: str | None = None
    application_id: str | None = None


class MappingTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_id)
    tenant_id: str = "default"
    name: str
    source: str = "historical"
    column_mapping: dict[str, str]
    created_by: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    version: int = 1


__all__ = [
    "ImportBatch", "ImportRow", "ImportStatus", "MappingTemplate",
    "RowClassification",
]
