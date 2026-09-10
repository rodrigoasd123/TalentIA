"""Logging estructurado con redacción obligatoria de secretos y PII.

Dos decisiones deliberadas:

1. **La redacción es del formatter, no del llamante.** Confiar en que cada
   `logger.info()` recuerde no incluir un token es una garantía que se rompe el
   primer día. El filtro se aplica siempre, en el último punto antes de escribir.
2. **El ``trace_id`` viaja por ``contextvars``**, no como parámetro. Así se
   propaga solo a través de la API, el grafo del agente y los repositorios sin
   ensuciar todas las firmas del sistema.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_actor_id: ContextVar[str] = ContextVar("actor_id", default="-")

# Claves cuyo valor jamás debe aparecer en un log, sin importar el contexto.
SENSITIVE_KEYS = frozenset(
    {
        "api_key", "apikey", "password", "passwd", "secret", "token",
        "access_token", "refresh_token", "client_secret", "authorization",
        "jwt", "private_key", "credential", "credentials", "gemini_api_key",
        "google_client_secret", "pii_map", "raw_resume_text",
    }
)

# Patrones de PII y de credenciales en texto libre.
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "[EMAIL_REDACTADO]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"), "[API_KEY_REDACTADA]"),
    (re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}\b"), "[API_KEY_REDACTADA]"),
    (re.compile(r"\bya29\.[0-9A-Za-z_\-]+\b"), "[OAUTH_TOKEN_REDACTADO]"),
    (re.compile(r"\beyJ[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+\b"), "[JWT_REDACTADO]"),
    # El teléfono exige una señal explícita: prefijo internacional o separadores
    # entre grupos. Un patrón más laxo devoraba tramos de los identificadores
    # hexadecimales (`efe3c47d1234...`), lo que dejaba los logs de auditoría
    # ilegibles justo donde más falta hace poder seguir la traza.
    (
        re.compile(r"(?<![A-Za-z0-9])\+\d{1,3}[ .\-]?\d[\d .\-]{6,16}\d(?![A-Za-z0-9])"),
        "[TELEFONO_REDACTADO]",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9])\d{3}[ .\-]\d{2,4}[ .\-]\d{2,4}(?![A-Za-z0-9])"),
        "[TELEFONO_REDACTADO]",
    ),
    (
        re.compile(
            r"(?i)\b(?:dni|nif|nie|c[eé]dula|documento|pasaporte)\s*[:.\-]?\s*"
            r"[0-9A-Za-z][0-9A-Za-z\-.]{5,14}\b"
        ),
        "[DOCUMENTO_REDACTADO]",
    ),
)


def redact(value: Any, _depth: int = 0) -> Any:
    """Devuelve una copia del valor con secretos y PII sustituidos.

    Recorre estructuras anidadas. La profundidad se acota para que un objeto
    cíclico o muy profundo no bloquee el proceso de logging.
    """
    if _depth > 6:
        return "[PROFUNDIDAD_MAXIMA]"
    if isinstance(value, str):
        out = value
        for pattern, replacement in _REDACTION_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, dict):
        return {
            k: ("[REDACTADO]" if str(k).lower() in SENSITIVE_KEYS else redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact(v, _depth + 1) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    """Formatter JSON de una línea por evento, con redacción aplicada."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "trace_id": _trace_id.get(),
            "actor_id": _actor_id.get(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(redact(extra))
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Formato legible para desarrollo local. Redacta igual que el JSON."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{datetime.now(UTC).strftime('%H:%M:%S')} {record.levelname:<7} " \
               f"[{_trace_id.get()[:8]}] {record.name}: {redact(record.getMessage())}"
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict) and extra:
            base += f" | {json.dumps(redact(extra), ensure_ascii=False, default=str)}"
        if record.exc_info:
            base += "\n" + redact(self.formatException(record.exc_info))
        return base


class StructuredLogger:
    """Envoltura fina sobre ``logging`` que acepta campos estructurados."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(self, level: int, message: str, **fields: Any) -> None:
        self._logger.log(level, message, extra={"extra_fields": fields})

    def debug(self, message: str, **fields: Any) -> None:
        self._log(logging.DEBUG, message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, **fields)

    def security(self, message: str, **fields: Any) -> None:
        """Evento de seguridad. Se marca aparte para poder alertar sobre él."""
        self._log(logging.WARNING, message, event_type="security", **fields)

    def exception(self, message: str, **fields: Any) -> None:
        self._logger.exception(message, extra={"extra_fields": fields})


def configure_logging(level: str = "INFO", as_json: bool = True) -> None:
    """Configura el logging raíz. Idempotente."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if as_json else TextFormatter())
    root.addHandler(handler)
    # Silenciamos el ruido de librerías de terceros.
    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)


# ── Contexto de traza ────────────────────────────────────────────────────────


def new_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_id(trace_id: str | None = None) -> str:
    value = trace_id or new_trace_id()
    _trace_id.set(value)
    return value


def get_trace_id() -> str:
    return _trace_id.get()


def set_actor_id(actor_id: str) -> None:
    _actor_id.set(actor_id)


__all__ = [
    "StructuredLogger",
    "configure_logging",
    "get_logger",
    "get_trace_id",
    "new_trace_id",
    "redact",
    "set_actor_id",
    "set_trace_id",
]
