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

from app.infrastructure.llm.model_catalog import (  # noqa: E402
    GENAI_LAB_EMBEDDING_MODELS,
    GENAI_LAB_TRANSCRIPTION_MODELS,
    SELECTABLE_LLM_MODELS,
    provider_for_model,
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

    st.subheader("Modelo de IA")
    known_models = list(SELECTABLE_LLM_MODELS)
    saved_model = _value(items, "llm.model", "gemini-2.5-flash")
    if saved_model not in known_models:
        st.warning(f"El modelo guardado «{saved_model}» ya no está disponible.")
        saved_model = known_models[0]
    model = st.selectbox(
        "Modelo",
        options=known_models,
        index=known_models.index(saved_model),
        disabled=not can_write,
        help="TalentIA selecciona automáticamente el proveedor y la clave correspondiente.",
    )
    provider = provider_for_model(model)
    provider_label = "Google Gemini directo" if provider == "gemini" else "GenAI Lab"
    st.caption(f"Proveedor asignado automáticamente: {provider_label}.")

    if can_write and model != str(current.get("model", "")):
        try:
            session.client().update_settings(
                {"llm.model": model},
                updated_by=session.current_user().get("email", "ui"),
            )
            st.success(f"Modelo {model} activado.")
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo activar el modelo")

    if can_write and st.button("Verificar modelo", width="stretch"):
        try:
            result = session.client().test_credentials(provider=provider, model=model)
            if result.get("ok"):
                st.success(result.get("message", "Conexión verificada."))
            else:
                st.error(result.get("message", "No se pudo verificar."))
        except ApiError as exc:
            design.api_error(exc, "No se pudo verificar")

    st.caption(
        "Las credenciales están cifradas y se asignan internamente. "
        f"Los modelos de {', '.join(GENAI_LAB_EMBEDDING_MODELS)} (embeddings) y "
        f"{', '.join(GENAI_LAB_TRANSCRIPTION_MODELS)} (audio) no aparecen aquí."
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
