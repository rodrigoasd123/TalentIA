"""Excepciones de dominio y de aplicación.

Cada excepción lleva un ``code`` estable que la API traduce a un envelope de
error uniforme y un ``http_status`` sugerido. Esto evita el antipatrón de
capturar ``Exception`` en las rutas y decidir el código a ojo.

La regla es: el dominio lanza excepciones de dominio; la capa API las traduce.
El dominio nunca importa nada de HTTP.
"""

from __future__ import annotations

from typing import Any


class VeraError(Exception):
    """Raíz de toda excepción propia del sistema."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "Error interno"

    def __init__(self, message: str | None = None, **details: Any) -> None:
        self.message = message or self.message
        self.details: dict[str, Any] = details
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


# ── Recursos ─────────────────────────────────────────────────────────────────


class NotFoundError(VeraError):
    code = "NOT_FOUND"
    http_status = 404
    message = "Recurso no encontrado"


class CandidateNotFound(NotFoundError):
    code = "CANDIDATE_NOT_FOUND"
    message = "El candidato no existe"


class JobNotFound(NotFoundError):
    code = "JOB_NOT_FOUND"
    message = "La vacante no existe"


class ApplicationNotFound(NotFoundError):
    code = "APPLICATION_NOT_FOUND"
    message = "La aplicación no existe"


class ResumeNotFound(NotFoundError):
    code = "RESUME_NOT_FOUND"
    message = "El CV no existe"


# ── Reglas de negocio ────────────────────────────────────────────────────────


class ValidationError(VeraError):
    code = "VALIDATION_ERROR"
    http_status = 422
    message = "Datos inválidos"


class InvalidStateTransition(VeraError):
    code = "INVALID_STATE_TRANSITION"
    http_status = 409
    message = "Transición de estado no permitida"


class InvalidScoringWeights(ValidationError):
    code = "INVALID_SCORING_WEIGHTS"
    message = "Los pesos de scoring deben sumar 100"


class ConsentMissingOrExpired(VeraError):
    code = "CONSENT_MISSING"
    http_status = 403
    message = "El candidato no tiene consentimiento vigente para este tratamiento"


class DuplicateApplication(VeraError):
    code = "DUPLICATE_APPLICATION"
    http_status = 409
    message = "El candidato ya tiene una aplicación activa en esta vacante"


# ── Seguridad y políticas ────────────────────────────────────────────────────


class AuthenticationError(VeraError):
    code = "AUTHENTICATION_FAILED"
    http_status = 401
    message = "Credenciales inválidas"


class PermissionDenied(VeraError):
    code = "PERMISSION_DENIED"
    http_status = 403
    message = "No tienes permiso para realizar esta acción"


class PolicyDenied(VeraError):
    code = "POLICY_DENIED"
    http_status = 403
    message = "La política del sistema deniega esta acción"


class HumanApprovalRequired(VeraError):
    code = "HUMAN_APPROVAL_REQUIRED"
    http_status = 428
    message = "Esta acción requiere aprobación humana previa"


class ToolNotAllowed(VeraError):
    code = "TOOL_NOT_ALLOWED"
    http_status = 403
    message = "La herramienta solicitada no está autorizada para el agente"


class RateLimitExceeded(VeraError):
    code = "RATE_LIMIT_EXCEEDED"
    http_status = 429
    message = "Se ha superado el límite de peticiones"


# ── Ingesta de documentos ────────────────────────────────────────────────────


class DocumentError(VeraError):
    code = "DOCUMENT_ERROR"
    http_status = 422
    message = "No se pudo procesar el documento"


class UnsupportedDocumentType(DocumentError):
    code = "UNSUPPORTED_DOCUMENT_TYPE"
    message = "Tipo de documento no admitido"


class DocumentTooLarge(DocumentError):
    code = "DOCUMENT_TOO_LARGE"
    message = "El documento supera el tamaño máximo permitido"


class ResumeParsingError(DocumentError):
    code = "RESUME_PARSING_ERROR"
    message = "No se pudo extraer texto útil del CV"


# ── Capa de IA ───────────────────────────────────────────────────────────────


class LLMError(VeraError):
    code = "LLM_ERROR"
    http_status = 502
    message = "Error al invocar el modelo de lenguaje"


class LLMNotConfigured(LLMError):
    code = "LLM_NOT_CONFIGURED"
    http_status = 503
    message = "No hay proveedor de IA configurado. Añade una API key en el panel."


class LLMTimeout(LLMError):
    code = "LLM_TIMEOUT"
    http_status = 504
    message = "El modelo no respondió a tiempo"


class LLMValidationError(LLMError):
    code = "LLM_VALIDATION_ERROR"
    http_status = 502
    message = "La salida del modelo no cumple el esquema esperado"


class BudgetExceeded(VeraError):
    code = "BUDGET_EXCEEDED"
    http_status = 429
    message = "Se ha agotado el presupuesto de IA asignado"


class EvidenceVerificationFailed(VeraError):
    code = "EVIDENCE_VERIFICATION_FAILED"
    http_status = 422
    message = "La evidencia aportada por el modelo no se encuentra en el CV"


class PromptInjectionDetected(VeraError):
    code = "PROMPT_INJECTION_DETECTED"
    http_status = 422
    message = "El documento contiene contenido que intenta manipular al sistema"


# ── Comunicaciones ───────────────────────────────────────────────────────────


class EmailError(VeraError):
    code = "EMAIL_ERROR"
    http_status = 502
    message = "No se pudo enviar el correo"


class EmailAlreadySent(VeraError):
    code = "EMAIL_ALREADY_SENT"
    http_status = 409
    message = "Ese correo ya fue enviado; se ignora el duplicado"


class GmailNotConfigured(EmailError):
    code = "GMAIL_NOT_CONFIGURED"
    http_status = 503
    message = "La integración con Gmail no está configurada"


__all__ = [n for n in dir() if n.endswith(("Error", "Denied", "Found", "Required", "Exceeded"))]
