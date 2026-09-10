"""Configuración en caliente, con secretos cifrados en reposo.

Aquí viven los valores que el usuario edita desde el panel: el proveedor de IA,
la API key, el modelo, la temperatura y las credenciales de Google OAuth.

Tres reglas que gobiernan este módulo:

1. **Un secreto nunca sale en claro por la API.** ``get_public_view`` devuelve
   una versión enmascarada. Para usar el valor real hay que pedirlo
   explícitamente con ``get_secret``, y eso solo lo hace el backend.
2. **Un secreto nunca se escribe sin cifrar.** El cifrado ocurre en el ``set``,
   no en el llamante, para que no dependa de que alguien se acuerde.
3. **Los cambios se auditan.** Se registra qué clave cambió y quién la cambió,
   nunca el valor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import SecretCipher, SecretDecryptionError, mask_secret
from app.core.logging import get_logger
from app.infrastructure.database.models import RuntimeSettingModel

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """Definición de una clave de configuración."""

    key: str
    label: str
    default: str = ""
    is_secret: bool = False
    group: str = "general"
    help_text: str = ""


#: Catálogo de configuración editable. Declararlo aquí, y no permitir claves
#: arbitrarias, evita que la tabla se convierta en un cajón de sastre y permite
#: que el panel se genere solo a partir de este catálogo.
SETTINGS_CATALOG: tuple[SettingSpec, ...] = (
    # ── Proveedor de IA ──────────────────────────────────────────────────────
    SettingSpec(
        "llm.provider", "Proveedor de IA", default="mock", group="ia",
        help_text="«gemini» para usar la API de Google, «mock» para el simulador local.",
    ),
    SettingSpec(
        "llm.api_key", "API key", is_secret=True, group="ia",
        help_text="Se guarda cifrada. Nunca se muestra completa ni aparece en los logs.",
    ),
    SettingSpec(
        "llm.model", "Modelo", default="gemini-2.5-flash", group="ia",
        help_text="Fija una versión concreta. Evita alias móviles del proveedor.",
    ),
    SettingSpec(
        "llm.temperature", "Temperatura", default="0.1", group="ia",
        help_text="Valores bajos dan resultados más reproducibles. Recomendado: 0.0–0.2.",
    ),
    SettingSpec(
        "llm.budget_usd_per_job", "Presupuesto por vacante (USD)", default="5.0", group="ia",
        help_text="Al agotarse, las evaluaciones pendientes pasan a revisión humana.",
    ),
    SettingSpec(
        "llm.enable_bias_audit", "Auditoría de sesgo con modelo", default="true", group="ia",
        help_text="La capa léxica determinística se aplica siempre, active o no esta opción.",
    ),
    # ── Google OAuth / Gmail ─────────────────────────────────────────────────
    SettingSpec(
        "google.client_id", "Google OAuth Client ID", group="google",
        help_text="Del proyecto de Google Cloud, en Credenciales → ID de cliente OAuth 2.0.",
    ),
    SettingSpec(
        "google.client_secret", "Google OAuth Client Secret", is_secret=True, group="google",
        help_text="Se guarda cifrado. No lo compartas ni lo subas al repositorio.",
    ),
    SettingSpec(
        "google.redirect_uri", "URI de redirección",
        default="http://localhost:8000/api/v1/auth/google/callback", group="google",
        help_text="Debe coincidir exactamente con la registrada en Google Cloud.",
    ),
    SettingSpec(
        "google.sender_email", "Correo remitente", group="google",
        help_text="Cuenta desde la que se enviarán las comunicaciones.",
    ),
    SettingSpec(
        "google.refresh_token", "Refresh token de Gmail", is_secret=True, group="google",
        help_text="Se obtiene al autorizar la aplicación. Cifrado en reposo.",
    ),
    # ── Comportamiento del sistema ───────────────────────────────────────────
    SettingSpec(
        "ff.ai_auto_shortlist", "Preselección automática", default="false", group="flags",
        help_text="Permite que VERA preseleccione sin intervención humana.",
    ),
    SettingSpec(
        "ff.ai_auto_rejection", "Rechazo automático", default="false", group="flags",
        help_text="Desactivado por defecto: un rechazo es irreversible y afecta a una persona.",
    ),
    SettingSpec(
        "ff.auto_email", "Envío automático de correos", default="false", group="flags",
        help_text="Las categorías sensibles seguirán exigiendo aprobación humana.",
    ),
    SettingSpec(
        "ff.dry_run", "Modo simulación", default="true", group="flags",
        help_text="Ejecuta el pipeline completo sin persistir decisiones ni enviar nada.",
    ),
)

CATALOG_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in SETTINGS_CATALOG}


class SettingsStore:
    """Acceso a la configuración en caliente sobre una sesión de base de datos."""

    def __init__(self, session: Session, *, cipher: SecretCipher | None = None) -> None:
        self._session = session
        self._cipher = cipher or SecretCipher("runtime-settings")

    # ── Lectura ──────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> str:
        """Valor en claro. Para secretos, descifra."""
        spec = CATALOG_BY_KEY.get(key)
        row = self._session.get(RuntimeSettingModel, key)
        if row is None:
            return str(default) if default is not None else (spec.default if spec else "")
        if row.is_secret:
            try:
                return self._cipher.decrypt(row.value)
            except SecretDecryptionError:
                logger.error("No se pudo descifrar un secreto", key=key)
                return ""
        return row.value

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get(key, "true" if default else "false")
        return str(raw).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def get_all(self) -> dict[str, str]:
        """Todos los valores en claro. Solo para uso interno del backend."""
        values = {spec.key: spec.default for spec in SETTINGS_CATALOG}
        for row in self._session.scalars(select(RuntimeSettingModel)):
            if row.key not in CATALOG_BY_KEY:
                continue
            values[row.key] = (
                self._cipher.decrypt(row.value) if row.is_secret else row.value
            )
        return values

    def get_public_view(self) -> list[dict[str, Any]]:
        """Vista para la API y el panel: los secretos van enmascarados.

        Devuelve también ``is_set`` para que la interfaz pueda distinguir entre
        «no configurado» y «configurado pero oculto», que es una distinción que
        el usuario necesita ver.
        """
        stored = {
            row.key: row for row in self._session.scalars(select(RuntimeSettingModel))
        }
        view: list[dict[str, Any]] = []
        for spec in SETTINGS_CATALOG:
            row = stored.get(spec.key)
            raw = ""
            if row is not None:
                raw = self._cipher.decrypt(row.value) if row.is_secret else row.value
            value = spec.default if row is None else raw
            view.append(
                {
                    "key": spec.key,
                    "label": spec.label,
                    "group": spec.group,
                    "help_text": spec.help_text,
                    "is_secret": spec.is_secret,
                    "is_set": bool(raw),
                    "value": mask_secret(value) if spec.is_secret else value,
                    "updated_at": row.updated_at.isoformat() if row else None,
                    "updated_by": row.updated_by if row else "",
                }
            )
        return view

    # ── Escritura ────────────────────────────────────────────────────────────

    def set(self, key: str, value: str, *, updated_by: str = "system") -> None:
        """Guarda un valor, cifrándolo si el catálogo lo declara secreto."""
        spec = CATALOG_BY_KEY.get(key)
        if spec is None:
            raise KeyError(
                f"«{key}» no está en el catálogo de configuración. "
                "Añádelo a SETTINGS_CATALOG antes de usarlo."
            )

        stored_value = self._cipher.encrypt(value) if spec.is_secret else value
        row = self._session.get(RuntimeSettingModel, key)
        if row is None:
            row = RuntimeSettingModel(key=key, is_secret=spec.is_secret)
            self._session.add(row)
        row.value = stored_value
        row.is_secret = spec.is_secret
        row.updated_by = updated_by
        self._session.flush()

        # Se registra el cambio, jamás el valor.
        logger.info(
            "Configuración actualizada",
            key=key,
            is_secret=spec.is_secret,
            has_value=bool(value),
            updated_by=updated_by,
        )

    def set_many(self, values: dict[str, str], *, updated_by: str = "system") -> list[str]:
        applied: list[str] = []
        for key, value in values.items():
            if key not in CATALOG_BY_KEY:
                logger.warning("Clave de configuración desconocida ignorada", key=key)
                continue
            self.set(key, value, updated_by=updated_by)
            applied.append(key)
        return applied

    def delete(self, key: str) -> None:
        row = self._session.get(RuntimeSettingModel, key)
        if row is not None:
            self._session.delete(row)
            self._session.flush()
            logger.info("Configuración eliminada", key=key)

    # ── Consultas de conveniencia ────────────────────────────────────────────

    def llm_config(self) -> dict[str, Any]:
        return {
            "provider": self.get("llm.provider", "mock"),
            "api_key": self.get("llm.api_key", ""),
            "model": self.get("llm.model", "gemini-2.5-flash"),
            "temperature": self.get_float("llm.temperature", 0.1),
            "budget_usd": self.get_float("llm.budget_usd_per_job", 5.0),
            "enable_bias_audit": self.get_bool("llm.enable_bias_audit", True),
        }

    def google_config(self) -> dict[str, Any]:
        return {
            "client_id": self.get("google.client_id", ""),
            "client_secret": self.get("google.client_secret", ""),
            "redirect_uri": self.get("google.redirect_uri", ""),
            "sender_email": self.get("google.sender_email", ""),
            "refresh_token": self.get("google.refresh_token", ""),
        }

    def feature_flags(self) -> dict[str, bool]:
        """Los flags de base de datos se superponen a los del entorno."""
        return {
            "AI_AUTO_SHORTLIST": self.get_bool("ff.ai_auto_shortlist", False),
            "AI_AUTO_REJECTION": self.get_bool("ff.ai_auto_rejection", False),
            "AUTO_EMAIL": self.get_bool("ff.auto_email", False),
            "DRY_RUN": self.get_bool("ff.dry_run", True),
        }

    def is_llm_ready(self) -> bool:
        config = self.llm_config()
        if config["provider"] == "mock":
            return True
        return bool(config["api_key"])


__all__ = ["CATALOG_BY_KEY", "SETTINGS_CATALOG", "SettingSpec", "SettingsStore"]
