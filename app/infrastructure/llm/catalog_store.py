"""Catálogo administrable de proveedores/modelos con compatibilidad retroactiva."""

from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import SecretCipher, SecretDecryptionError
from app.core.exceptions import ValidationError
from app.infrastructure.database.models import AIModelConfigModel, AIProviderConfigModel
from app.infrastructure.llm.model_catalog import SELECTABLE_LLM_MODELS, provider_for_model
from app.infrastructure.llm.openai_compatible_adapter import DEFAULT_GENAI_LAB_BASE_URL
from app.infrastructure.settings_store import SettingsStore

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_SYSTEM_PROVIDERS = {
    "gemini": ("Google Gemini", "gemini", ""),
    "openai": ("OpenAI", "openai", ""),
    "genai_lab": ("GenAI Lab", "openai_compatible", DEFAULT_GENAI_LAB_BASE_URL),
    "mock": ("Simulador local", "mock", ""),
}
_LEGACY_SECRET_KEYS = {
    "gemini": "llm.gemini_api_key",
    "openai": "llm.openai_api_key",
    "genai_lab": "llm.genai_lab_api_key",
}


def validate_base_url(value: str, *, allow_empty: bool = False) -> str:
    """Valida una URL de proveedor sin resolver DNS ni efectuar llamadas de red."""
    normalized = value.strip().rstrip("/")
    if not normalized and allow_empty:
        return ""
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValidationError("La URL del proveedor debe ser HTTPS y no contener credenciales.")
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise ValidationError("La URL del proveedor no puede apuntar a un host local.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local):
        raise ValidationError("La URL del proveedor no puede apuntar a una red privada.")
    return normalized


class AIModelCatalogStore:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = SettingsStore(session)
        self.cipher = SecretCipher("ai-provider-credentials")

    def ensure_builtins(self) -> None:
        for provider_id, (name, adapter, base_url) in _SYSTEM_PROVIDERS.items():
            if self.session.get(AIProviderConfigModel, provider_id) is None:
                self.session.add(
                    AIProviderConfigModel(
                        id=provider_id,
                        display_name=name,
                        adapter_type=adapter,
                        base_url=base_url,
                        is_system=True,
                        is_enabled=True,
                        created_by="migration",
                    )
                )
        self.session.flush()
        existing = set(self.session.scalars(select(AIModelConfigModel.model_id)))
        for model_id in ("mock", *SELECTABLE_LLM_MODELS):
            if model_id in existing:
                continue
            provider_id = provider_for_model(model_id)
            self.session.add(
                AIModelConfigModel(
                    id=uuid.uuid4().hex,
                    provider_id=provider_id,
                    model_id=model_id,
                    display_name=model_id,
                    capabilities=["generation"],
                    is_system=True,
                    is_enabled=True,
                    created_by="migration",
                )
            )
        self.session.flush()

    def list_public(self) -> list[dict[str, object]]:
        self.ensure_builtins()
        providers = list(
            self.session.scalars(select(AIProviderConfigModel).order_by(AIProviderConfigModel.id))
        )
        models = list(
            self.session.scalars(
                select(AIModelConfigModel).order_by(
                    AIModelConfigModel.provider_id, AIModelConfigModel.model_id
                )
            )
        )
        by_provider: dict[str, list[dict[str, object]]] = {}
        for model in models:
            by_provider.setdefault(model.provider_id, []).append(self._model_public(model))
        return [
            {
                "id": provider.id,
                "display_name": provider.display_name,
                "adapter_type": provider.adapter_type,
                "base_url": provider.base_url,
                "is_system": provider.is_system,
                "is_enabled": provider.is_enabled,
                "credential_is_set": self._credential_is_set(provider),
                "verified_at": provider.verified_at.isoformat() if provider.verified_at else None,
                "version": provider.version,
                "models": by_provider.get(provider.id, []),
            }
            for provider in providers
        ]

    def selectable_models(self) -> list[str]:
        self.ensure_builtins()
        statement = (
            select(AIModelConfigModel.model_id)
            .join(AIProviderConfigModel, AIProviderConfigModel.id == AIModelConfigModel.provider_id)
            .where(AIModelConfigModel.is_enabled.is_(True))
            .where(AIProviderConfigModel.is_enabled.is_(True))
            .order_by(AIModelConfigModel.model_id)
        )
        return list(self.session.scalars(statement))

    def create_provider(
        self, *, provider_id: str, display_name: str, base_url: str, created_by: str
    ) -> dict[str, object]:
        normalized_id = provider_id.strip().casefold()
        if not _ID_RE.fullmatch(normalized_id):
            raise ValidationError("El ID usa solo minúsculas, números, guion o guion bajo.")
        if self.session.get(AIProviderConfigModel, normalized_id):
            raise ValidationError("Ya existe un proveedor con ese identificador.")
        provider = AIProviderConfigModel(
            id=normalized_id,
            display_name=display_name.strip(),
            adapter_type="openai_compatible",
            base_url=validate_base_url(base_url),
            created_by=created_by,
        )
        if not provider.display_name:
            raise ValidationError("El nombre del proveedor es obligatorio.")
        self.session.add(provider)
        self.session.flush()
        return self.provider_public(provider)

    def update_provider(
        self,
        provider_id: str,
        *,
        expected_version: int,
        display_name: str | None = None,
        base_url: str | None = None,
        is_enabled: bool | None = None,
    ) -> dict[str, object]:
        provider = self._provider(provider_id)
        self._check_version(provider.version, expected_version)
        if display_name is not None:
            if not display_name.strip():
                raise ValidationError("El nombre del proveedor es obligatorio.")
            provider.display_name = display_name.strip()
        if base_url is not None:
            if provider.adapter_type not in {"openai_compatible"}:
                raise ValidationError("La URL solo es editable en proveedores compatibles.")
            provider.base_url = validate_base_url(base_url)
        if is_enabled is not None:
            if not is_enabled and provider.id == "mock":
                raise ValidationError(
                    "El simulador local es el fallback y no puede deshabilitarse."
                )
            if not is_enabled and self._active_model_uses(provider.id):
                raise ValidationError(
                    "Asigna otro modelo activo antes de deshabilitar el proveedor."
                )
            provider.is_enabled = is_enabled
        provider.version += 1
        self.session.flush()
        return self.provider_public(provider)

    def set_credential(self, provider_id: str, credential: str, *, expected_version: int) -> None:
        provider = self._provider(provider_id)
        self._check_version(provider.version, expected_version)
        if provider.adapter_type == "mock":
            raise ValidationError("El simulador local no utiliza credenciales.")
        if not credential.strip():
            raise ValidationError("La credencial no puede estar vacía.")
        provider.encrypted_credential = self.cipher.encrypt(credential.strip())
        provider.verified_at = None
        provider.version += 1
        self.session.flush()

    def mark_verified(self, provider_id: str) -> None:
        provider = self._provider(provider_id)
        provider.verified_at = datetime.now(UTC)
        provider.version += 1
        self.session.flush()

    def add_model(
        self,
        provider_id: str,
        *,
        model_id: str,
        display_name: str,
        capabilities: list[str],
        input_price: float | None,
        output_price: float | None,
        created_by: str,
    ) -> dict[str, object]:
        provider = self._provider(provider_id)
        if not provider.is_enabled:
            raise ValidationError("Habilita el proveedor antes de agregar modelos.")
        remote_id = model_id.strip()
        if not remote_id or len(remote_id) > 160 or any(c.isspace() for c in remote_id):
            raise ValidationError("El identificador remoto del modelo no es válido.")
        if self.session.scalar(
            select(AIModelConfigModel).where(AIModelConfigModel.model_id == remote_id)
        ):
            raise ValidationError("Ese identificador de modelo ya existe.")
        caps = sorted({item.strip().casefold() for item in capabilities if item.strip()})
        if "generation" not in caps:
            raise ValidationError("R1 solo admite modelos con capacidad generation.")
        self._validate_price(input_price)
        self._validate_price(output_price)
        model = AIModelConfigModel(
            id=uuid.uuid4().hex,
            provider_id=provider.id,
            model_id=remote_id,
            display_name=display_name.strip() or remote_id,
            capabilities=caps,
            input_price_per_million=input_price,
            output_price_per_million=output_price,
            created_by=created_by,
        )
        self.session.add(model)
        self.session.flush()
        return self._model_public(model)

    def update_model(
        self,
        model_id: str,
        *,
        expected_version: int,
        display_name: str | None = None,
        is_enabled: bool | None = None,
        input_price: float | None = None,
        output_price: float | None = None,
    ) -> dict[str, object]:
        model = self._model(model_id)
        self._check_version(model.version, expected_version)
        if display_name is not None:
            model.display_name = display_name.strip() or model.model_id
        if is_enabled is not None:
            if not is_enabled and model.model_id == "mock":
                raise ValidationError(
                    "El modelo simulado es el fallback y no puede deshabilitarse."
                )
            if not is_enabled and self.settings.get("llm.model") == model.model_id:
                raise ValidationError("Activa otro modelo antes de deshabilitar el modelo en uso.")
            model.is_enabled = is_enabled
        if input_price is not None:
            self._validate_price(input_price)
            model.input_price_per_million = input_price
        if output_price is not None:
            self._validate_price(output_price)
            model.output_price_per_million = output_price
        model.version += 1
        self.session.flush()
        return self._model_public(model)

    def resolve(self, model_id: str) -> dict[str, object]:
        self.ensure_builtins()
        model = self.session.scalar(
            select(AIModelConfigModel).where(AIModelConfigModel.model_id == model_id)
        )
        if model is None or not model.is_enabled:
            raise ValidationError("El modelo no existe o está deshabilitado.")
        provider = self._provider(model.provider_id)
        if not provider.is_enabled:
            raise ValidationError("El proveedor del modelo está deshabilitado.")
        return {
            "provider": provider.id,
            "adapter_type": provider.adapter_type,
            "base_url": provider.base_url,
            "api_key": self._credential(provider),
            "model": model.model_id,
            "input_price": model.input_price_per_million,
            "output_price": model.output_price_per_million,
        }

    def provider_public(self, provider: AIProviderConfigModel) -> dict[str, object]:
        return {
            "id": provider.id,
            "display_name": provider.display_name,
            "adapter_type": provider.adapter_type,
            "base_url": provider.base_url,
            "is_system": provider.is_system,
            "is_enabled": provider.is_enabled,
            "credential_is_set": self._credential_is_set(provider),
            "verified_at": provider.verified_at.isoformat() if provider.verified_at else None,
            "version": provider.version,
        }

    def _provider(self, provider_id: str) -> AIProviderConfigModel:
        self.ensure_builtins()
        provider = self.session.get(AIProviderConfigModel, provider_id)
        if provider is None:
            raise ValidationError("Proveedor no encontrado.")
        return provider

    def _model(self, model_id: str) -> AIModelConfigModel:
        model = self.session.get(AIModelConfigModel, model_id)
        if model is None:
            model = self.session.scalar(
                select(AIModelConfigModel).where(AIModelConfigModel.model_id == model_id)
            )
        if model is None:
            raise ValidationError("Modelo no encontrado.")
        return model

    def _credential(self, provider: AIProviderConfigModel) -> str:
        if provider.encrypted_credential:
            try:
                return self.cipher.decrypt(provider.encrypted_credential)
            except SecretDecryptionError as exc:
                raise ValidationError("La credencial del proveedor no puede descifrarse.") from exc
        legacy = _LEGACY_SECRET_KEYS.get(provider.id)
        if legacy:
            value = self.settings.get(legacy, "")
            if not value and provider.id == "genai_lab":
                value = self.settings.get("llm.api_key", "")
            return value
        return ""

    def _credential_is_set(self, provider: AIProviderConfigModel) -> bool:
        return bool(provider.encrypted_credential or self._credential(provider))

    def _active_model_uses(self, provider_id: str) -> bool:
        active = self.settings.get("llm.model", "")
        return bool(
            self.session.scalar(
                select(AIModelConfigModel.id).where(
                    AIModelConfigModel.provider_id == provider_id,
                    AIModelConfigModel.model_id == active,
                )
            )
        )

    @staticmethod
    def _check_version(actual: int, expected: int) -> None:
        if actual != expected:
            raise ValidationError("La configuración cambió; recarga el panel antes de guardar.")

    @staticmethod
    def _validate_price(value: float | None) -> None:
        if value is not None and (value < 0 or value > 1_000_000):
            raise ValidationError("La tarifa por millón debe ser positiva y razonable.")

    @staticmethod
    def _model_public(model: AIModelConfigModel) -> dict[str, object]:
        return {
            "id": model.id,
            "provider_id": model.provider_id,
            "model_id": model.model_id,
            "display_name": model.display_name,
            "capabilities": list(model.capabilities or []),
            "input_price_per_million": model.input_price_per_million,
            "output_price_per_million": model.output_price_per_million,
            "is_system": model.is_system,
            "is_enabled": model.is_enabled,
            "version": model.version,
        }


__all__ = ["AIModelCatalogStore", "validate_base_url"]
