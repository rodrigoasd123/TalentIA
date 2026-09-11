"""Formato legible de estados, roles y valores del ATS."""

from __future__ import annotations

from datetime import datetime
from typing import Any

ROLE_LABELS = {
    "admin": "Administrador",
    "hiring_manager": "Responsable de RR. HH.",
    "recruiter": "Recruiter",
    "interviewer": "Entrevistador",
    "auditor": "Auditor",
}

JOB_STATUS_LABELS = {
    "draft": "Borrador",
    "open": "Abierta",
    "paused": "Pausada",
    "closed": "Cerrada",
    "archived": "Archivada",
}

APPLICATION_STATUS_LABELS = {
    "new": "Ingresado",
    "resume_processed": "CV procesado",
    "under_evaluation": "En revisión",
    "human_review": "Revisión humana",
    "shortlisted": "Preseleccionado",
    "approved_for_interview": "Entrevista",
    "interview_scheduled": "Entrevista agendada",
    "interviewed": "Entrevistado",
    "approved": "Oferta",
    "hired": "Contratado",
    "rejected": "Rechazado",
    "withdrawn": "Retirado",
}

APPLICATION_STAGES = list(APPLICATION_STATUS_LABELS)

REVIEW_REASON_LABELS = {
    "score_borderline": "Puntaje en zona gris",
    "injection_detected": "Intento de manipulación",
    "bias_detected": "Posible sesgo",
    "evidence_unverifiable": "Evidencia no verificable",
    "low_parse_confidence": "Extracción poco confiable",
    "incomplete_resume": "CV incompleto",
    "senior_candidate": "Perfil senior",
    "ambiguous_rejection": "Caso ambiguo",
    "score_override": "Puntaje modificado",
    "sensitive_email": "Comunicación sensible",
    "job_offer": "Oferta laboral",
    "data_conflict": "Conflicto de datos",
    "possible_duplicate": "Posible duplicado",
    "hard_filter_failed": "Requisito obligatorio no acreditado",
    "llm_failure": "Proveedor de IA no disponible",
    "budget_exceeded": "Presupuesto agotado",
}

RECOMMENDATION_LABELS = {
    "shortlist": "Coincidencia alta para revisión",
    "review": "Requiere revisión humana",
    "reject": "Evidencia insuficiente o requisitos no acreditados",
}

IMPORT_STATUS_LABELS = {
    "uploaded": "Cargado",
    "validating": "Validando",
    "ready_for_review": "Listo para revisión",
    "partially_valid": "Parcialmente válido",
    "rejected": "Rechazado",
    "imported": "Importado",
    "cancelled": "Cancelado",
}

ROW_CLASSIFICATION_LABELS = {
    "new": "Nuevo",
    "exact_duplicate": "Duplicado exacto",
    "possible_duplicate": "Posible duplicado",
    "already_in_process": "Ya está en proceso",
    "invalid": "Con error",
    "manual_review_required": "Requiere revisión",
}


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role or "Sin rol")


def job_status(status: str) -> str:
    return JOB_STATUS_LABELS.get(status, status or "Sin estado")


def app_status(status: str) -> str:
    return APPLICATION_STATUS_LABELS.get(status, status or "Sin estado")


def review_reason(reason: str) -> str:
    return REVIEW_REASON_LABELS.get(reason, reason)


def recommendation(value: str) -> str:
    return RECOMMENDATION_LABELS.get(value, value or "Sin evaluación")


def import_status(value: str) -> str:
    return IMPORT_STATUS_LABELS.get(value, value or "Sin estado")


def row_classification(value: str) -> str:
    return ROW_CLASSIFICATION_LABELS.get(value, value or "Sin clasificar")


def score(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


def percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return str(value)


def days_from_hours(value: Any) -> str:
    try:
        return f"{float(value) / 24:.1f} dias"
    except (TypeError, ValueError):
        return "-"


def short_id(value: str, size: int = 8) -> str:
    return (value or "")[:size] or "-"


def date_short(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value[:16]


def tone_for_status(status: str) -> str:
    if status in {"open", "ready_for_review", "imported", "hired", "approved", "shortlisted"}:
        return "success"
    if status in {"draft", "human_review", "partially_valid", "pending", "assigned"}:
        return "warning"
    if status in {"rejected", "cancelled", "failed", "critical", "high"}:
        return "danger"
    if status in {"paused", "closed", "archived", "withdrawn"}:
        return "muted"
    return "info"
