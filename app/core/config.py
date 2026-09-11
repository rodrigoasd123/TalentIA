"""Configuración estática por entorno.

Distinguimos dos niveles de configuración y es importante no mezclarlos:

* **Estática** (este módulo): procede de variables de entorno, se lee una vez al
  arrancar y no cambia en caliente. Aquí viven la URL de base de datos, las
  claves maestras de cifrado y los límites de seguridad.
* **En caliente** (``app.infrastructure.settings_store``): procede de la base de
  datos, se edita desde el panel de administración y contiene la configuración
  del proveedor de IA, el modelo elegido y las credenciales de Google OAuth.
  Los valores sensibles se guardan cifrados con una clave derivada de
  ``TALENTIA_SECRET_KEY`` (con alias heredado temporal).

Una API key nunca debe vivir en un fichero de configuración del repositorio.
Por eso la del proveedor de IA no está aquí.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import warnings
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_KEY_FILE = Path(".talentia_dev_key")
_LEGACY_DEV_KEY_FILE = Path(".vera_dev_key")


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Configuración estática de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TALENTIA_",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = Environment.DEVELOPMENT

    # ── Secretos maestros ────────────────────────────────────────────────────
    secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # ── Persistencia ─────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./talentia.db"
    database_echo: bool = False

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_base_url: str = "http://127.0.0.1:8000"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # ── Almacenamiento e ingesta ─────────────────────────────────────────────
    storage_path: Path = Path("./storage")
    max_upload_mb: int = 10
    max_resume_chars: int = 60_000
    import_max_file_mb: int = Field(default=20, ge=1, le=100)
    import_max_rows: int = Field(default=10_000, ge=1, le=100_000)
    import_storage_path: Path = Path("./storage/imports")

    # ── Feature flags (lo irreversible arranca apagado) ──────────────────────
    ff_ai_auto_shortlist: bool = False
    ff_ai_auto_rejection: bool = False
    ff_auto_email: bool = False
    ff_semantic_search: bool = False
    ff_dry_run: bool = True

    # ── Presupuesto y límites de IA ──────────────────────────────────────────
    llm_budget_usd_per_job: float = 5.0
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2

    # ── Observabilidad ───────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = True
    mlflow_enabled: bool = True
    mlflow_tracking_uri: str = ""
    mlflow_experiment_name: str = "TalentIA-LLM"
    mlflow_ui_url: str = "http://127.0.0.1:5000"

    @property
    def resolved_mlflow_tracking_uri(self) -> str:
        if self.mlflow_tracking_uri:
            return self.mlflow_tracking_uri
        database = Path("./mlflow.db").resolve().as_posix()
        return f"sqlite:///{database}"

    # ── Umbrales por defecto del pipeline de evaluación ──────────────────────
    default_minimum_score: float = 70.0
    default_review_threshold: float = 5.0
    max_unverified_evidence_ratio: float = 0.20

    @field_validator("storage_path")
    @classmethod
    def _resolve_storage(cls, value: Path) -> Path:
        value.mkdir(parents=True, exist_ok=True)
        return value.resolve()

    @field_validator("import_storage_path")
    @classmethod
    def _resolve_import_storage(cls, value: Path) -> Path:
        value.mkdir(parents=True, exist_ok=True)
        return value.resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolved_secret_key(self) -> str:
        """Devuelve la clave maestra, generando una de desarrollo si falta.

        En cualquier entorno distinto de ``development`` la ausencia de clave es
        un error de arranque: preferimos no arrancar antes que cifrar con una
        clave improvisada que nadie podrá reproducir tras un reinicio.
        """
        if self.secret_key:
            return self.secret_key
        if self.environment is not Environment.DEVELOPMENT:
            raise RuntimeError(
                "TALENTIA_SECRET_KEY es obligatoria fuera de development. "
                "Genérala con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if _DEV_KEY_FILE.exists() and _LEGACY_DEV_KEY_FILE.exists():
            current = _DEV_KEY_FILE.read_text(encoding="utf-8").strip()
            legacy = _LEGACY_DEV_KEY_FILE.read_text(encoding="utf-8").strip()
            if not secrets.compare_digest(current, legacy):
                raise RuntimeError(
                    "Existen archivos de clave de desarrollo TalentIA y heredado "
                    "con contenidos distintos; resuelve el conflicto antes de iniciar."
                )
            return current
        if _DEV_KEY_FILE.exists():
            return _DEV_KEY_FILE.read_text(encoding="utf-8").strip()
        if _LEGACY_DEV_KEY_FILE.exists():
            legacy = _LEGACY_DEV_KEY_FILE.read_text(encoding="utf-8").strip()
            _DEV_KEY_FILE.write_text(legacy, encoding="utf-8")
            warnings.warn(
                "Se adoptó el archivo de clave de desarrollo heredado como "
                ".talentia_dev_key.", FutureWarning, stacklevel=2,
            )
            return legacy
        generated = secrets.token_urlsafe(48)
        _DEV_KEY_FILE.write_text(generated, encoding="utf-8")
        return generated

    #: Longitud mínima del secreto de firma. HMAC-SHA256 recomienda al menos 32
    #: bytes de material: por debajo, la firma es más débil de lo que aparenta.
    MIN_JWT_SECRET_BYTES: ClassVar[int] = 32

    def resolved_jwt_secret(self) -> str:
        """Clave de firma de tokens, siempre con longitud suficiente.

        El secreto configurado se estira a 64 caracteres hexadecimales mediante
        SHA-256. Estirar no crea entropía que no existiera, así que fuera de
        desarrollo también se exige que el valor original sea suficientemente
        largo: el estirado protege del error de longitud, no del de un secreto
        corto y adivinable.
        """
        if self.jwt_secret:
            raw = self.jwt_secret
        elif self.environment is Environment.DEVELOPMENT:
            # Derivada de la maestra para no proliferar ficheros en desarrollo.
            raw = f"jwt::{self.resolved_secret_key()}"
        else:
            raise RuntimeError("TALENTIA_JWT_SECRET es obligatoria fuera de development.")

        if (
            self.environment is not Environment.DEVELOPMENT
            and len(raw.encode("utf-8")) < self.MIN_JWT_SECRET_BYTES
        ):
            raise RuntimeError(
                f"TALENTIA_JWT_SECRET debe tener al menos {self.MIN_JWT_SECRET_BYTES} "
                "caracteres. Genera una con: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def static_feature_flags(self) -> dict[str, bool]:
        return {
            "AI_AUTO_SHORTLIST": self.ff_ai_auto_shortlist,
            "AI_AUTO_REJECTION": self.ff_ai_auto_rejection,
            "AUTO_EMAIL": self.ff_auto_email,
            "SEMANTIC_SEARCH": self.ff_semantic_search,
            "DRY_RUN": self.ff_dry_run,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instancia única de configuración. Cacheada para no releer el entorno."""
    overrides: dict[str, str] = {}
    for field_name in Settings.model_fields:
        official = f"TALENTIA_{field_name.upper()}"
        legacy = f"VERA_{field_name.upper()}"
        if official in os.environ:
            overrides[field_name] = os.environ[official]
        elif legacy in os.environ:
            overrides[field_name] = os.environ[legacy]
            warnings.warn(
                f"{legacy} está obsoleta; usa {official}. No se registró su valor.",
                FutureWarning,
                stacklevel=1,
            )
    return Settings(**overrides)


def database_url_is_explicit() -> bool:
    return "TALENTIA_DATABASE_URL" in os.environ or "VERA_DATABASE_URL" in os.environ


def reset_settings_cache() -> None:
    """Solo para tests: fuerza la relectura de la configuración."""
    get_settings.cache_clear()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "app" / "ai" / "prompts" / "versions"
FIXTURES_DIR = PROJECT_ROOT / "fixtures"

__all__ = [
    "FIXTURES_DIR",
    "PROJECT_ROOT",
    "PROMPTS_DIR",
    "Environment",
    "Settings",
    "database_url_is_explicit",
    "get_settings",
    "reset_settings_cache",
]
