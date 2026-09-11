"""Configuración y preferencias."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import role_label  # noqa: E402

from app.infrastructure.llm.gemini_adapter import FALLBACK_MODELS  # noqa: E402
from app.infrastructure.llm.model_catalog import (  # noqa: E402
    GENAI_LAB_CHAT_MODELS,
    GENAI_LAB_EMBEDDING_MODELS,
    GENAI_LAB_TRANSCRIPTION_MODELS,
)
from app.infrastructure.llm.openai_compatible_adapter import (  # noqa: E402
    DEFAULT_GENAI_LAB_BASE_URL,
)


def _settings_by_key(settings: list[dict]) -> dict[str, dict]:
    return {item["key"]: item for item in settings}


def _value(items: dict[str, dict], key: str, default: str = "") -> str:
    item = items.get(key)
    if not item:
        return default
    if item.get("is_secret"):
        return default
    return item.get("value") or default


def _is_set(items: dict[str, dict], key: str) -> bool:
    item = items.get(key)
    return bool(item and item.get("is_set"))


def _masked(items: dict[str, dict], key: str) -> str:
    item = items.get(key)
    return str(item.get("value", "")) if item else ""


def _flag(items: dict[str, dict], key: str, default: bool = False) -> bool:
    value = _value(items, key, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "si", "sí", "on"}


def _preferences() -> None:
    st.subheader("Preferencias de interfaz")
    st.radio("Densidad visual", ["Cómoda", "Compacta"], key="ui_density", horizontal=True)
    st.selectbox("Color de acento", ["Azul", "Verde", "Ambar"], key="ui_accent")
    st.toggle(
        "Mostrar detalles técnicos",
        key="ui_show_details",
        help="Muestra versiones, trazas y datos técnicos cuando la página los tenga.",
    )
    st.info("Estas preferencias solo afectan tu sesión actual.")


def _technical_settings() -> None:  # noqa: C901 - Configuración técnica agrupada.
    if not session.has_permission("settings:read"):
        st.info("Tu rol no permite ver configuración técnica.")
        return

    try:
        current = session.client().get_settings()
    except ApiError as exc:
        design.api_error(exc, "No se pudo cargar la configuración")
        return

    items = _settings_by_key(current.get("settings", []))
    can_write = session.has_permission("settings:write") or session.is_lab_session()

    design.metric_grid(
        [
            ("Proveedor IA", str(current.get("provider", "-")), ""),
            ("Modelo", str(current.get("model", "-")), ""),
            ("Estado IA", "Lista" if current.get("llm_ready") else "No configurada", ""),
            ("Modo", "Simulado" if current.get("is_simulated") else "Real", ""),
        ]
    )

    if current.get("is_simulated"):
        st.warning("El proveedor de IA está en modo simulado o sin credenciales reales.")

    st.subheader("Proveedor de IA")
    provider = st.selectbox(
        "Proveedor",
        options=["genai_lab", "gemini", "mock"],
        index=["genai_lab", "gemini", "mock"].index(
            _value(items, "llm.provider", "genai_lab")
            if _value(items, "llm.provider", "genai_lab")
            in {"genai_lab", "gemini", "mock"}
            else "genai_lab"
        ),
        format_func=lambda value: {
            "genai_lab": "GenAI Lab (gateway)",
            "gemini": "Google Gemini directo",
            "mock": "Simulado local",
        }[value],
        disabled=not can_write,
    )
    provider_key = (
        "llm.genai_lab_api_key" if provider == "genai_lab" else "llm.gemini_api_key"
    )
    legacy_lab_key = provider == "genai_lab" and _is_set(items, "llm.api_key")
    if _is_set(items, provider_key) or legacy_lab_key:
        masked_key = (
            _masked(items, provider_key)
            if _is_set(items, provider_key)
            else _masked(items, "llm.api_key")
        )
        st.success(f"Clave guardada para este proveedor: {masked_key}")
        st.caption("Deja el campo vacío para conservarla.")
    api_key = st.text_input(
        "Nueva API key",
        type="password",
        value="",
        disabled=provider == "mock" or not can_write,
    )

    base_url = _value(items, "llm.base_url", DEFAULT_GENAI_LAB_BASE_URL)
    if provider == "genai_lab":
        base_url = DEFAULT_GENAI_LAB_BASE_URL
        st.caption("Gateway configurado automáticamente para este laboratorio.")

    known_models = (
        list(GENAI_LAB_CHAT_MODELS)
        if provider == "genai_lab"
        else list(FALLBACK_MODELS) if provider == "gemini" else ["mock"]
    )
    saved_model = _value(items, "llm.model", "gemini-2.5-flash")
    if saved_model not in known_models:
        if provider == "genai_lab":
            st.warning(
                f"El modelo guardado «{saved_model}» ya no está disponible. "
                "Selecciona un modelo vigente."
            )
            saved_model = (
                "genailab-maas-gpt-4o"
                if "genailab-maas-gpt-4o" in known_models
                else known_models[0]
            )
        else:
            known_models.insert(0, saved_model)
    model = st.selectbox(
        "Modelo",
        options=known_models,
        index=known_models.index(saved_model),
        disabled=provider == "mock" or not can_write,
    )

    c1, c2 = st.columns(2)
    with c1:
        temperature = st.slider(
            "Temperatura",
            min_value=0.0,
            max_value=1.0,
            value=float(_value(items, "llm.temperature", "0.1") or 0.1),
            step=0.05,
            disabled=not can_write,
        )
    with c2:
        budget = st.number_input(
            "Presupuesto por vacante (USD)",
            min_value=0.0,
            max_value=1000.0,
            value=float(_value(items, "llm.budget_usd_per_job", "5.0") or 5.0),
            step=0.5,
            disabled=not can_write,
        )

    bias_audit = st.toggle(
        "Auditoría de sesgo con modelo",
        value=_flag(items, "llm.enable_bias_audit", True),
        disabled=not can_write,
    )

    if can_write:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Verificar conexión", width="stretch"):
                try:
                    result = session.client().test_credentials(
                        provider=provider, api_key=api_key, model=model, base_url=base_url
                    )
                    if result.get("ok"):
                        st.success(result.get("message", "Conexión verificada."))
                    else:
                        st.error(result.get("message", "No se pudo verificar."))
                except ApiError as exc:
                    design.api_error(exc, "No se pudo verificar")
        with b2:
            if st.button("Guardar IA", type="primary", width="stretch"):
                values = {
                    "llm.provider": provider,
                    "llm.model": model,
                    "llm.base_url": base_url.strip(),
                    "llm.temperature": str(temperature),
                    "llm.budget_usd_per_job": str(budget),
                    "llm.enable_bias_audit": "true" if bias_audit else "false",
                }
                if api_key.strip():
                    values[provider_key] = api_key.strip()
                try:
                    session.client().update_settings(
                        values, updated_by=session.current_user().get("email", "ui")
                    )
                    st.success("Configuración guardada.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo guardar")

    if provider == "genai_lab":
        st.caption(
            f"Catálogo validado: {len(GENAI_LAB_CHAT_MODELS)} modelos de generación. "
            f"Además están registrados {', '.join(GENAI_LAB_EMBEDDING_MODELS)} "
            f"(embeddings) y {', '.join(GENAI_LAB_TRANSCRIPTION_MODELS)} "
            "(audio), que no son válidos para evaluar texto y por eso no aparecen "
            "en el selector."
        )

    st.subheader("Integraciones")
    try:
        provider_status = session.client().email_provider()
        design.badge_row(
            [
                (
                    "Correo simulado"
                    if provider_status.get("is_simulated")
                    else "Correo configurado",
                    "warning" if provider_status.get("is_simulated") else "success",
                )
            ]
        )
    except ApiError:
        st.info("No se pudo consultar el estado del correo.")

    if st.session_state.get("ui_show_details"):
        st.subheader("Configuración pública")
        st.dataframe(
            [
                {
                    "Clave": item["key"],
                    "Grupo": item["group"],
                    "Valor": item["value"],
                    "Secreto": "Sí" if item["is_secret"] else "No",
                    "Establecido": "Sí" if item["is_set"] else "No",
                }
                for item in current.get("settings", [])
            ],
            width="stretch",
            hide_index=True,
        )


def render() -> None:
    design.page_header(
        "Configuración",
        "Ajustes simples de interfaz y estado técnico autorizado.",
        "Control",
    )

    user = session.current_user()
    design.badge_row(
        [
            (user.get("email", "sin usuario"), "info"),
            (role_label(user.get("role", "")), "muted"),
        ]
    )

    prefs_tab, tech_tab = st.tabs(["Personalización", "Sistema"])
    with prefs_tab:
        _preferences()
    with tech_tab:
        _technical_settings()


render()
