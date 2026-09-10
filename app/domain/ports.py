"""Puertos: las interfaces que el dominio necesita del mundo exterior.

Viven en el dominio y no en infraestructura porque quien define un contrato es
quien lo consume, no quien lo implementa. Así el dominio no importa nada de
infraestructura y la dependencia queda invertida.

Solo se define un puerto donde va a existir una segunda implementación real
(SQLite y PostgreSQL, Gemini y un doble de pruebas, disco y almacenamiento
remoto). Abstraer por costumbre lo que nunca va a cambiar solo añade ruido.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.domain.entities import (
    Application,
    AuditEvent,
    Candidate,
    EmailMessage,
    Evaluation,
    HumanReviewItem,
    Job,
    ResumeDocument,
    User,
    WorkflowRun,
)
from app.domain.enums import ApplicationStatus


# ── Persistencia ─────────────────────────────────────────────────────────────


@runtime_checkable
class JobRepository(Protocol):
    def add(self, job: Job) -> Job: ...
    def get(self, job_id: str) -> Job | None: ...
    def get_by_code(self, code: str) -> Job | None: ...
    def update(self, job: Job) -> Job: ...
    def list(self, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> list[Job]: ...


@runtime_checkable
class CandidateRepository(Protocol):
    def add(self, candidate: Candidate) -> Candidate: ...
    def get(self, candidate_id: str) -> Candidate | None: ...
    def get_by_email(self, email: str) -> Candidate | None: ...
    def update(self, candidate: Candidate) -> Candidate: ...
    def list(self, *, limit: int = 50, cursor: str | None = None) -> list[Candidate]: ...
    def find_potential_duplicates(self, candidate: Candidate) -> list[Candidate]: ...


@runtime_checkable
class ApplicationRepository(Protocol):
    def add(self, application: Application) -> Application: ...
    def get(self, application_id: str) -> Application | None: ...
    def get_by_idempotency_key(self, key: str) -> Application | None: ...
    def update(self, application: Application) -> Application: ...
    def list_for_job(self, job_id: str, *, status: ApplicationStatus | None = None) -> list[Application]: ...
    def list_for_candidate(self, candidate_id: str) -> list[Application]: ...


@runtime_checkable
class ResumeRepository(Protocol):
    def add(self, resume: ResumeDocument) -> ResumeDocument: ...
    def get(self, resume_id: str) -> ResumeDocument | None: ...
    def get_by_hash(self, content_hash: str) -> ResumeDocument | None: ...
    def update(self, resume: ResumeDocument) -> ResumeDocument: ...
    def list_for_candidate(self, candidate_id: str) -> list[ResumeDocument]: ...


@runtime_checkable
class EvaluationRepository(Protocol):
    def add(self, evaluation: Evaluation) -> Evaluation: ...
    def get(self, evaluation_id: str) -> Evaluation | None: ...
    def list_for_application(self, application_id: str) -> list[Evaluation]: ...
    def get_current(self, application_id: str) -> Evaluation | None: ...
    def supersede(self, evaluation_id: str, new_evaluation_id: str) -> None: ...


@runtime_checkable
class ReviewRepository(Protocol):
    def add(self, item: HumanReviewItem) -> HumanReviewItem: ...
    def get(self, item_id: str) -> HumanReviewItem | None: ...
    def update(self, item: HumanReviewItem) -> HumanReviewItem: ...
    def list_queue(self, *, status: str | None = None, assigned_to: str | None = None) -> list[HumanReviewItem]: ...
    def find_open_for_application(self, application_id: str) -> HumanReviewItem | None: ...


@runtime_checkable
class EmailRepository(Protocol):
    def add(self, message: EmailMessage) -> EmailMessage: ...
    def get(self, message_id: str) -> EmailMessage | None: ...
    def get_by_idempotency_key(self, key: str) -> EmailMessage | None: ...
    def update(self, message: EmailMessage) -> EmailMessage: ...
    def list_for_application(self, application_id: str) -> list[EmailMessage]: ...
    def count_sent_since(self, job_id: str, hours: int) -> int: ...


@runtime_checkable
class UserRepository(Protocol):
    def add(self, user: User) -> User: ...
    def get(self, user_id: str) -> User | None: ...
    def get_by_email(self, email: str) -> User | None: ...
    def update(self, user: User) -> User: ...
    def list(self) -> list[User]: ...


@runtime_checkable
class AuditRepository(Protocol):
    """Solo inserción y lectura. No existe ``update`` ni ``delete`` a propósito:
    lo que no se puede llamar no se puede usar por error."""

    def append(self, event: AuditEvent) -> AuditEvent: ...
    def list(self, *, resource_id: str | None = None, trace_id: str | None = None,
             action: str | None = None, limit: int = 100) -> list[AuditEvent]: ...
    def last_hash(self) -> str: ...
    def verify_chain(self) -> tuple[bool, str | None]: ...


@runtime_checkable
class WorkflowRepository(Protocol):
    def add(self, run: WorkflowRun) -> WorkflowRun: ...
    def get(self, run_id: str) -> WorkflowRun | None: ...
    def update(self, run: WorkflowRun) -> WorkflowRun: ...
    def list_for_application(self, application_id: str) -> list[WorkflowRun]: ...


# ── Servicios externos ───────────────────────────────────────────────────────


@runtime_checkable
class LLMPort(Protocol):
    """Contrato mínimo con un proveedor de modelos de lenguaje.

    Deliberadamente estrecho: solo generar texto o JSON estructurado. No expone
    herramientas, ni llamadas a funciones, ni streaming. Un puerto ancho invita
    a que la lógica de negocio se apoye en capacidades del proveedor y quede
    atada a él.
    """

    @property
    def model_name(self) -> str: ...

    @property
    def is_configured(self) -> bool: ...

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        timeout_seconds: int = 60,
    ) -> "LLMResponse": ...

    def list_models(self) -> list[str]: ...


class LLMResponse(Protocol):
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    finish_reason: str


@runtime_checkable
class EmailPort(Protocol):
    """Envío de correo. La implementación de Gmail no se expone al agente."""

    @property
    def is_configured(self) -> bool: ...

    def send(
        self, *, to: str, subject: str, body: str, idempotency_key: str
    ) -> dict[str, str]: ...


@runtime_checkable
class StoragePort(Protocol):
    def save(self, *, content: bytes, filename: str, folder: str = "resumes") -> str: ...
    def read(self, path: str) -> bytes: ...
    def delete(self, path: str) -> None: ...
    def exists(self, path: str) -> bool: ...


@runtime_checkable
class TextExtractorPort(Protocol):
    def extract(self, *, content: bytes, filename: str) -> "ExtractedText": ...


class ExtractedText(Protocol):
    text: str
    char_count: int
    page_count: int
    extraction_ok: bool
    warnings: list[str]
    hidden_text_found: bool


@runtime_checkable
class ClockPort(Protocol):
    """Reloj inyectable. Sin esto, cualquier test que dependa de SLA o de
    caducidad de consentimiento es frágil o directamente imposible."""

    def now(self) -> Any: ...


@runtime_checkable
class SchedulerPort(Protocol):
    def schedule(self, *, task_name: str, run_at: Any, payload: dict[str, Any]) -> str: ...
    def cancel(self, task_id: str) -> bool: ...
    def due_tasks(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class SettingsStorePort(Protocol):
    """Configuración editable en caliente, con secretos cifrados en reposo."""

    def get_all(self) -> dict[str, Any]: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any, *, secret: bool = False) -> None: ...
    def delete(self, key: str) -> None: ...


__all__ = [
    "ApplicationRepository", "AuditRepository", "CandidateRepository", "ClockPort",
    "EmailPort", "EmailRepository", "EvaluationRepository", "ExtractedText",
    "JobRepository", "LLMPort", "LLMResponse", "ResumeRepository",
    "ReviewRepository", "SchedulerPort", "SettingsStorePort", "StoragePort",
    "TextExtractorPort", "UserRepository", "WorkflowRepository",
]
