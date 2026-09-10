"""Enumerados del dominio.

Se usa ``StrEnum`` para que el valor persistido sea legible en la base de datos
y en los logs. La validación de valores admisibles vive aquí, en el dominio, no
en la base de datos: así funciona igual sobre SQLite y sobre PostgreSQL.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    INTERVIEWER = "interviewer"
    AUDITOR = "auditor"


class Permission(StrEnum):
    JOB_READ = "job:read"
    JOB_WRITE = "job:write"
    JOB_PUBLISH = "job:publish"
    CANDIDATE_READ = "candidate:read"
    CANDIDATE_WRITE = "candidate:write"
    CANDIDATE_PII_READ = "candidate:pii:read"
    APPLICATION_READ = "application:read"
    APPLICATION_TRANSITION = "application:transition"
    EVALUATION_RUN = "evaluation:run"
    EVALUATION_OVERRIDE = "evaluation:override"
    REVIEW_DECIDE = "review:decide"
    EMAIL_PREPARE = "email:prepare"
    EMAIL_APPROVE = "email:approve"
    EMAIL_SEND = "email:send"
    INTERVIEW_MANAGE = "interview:manage"
    AUDIT_READ = "audit:read"
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"


#: Matriz de permisos por rol. Es la fuente de verdad del RBAC y la referencia
#: contra la que se escriben los tests negativos de autorización.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECRUITER: frozenset(
        {
            Permission.JOB_READ, Permission.JOB_WRITE, Permission.JOB_PUBLISH,
            Permission.CANDIDATE_READ, Permission.CANDIDATE_WRITE,
            Permission.CANDIDATE_PII_READ, Permission.APPLICATION_READ,
            Permission.APPLICATION_TRANSITION, Permission.EVALUATION_RUN,
            Permission.REVIEW_DECIDE, Permission.EMAIL_PREPARE,
            Permission.INTERVIEW_MANAGE, Permission.AUDIT_READ,
            Permission.SETTINGS_READ,
        }
    ),
    Role.HIRING_MANAGER: frozenset(
        {
            Permission.JOB_READ, Permission.CANDIDATE_READ,
            Permission.CANDIDATE_PII_READ, Permission.APPLICATION_READ,
            Permission.APPLICATION_TRANSITION, Permission.EVALUATION_OVERRIDE,
            Permission.REVIEW_DECIDE, Permission.EMAIL_APPROVE,
            Permission.INTERVIEW_MANAGE, Permission.AUDIT_READ,
        }
    ),
    Role.INTERVIEWER: frozenset(
        {
            Permission.JOB_READ, Permission.CANDIDATE_READ,
            Permission.APPLICATION_READ, Permission.INTERVIEW_MANAGE,
        }
    ),
    # El auditor lo ve todo y no modifica nada. Es deliberado: un auditor que
    # puede escribir deja de ser un control independiente.
    Role.AUDITOR: frozenset(
        {
            Permission.JOB_READ, Permission.CANDIDATE_READ,
            Permission.APPLICATION_READ, Permission.AUDIT_READ,
            Permission.SETTINGS_READ,
        }
    ),
}


class JobStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ApplicationStatus(StrEnum):
    """Estados del candidato dentro de una vacante concreta.

    El conjunto es configurable por vacante en cuanto a *qué subconjunto* se usa,
    pero el catálogo global es cerrado para que las métricas sean comparables
    entre procesos distintos.
    """

    NEW = "new"
    RESUME_PROCESSED = "resume_processed"
    UNDER_EVALUATION = "under_evaluation"
    SHORTLISTED = "shortlisted"
    HUMAN_REVIEW = "human_review"
    APPROVED_FOR_INTERVIEW = "approved_for_interview"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWED = "interviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    HIRED = "hired"
    WITHDRAWN = "withdrawn"


#: Estados desde los que ya no se avanza. Sirven para métricas y para impedir
#: que un reintento reabra un proceso cerrado.
TERMINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {ApplicationStatus.REJECTED, ApplicationStatus.HIRED, ApplicationStatus.WITHDRAWN}
)


class Recommendation(StrEnum):
    """Conjunto cerrado de recomendaciones que el modelo puede emitir.

    Es cerrado a propósito: si el modelo pudiera devolver texto libre, ese texto
    acabaría interpretándose en algún punto como decisión.
    """

    REJECT = "reject"
    REVIEW = "review"
    SHORTLIST = "shortlist"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"


class ActionType(StrEnum):
    """Acciones que el agente puede *proponer*. Nunca ejecutar."""

    READ_CANDIDATE = "read_candidate"
    READ_JOB = "read_job"
    EVALUATE_CANDIDATE = "evaluate_candidate"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    PREPARE_EMAIL = "prepare_email"
    CHANGE_STATUS = "change_status"
    SEND_EMAIL = "send_email"


class ReviewReason(StrEnum):
    """Motivos por los que un caso entra en la cola de revisión humana."""

    SCORE_BORDERLINE = "score_borderline"
    INJECTION_DETECTED = "injection_detected"
    BIAS_DETECTED = "bias_detected"
    EVIDENCE_UNVERIFIABLE = "evidence_unverifiable"
    LOW_PARSE_CONFIDENCE = "low_parse_confidence"
    INCOMPLETE_RESUME = "incomplete_resume"
    SENIOR_CANDIDATE = "senior_candidate"
    AMBIGUOUS_REJECTION = "ambiguous_rejection"
    SCORE_OVERRIDE = "score_override"
    SENSITIVE_EMAIL = "sensitive_email"
    JOB_OFFER = "job_offer"
    DATA_CONFLICT = "data_conflict"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    HARD_FILTER_FAILED = "hard_filter_failed"
    LLM_FAILURE = "llm_failure"
    BUDGET_EXCEEDED = "budget_exceeded"


#: Prioridad y plazo objetivo por motivo. Los motivos de seguridad tienen el
#: plazo más corto porque un intento de manipulación no debe esperar un día.
REVIEW_SLA_HOURS: dict[ReviewReason, int] = {
    ReviewReason.INJECTION_DETECTED: 4,
    ReviewReason.BIAS_DETECTED: 4,
    ReviewReason.JOB_OFFER: 4,
    ReviewReason.EVIDENCE_UNVERIFIABLE: 8,
    ReviewReason.SENSITIVE_EMAIL: 8,
    ReviewReason.AMBIGUOUS_REJECTION: 12,
    ReviewReason.SENIOR_CANDIDATE: 12,
    ReviewReason.SCORE_BORDERLINE: 24,
    ReviewReason.LOW_PARSE_CONFIDENCE: 24,
    ReviewReason.DATA_CONFLICT: 24,
    ReviewReason.HARD_FILTER_FAILED: 24,
    ReviewReason.SCORE_OVERRIDE: 24,
    ReviewReason.LLM_FAILURE: 24,
    ReviewReason.BUDGET_EXCEEDED: 24,
    ReviewReason.INCOMPLETE_RESUME: 48,
    ReviewReason.POSSIBLE_DUPLICATE: 48,
}


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActorType(StrEnum):
    USER = "user"
    AI_AGENT = "ai_agent"
    SYSTEM = "system"


class InjectionCategory(StrEnum):
    """Categorías de intento de manipulación detectables en un documento."""

    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_IMPERSONATION = "role_impersonation"
    SCORE_MANIPULATION = "score_manipulation"
    ACTION_COMMAND = "action_command"
    FAKE_DELIMITER = "fake_delimiter"
    HIDDEN_TEXT = "hidden_text"
    ENCODING_EVASION = "encoding_evasion"
    KEYWORD_STUFFING = "keyword_stuffing"
    PROMPT_EXFILTRATION = "prompt_exfiltration"


class PIICategory(StrEnum):
    """Categorías de dato personal que se retiran antes de la evaluación."""

    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    NATIONAL_ID = "national_id"
    BIRTH_DATE = "birth_date"
    AGE = "age"
    GENDER = "gender"
    NATIONALITY = "nationality"
    MARITAL_STATUS = "marital_status"
    PHOTO = "photo"
    RELIGION = "religion"
    HEALTH = "health"
    URL_PROFILE = "url_profile"


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"


class EmailStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailTemplateKind(StrEnum):
    RECEIPT_CONFIRMATION = "receipt_confirmation"
    SHORTLISTED = "shortlisted"
    INTERVIEW_INVITATION = "interview_invitation"
    DOCUMENT_REQUEST = "document_request"
    REJECTION = "rejection"
    INTERVIEW_REMINDER = "interview_reminder"
    PROCESS_CLOSED = "process_closed"


#: Categorías cuyo envío exige aprobación humana explícita, con independencia
#: de la configuración de la vacante. Son irreversibles y afectan a una persona.
SENSITIVE_EMAIL_KINDS: frozenset[EmailTemplateKind] = frozenset(
    {
        EmailTemplateKind.REJECTION,
        EmailTemplateKind.INTERVIEW_INVITATION,
        EmailTemplateKind.PROCESS_CLOSED,
    }
)


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_HUMAN = "awaiting_human"
    CANCELLED = "cancelled"


class FilterOperator(StrEnum):
    """Operadores admitidos en los filtros determinísticos de una vacante."""

    GTE = "gte"
    LTE = "lte"
    EQUALS = "equals"
    CONTAINS_ALL = "contains_all"
    CONTAINS_ANY = "contains_any"
    IN = "in"
    MIN_LEVEL = "min_level"


class LanguageLevel(StrEnum):
    """Niveles ordenados. El orden importa para el operador ``min_level``."""

    A1 = "a1"
    A2 = "a2"
    B1 = "b1"
    B2 = "b2"
    C1 = "c1"
    C2 = "c2"
    NATIVE = "native"


LANGUAGE_LEVEL_ORDER: dict[LanguageLevel, int] = {
    LanguageLevel.A1: 1, LanguageLevel.A2: 2, LanguageLevel.B1: 3,
    LanguageLevel.B2: 4, LanguageLevel.C1: 5, LanguageLevel.C2: 6,
    LanguageLevel.NATIVE: 7,
}


class ScoringDimension(StrEnum):
    """Dimensiones que puede ponderar una vacante. Conjunto cerrado."""

    TECHNICAL = "technical"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECTS = "projects"
    SEMANTIC = "semantic"
    LANGUAGES = "languages"


__all__ = [
    "LANGUAGE_LEVEL_ORDER", "REVIEW_SLA_HOURS", "ROLE_PERMISSIONS",
    "SENSITIVE_EMAIL_KINDS", "TERMINAL_STATUSES", "ActionType", "ActorType",
    "ApplicationStatus", "DocumentType", "EmailStatus", "EmailTemplateKind",
    "FilterOperator", "InjectionCategory", "JobStatus", "LanguageLevel",
    "PIICategory", "Permission", "PolicyDecision", "Recommendation",
    "ReviewReason", "ReviewStatus", "Role", "ScoringDimension", "Severity",
    "WorkflowStatus",
]
