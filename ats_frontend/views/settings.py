"""Configuración y preferencias."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia.formatters import role_label  # noqa: E402

from app.infrastructure.llm.model_catalog import (  # noqa: E402
    GENAI_LAB_EMBEDDING_MODELS,
    GENAI_LAB_TRANSCRIPTION_MODELS,
)
from talentia import design, session  # noqa: E402


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


def _provider_management(providers: list[dict], can_write: bool) -> None:  # noqa: C901
    st.subheader("Proveedores y modelos")
    st.caption(
        "Las credenciales son write-only: se cifran en el backend y nunca vuelven al navegador."
    )
    st.dataframe(
        [
            {
                "Proveedor": item["display_name"],
                "ID": item["id"],
                "Adaptador": item["adapter_type"],
                "Estado": "Habilitado" if item["is_enabled"] else "Deshabilitado",
                "Credencial": "Configurada" if item["credential_is_set"] else "Pendiente",
                "Modelos": len(item.get("models", [])),
            }
            for item in providers
        ],
        width="stretch",
        hide_index=True,
    )

    if can_write:
        with st.expander("Agregar proveedor OpenAI-compatible"):
            with st.form("create-ai-provider"):
                provider_id = st.text_input("Identificador", placeholder="mi_proveedor")
                display_name = st.text_input("Nombre visible", placeholder="Mi proveedor")
                base_url = st.text_input("URL base HTTPS", placeholder="https://api.ejemplo.com")
                submitted = st.form_submit_button("Agregar proveedor")
            if submitted:
                try:
                    session.client().create_provider(provider_id, display_name, base_url)
                    st.success("Proveedor agregado. Ahora configura su credencial y modelos.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo agregar el proveedor")

    for provider in providers:
        provider_id = str(provider["id"])
        with st.expander(f"{provider['display_name']} · {provider_id}"):
            st.caption(f"URL: {provider.get('base_url') or 'Administrada por el adaptador nativo'}")
            if can_write and provider.get("adapter_type") != "mock":
                provider_enabled = bool(provider["is_enabled"])
                if st.button(
                    "Deshabilitar proveedor" if provider_enabled else "Habilitar proveedor",
                    key=f"toggle-provider-{provider_id}",
                ):
                    try:
                        session.client().update_provider(
                            provider_id,
                            expected_version=int(provider["version"]),
                            is_enabled=not provider_enabled,
                        )
                        st.rerun()
                    except ApiError as exc:
                        design.api_error(exc, "No se pudo cambiar el proveedor")
            if can_write and provider.get("adapter_type") != "mock":
                credential = st.text_input(
                    "Nueva credencial",
                    type="password",
                    key=f"provider-secret-{provider_id}",
                    placeholder="Ya configurada" if provider["credential_is_set"] else "Pendiente",
                )
                if st.button("Guardar credencial", key=f"save-secret-{provider_id}"):
                    if not credential:
                        st.warning("Escribe una credencial para guardarla.")
                    else:
                        try:
                            session.client().set_provider_credential(
                                provider_id,
                                credential,
                                expected_version=int(provider["version"]),
                            )
                            st.success("Credencial cifrada y guardada.")
                            st.rerun()
                        except ApiError as exc:
                            design.api_error(exc, "No se pudo guardar la credencial")

            models = list(provider.get("models", []))
            if models:
                st.dataframe(
                    [
                        {
                            "Modelo": item["display_name"],
                            "ID remoto": item["model_id"],
                            "Estado": "Habilitado" if item["is_enabled"] else "Deshabilitado",
                            "Entrada / 1M": item.get("input_price_per_million"),
                            "Salida / 1M": item.get("output_price_per_million"),
                        }
                        for item in models
                    ],
                    width="stretch",
                    hide_index=True,
                )
                if can_write:
                    selected_model = st.selectbox(
                        "Modelo a gestionar",
                        models,
                        format_func=lambda item: str(item["model_id"]),
                        key=f"manage-model-{provider_id}",
                    )
                    enabled = bool(selected_model["is_enabled"])
                    if st.button(
                        "Deshabilitar modelo" if enabled else "Habilitar modelo",
                        key=f"toggle-model-{provider_id}",
                    ):
                        try:
                            session.client().update_provider_model(
                                str(selected_model["id"]),
                                expected_version=int(selected_model["version"]),
                                is_enabled=not enabled,
                            )
                            st.rerun()
                        except ApiError as exc:
                            design.api_error(exc, "No se pudo cambiar el modelo")

            if can_write and provider.get("adapter_type") != "mock":
                with st.form(f"add-model-{provider_id}"):
                    model_id = st.text_input("ID remoto del nuevo modelo")
                    model_name = st.text_input("Nombre visible del nuevo modelo")
                    col_in, col_out = st.columns(2)
                    with col_in:
                        input_price = st.number_input(
                            "USD entrada / 1M tokens", min_value=0.0, value=None
                        )
                    with col_out:
                        output_price = st.number_input(
                            "USD salida / 1M tokens", min_value=0.0, value=None
                        )
                    add_model = st.form_submit_button("Agregar modelo")
                if add_model:
                    try:
                        session.client().create_provider_model(
                            provider_id,
                            model_id=model_id,
                            display_name=model_name,
                            input_price_per_million=input_price,
                            output_price_per_million=output_price,
                        )
                        st.success("Modelo agregado al catálogo.")
                        st.rerun()
                    except ApiError as exc:
                        design.api_error(exc, "No se pudo agregar el modelo")


def _technical_settings() -> None:  # noqa: C901 - Configuración técnica agrupada.
    if not session.has_permission("settings:read"):
        st.info("Tu rol no permite ver configuración técnica.")
        return

    try:
        current = session.client().get_settings()
        providers = session.client().list_providers()
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
    known_models = session.client().list_models()
    if not known_models:
        st.error("No hay modelos habilitados. Habilita al menos el simulador local.")
        return
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
    provider = next(
        (
            str(item["id"])
            for item in providers
            if any(child["model_id"] == model for child in item.get("models", []))
        ),
        "unknown",
    )
    provider_label = {
        "gemini": "Google Gemini directo",
        "openai": "OpenAI directo",
        "genai_lab": "GenAI Lab",
    }.get(provider, provider)
    st.caption(f"Proveedor asignado automáticamente: {provider_label}.")

    secret_key = {
        "gemini": "llm.gemini_api_key",
        "openai": "llm.openai_api_key",
        "genai_lab": "llm.genai_lab_api_key",
    }.get(provider)
    secret_item = items.get(secret_key or "", {})
    if secret_key:
        api_key = st.text_input(
            f"Credencial de {provider_label}",
            type="password",
            placeholder=(
                "Ya configurada; escribe una nueva para reemplazarla"
                if secret_item.get("is_set")
                else "Ingresa la credencial"
            ),
            disabled=not can_write,
            help="La clave se envía al backend, se cifra y nunca vuelve a mostrarse.",
        )
        if can_write and st.button("Guardar credencial", width="stretch"):
            if not api_key.strip():
                st.warning("Escribe una credencial para guardarla.")
            else:
                try:
                    session.client().update_settings(
                        {secret_key: api_key.strip()},
                        updated_by=session.current_user().get("email", "ui"),
                    )
                    st.success("Credencial guardada de forma cifrada.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo guardar la credencial")

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

    _provider_management(providers, can_write)

    if can_write:
        with st.expander("Benchmark gobernado de modelos"):
            st.caption(
                "Usa tres casos sintéticos versionados. No envía CVs ni datos de candidatos. "
                "Cada ejecución consume llamadas reales de los modelos seleccionados."
            )
            selected = st.multiselect(
                "Modelos a comparar (máximo 5)", known_models, max_selections=5
            )
            baseline = st.selectbox("Modelo base", selected or [model], disabled=not selected)
            confirm_benchmark = st.checkbox("Confirmo el consumo de la ejecución del benchmark")
            if st.button("Ejecutar benchmark", disabled=not selected):
                try:
                    with st.spinner("Ejecutando suite sintética..."):
                        result = session.client().benchmark_models(
                            models=selected,
                            baseline_model=baseline,
                            confirmed=confirm_benchmark,
                        )
                    st.success(
                        f"Suite {result.get('suite_version')} ejecutada. "
                        f"Hash: {result.get('suite_hash')}"
                    )
                    st.dataframe(result.get("ranking", []), hide_index=True)
                except ApiError as exc:
                    design.api_error(exc, "No se pudo ejecutar el benchmark")

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
