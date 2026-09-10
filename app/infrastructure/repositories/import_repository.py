"""Persistencia SQLAlchemy para lotes, staging y plantillas de importación."""

from __future__ import annotations

from datetime import UTC

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domain.imports import (
    ImportBatch,
    ImportRow,
    ImportStatus,
    MappingTemplate,
    RowClassification,
)
from app.infrastructure.database.models import (
    ImportBatchModel,
    ImportMappingTemplateModel,
    ImportRowModel,
)


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class SqlImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_batch(self, batch: ImportBatch) -> ImportBatch:
        self.session.add(ImportBatchModel(
            id=batch.id, tenant_id=batch.tenant_id, filename=batch.filename,
            storage_path=batch.storage_path, checksum=batch.checksum, source=batch.source,
            sheet_name=batch.sheet_name, status=batch.status.value,
            column_mapping=batch.column_mapping, suggested_mapping=batch.suggested_mapping,
            summary=batch.summary, row_count=batch.row_count, created_by=batch.created_by,
            confirmed_by=batch.confirmed_by, confirmed_at=batch.confirmed_at,
            confirmation_key=batch.confirmation_key,
            cancellation_reason=batch.cancellation_reason,
            created_at=batch.created_at, updated_at=batch.updated_at, version=batch.version,
        ))
        self.session.flush()
        return batch

    def get_batch(self, batch_id: str) -> ImportBatch | None:
        model = self.session.get(ImportBatchModel, batch_id)
        return self._batch(model) if model else None

    def find_by_checksum(self, checksum: str, tenant_id: str = "default") -> ImportBatch | None:
        model = self.session.scalar(select(ImportBatchModel).where(
            ImportBatchModel.tenant_id == tenant_id,
            ImportBatchModel.checksum == checksum,
        ))
        return self._batch(model) if model else None

    def find_by_confirmation_key(self, key: str) -> ImportBatch | None:
        if not key:
            return None
        model = self.session.scalar(select(ImportBatchModel).where(
            ImportBatchModel.confirmation_key == key
        ))
        return self._batch(model) if model else None

    def update_batch(self, batch: ImportBatch) -> ImportBatch:
        model = self.session.get(ImportBatchModel, batch.id)
        if model is None:
            raise ValueError("Lote no encontrado")
        model.sheet_name = batch.sheet_name
        model.status = batch.status.value
        model.column_mapping = batch.column_mapping
        model.suggested_mapping = batch.suggested_mapping
        model.summary = batch.summary
        model.row_count = batch.row_count
        model.confirmed_by = batch.confirmed_by
        model.confirmed_at = batch.confirmed_at
        model.confirmation_key = batch.confirmation_key
        model.cancellation_reason = batch.cancellation_reason
        model.updated_at = batch.updated_at
        model.version = batch.version
        self.session.flush()
        return batch

    def replace_rows(self, batch_id: str, rows: list[ImportRow]) -> None:
        self.session.execute(delete(ImportRowModel).where(ImportRowModel.batch_id == batch_id))
        self.session.add_all([
            ImportRowModel(
                id=row.id, batch_id=row.batch_id, row_number=row.row_number,
                raw_data=row.raw_data, normalized_data=row.normalized_data,
                classification=row.classification.value, errors=row.errors,
                signals=row.signals, candidate_id=row.candidate_id,
                application_id=row.application_id,
            ) for row in rows
        ])
        self.session.flush()

    def update_row(self, row: ImportRow) -> None:
        model = self.session.get(ImportRowModel, row.id)
        if model is None:
            raise ValueError("Fila de importación no encontrada")
        model.normalized_data = row.normalized_data
        model.classification = row.classification.value
        model.errors = row.errors
        model.signals = row.signals
        model.candidate_id = row.candidate_id
        model.application_id = row.application_id

    def list_rows(
        self, batch_id: str, *, offset: int = 0, limit: int = 100,
        classifications: set[RowClassification] | None = None,
    ) -> list[ImportRow]:
        stmt = select(ImportRowModel).where(ImportRowModel.batch_id == batch_id)
        if classifications:
            stmt = stmt.where(ImportRowModel.classification.in_(c.value for c in classifications))
        stmt = stmt.order_by(ImportRowModel.row_number).offset(offset).limit(limit)
        return [self._row(model) for model in self.session.scalars(stmt)]

    def count_rows(self, batch_id: str) -> int:
        return int(self.session.scalar(select(func.count()).select_from(ImportRowModel).where(
            ImportRowModel.batch_id == batch_id
        )) or 0)

    def save_template(self, template: MappingTemplate) -> MappingTemplate:
        self.session.add(ImportMappingTemplateModel(
            id=template.id, tenant_id=template.tenant_id, name=template.name,
            source=template.source, column_mapping=template.column_mapping,
            created_by=template.created_by, created_at=template.created_at,
            updated_at=template.updated_at, version=template.version,
        ))
        self.session.flush()
        return template

    def list_templates(self, source: str | None = None) -> list[MappingTemplate]:
        stmt = select(ImportMappingTemplateModel).order_by(ImportMappingTemplateModel.name)
        if source:
            stmt = stmt.where(ImportMappingTemplateModel.source == source)
        return [self._template(model) for model in self.session.scalars(stmt)]

    @staticmethod
    def _batch(model: ImportBatchModel) -> ImportBatch:
        return ImportBatch(
            id=model.id, tenant_id=model.tenant_id, filename=model.filename,
            storage_path=model.storage_path, checksum=model.checksum, source=model.source,
            sheet_name=model.sheet_name, status=ImportStatus(model.status),
            column_mapping=dict(model.column_mapping or {}),
            suggested_mapping=dict(model.suggested_mapping or {}),
            summary=dict(model.summary or {}), row_count=model.row_count,
            created_by=model.created_by, confirmed_by=model.confirmed_by,
            confirmed_at=_aware(model.confirmed_at) if model.confirmed_at else None,
            confirmation_key=model.confirmation_key,
            cancellation_reason=model.cancellation_reason,
            created_at=_aware(model.created_at), updated_at=_aware(model.updated_at),
            version=model.version,
        )

    @staticmethod
    def _row(model: ImportRowModel) -> ImportRow:
        return ImportRow(
            id=model.id, batch_id=model.batch_id, row_number=model.row_number,
            raw_data=dict(model.raw_data or {}), normalized_data=dict(model.normalized_data or {}),
            classification=RowClassification(model.classification),
            errors=list(model.errors or []), signals=list(model.signals or []),
            candidate_id=model.candidate_id, application_id=model.application_id,
        )

    @staticmethod
    def _template(model: ImportMappingTemplateModel) -> MappingTemplate:
        return MappingTemplate(
            id=model.id, tenant_id=model.tenant_id, name=model.name, source=model.source,
            column_mapping=dict(model.column_mapping or {}), created_by=model.created_by,
            created_at=_aware(model.created_at), updated_at=_aware(model.updated_at),
            version=model.version,
        )


__all__ = ["SqlImportRepository"]
