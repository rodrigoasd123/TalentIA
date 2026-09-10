"""Unidad de trabajo.

Agrupa los repositorios de una operación bajo una única transacción. La razón es
concreta: un caso de uso como «evaluar candidatura» escribe en cuatro tablas —la
evaluación, la candidatura, la ejecución del workflow y la auditoría—. Si falla a
mitad, o se aplican las cuatro o ninguna. Cualquier resultado intermedio deja el
sistema contando una historia que no ocurrió.

Se usa como gestor de contexto: confirma al salir bien y revierte al fallar. Que
sea automático evita el olvido, que es la forma habitual en que este patrón
falla en la práctica.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.repositories.sqlalchemy_repos import (
    SqlApplicationRepository,
    SqlAuditRepository,
    SqlCandidateRepository,
    SqlEmailRepository,
    SqlEvaluationRepository,
    SqlJobRepository,
    SqlResumeRepository,
    SqlReviewRepository,
    SqlTemplateRepository,
    SqlUserRepository,
    SqlWorkflowRepository,
)
from app.infrastructure.settings_store import SettingsStore

logger = get_logger(__name__)


class UnitOfWork:
    """Transacción con todos los repositorios de la operación."""

    def __init__(self, session: Session | None = None) -> None:
        self._external_session = session is not None
        self.session = session or get_session_factory()()
        self._bind_repositories()

    def _bind_repositories(self) -> None:
        self.users = SqlUserRepository(self.session)
        self.jobs = SqlJobRepository(self.session)
        self.candidates = SqlCandidateRepository(self.session)
        self.resumes = SqlResumeRepository(self.session)
        self.applications = SqlApplicationRepository(self.session)
        self.evaluations = SqlEvaluationRepository(self.session)
        self.reviews = SqlReviewRepository(self.session)
        self.emails = SqlEmailRepository(self.session)
        self.templates = SqlTemplateRepository(self.session)
        self.audit = SqlAuditRepository(self.session)
        self.workflows = SqlWorkflowRepository(self.session)
        self.settings = SettingsStore(self.session)

    # ── Gestor de contexto ───────────────────────────────────────────────────

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
                logger.warning(
                    "Transacción revertida",
                    error_type=exc_type.__name__,
                    error=str(exc)[:200],
                )
        finally:
            # Una sesión inyectada la gestiona quien la creó; normalmente es
            # FastAPI, y cerrarla aquí rompería el resto de la petición.
            if not self._external_session:
                self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()


__all__ = ["UnitOfWork"]
