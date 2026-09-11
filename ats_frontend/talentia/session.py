"""Sesión, permisos y cliente HTTP para el frontend."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st
from api_client import DEFAULT_BASE_URL, ApiError, TalentIAApiClient
from talentia import design
from talentia.formatters import role_label

AUTH_TOKEN = "auth_access_token"
REFRESH_TOKEN = "auth_refresh_token"
AUTH_USER = "auth_user"
AUTH_EXPIRES = "auth_expires_at"
AUTH_MODE = "auth_mode"


def init_state() -> None:
    st.session_state.setdefault("api_base_url", DEFAULT_BASE_URL)
    st.session_state.setdefault("ui_density", "Cómoda")
    st.session_state.setdefault("ui_accent", "Azul")
    st.session_state.setdefault("ui_show_details", False)


def client() -> TalentIAApiClient:
    return TalentIAApiClient(
        st.session_state.get("api_base_url", DEFAULT_BASE_URL),
        access_token=st.session_state.get(AUTH_TOKEN, ""),
    )


def anonymous_client() -> TalentIAApiClient:
    return TalentIAApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))


def current_user() -> dict[str, Any]:
    return st.session_state.get(AUTH_USER, {}) or {}


def permissions() -> set[str]:
    return set(current_user().get("permissions", []))


def has_permission(permission: str) -> bool:
    return permission in permissions()


def has_any(*required: str) -> bool:
    if not required:
        return True
    available = permissions()
    return any(permission in available for permission in required)


def is_lab_session() -> bool:
    return bool(current_user().get("is_lab_session")) or st.session_state.get(AUTH_MODE) == "lab"


def role() -> str:
    return str(current_user().get("role", ""))


def is_authenticated() -> bool:
    return bool(current_user()) and (
        st.session_state.get(AUTH_MODE) == "lab" or bool(st.session_state.get(AUTH_TOKEN))
    )


def clear_session(message: str = "") -> None:
    for key in (AUTH_TOKEN, REFRESH_TOKEN, AUTH_USER, AUTH_EXPIRES, AUTH_MODE):
        st.session_state.pop(key, None)
    if message:
        st.session_state["auth_notice"] = message


def _store_login(pair: dict[str, Any]) -> None:
    st.session_state[AUTH_TOKEN] = pair.get("access_token", "")
    st.session_state[REFRESH_TOKEN] = pair.get("refresh_token", "")
    st.session_state[AUTH_EXPIRES] = time.time() + float(pair.get("expires_in", 0) or 0)
    st.session_state[AUTH_MODE] = "jwt"
    profile = client().me()
    user = pair.get("user", {})
    st.session_state[AUTH_USER] = {
        "id": user.get("id") or profile.get("user_id", ""),
        "email": user.get("email") or profile.get("email", ""),
        "full_name": user.get("full_name", ""),
        "role": user.get("role") or profile.get("role", ""),
        "permissions": profile.get("permissions", []),
        "is_lab_session": profile.get("is_lab_session", False),
    }


def _store_lab_session(profile: dict[str, Any]) -> None:
    st.session_state[AUTH_MODE] = "lab"
    st.session_state.pop(AUTH_TOKEN, None)
    st.session_state.pop(REFRESH_TOKEN, None)
    st.session_state.pop(AUTH_EXPIRES, None)
    st.session_state[AUTH_USER] = {
        "id": profile.get("user_id", "lab-recruiter"),
        "email": profile.get("email", "recruiter@example.test"),
        "full_name": "Sesion de laboratorio",
        "role": profile.get("role", "recruiter"),
        "permissions": profile.get("permissions", []),
        "is_lab_session": True,
    }


def logout() -> None:
    refresh = st.session_state.get(REFRESH_TOKEN, "")
    if refresh:
        try:
            client().logout(refresh)
        except ApiError:
            pass
    clear_session("Sesión cerrada correctamente.")
    st.rerun()


def _token_expired() -> bool:
    expires = st.session_state.get(AUTH_EXPIRES)
    if not expires:
        return False
    return time.time() >= float(expires)


def ensure_session() -> bool:
    init_state()
    if st.session_state.get(AUTH_MODE) == "jwt" and _token_expired():
        clear_session("Tu sesión expiró por seguridad. Inicia sesión nuevamente.")

    if is_authenticated():
        return True

    render_login()
    return False


def require_permission(*required: str) -> bool:
    if has_any(*required):
        return True
    design.page_header("Acceso denegado", "Esta sección no está disponible para tu rol.")
    st.info(
        f"Rol activo: {role_label(role())}. "
        "Si necesitas acceso, solicita el cambio a un responsable."
    )
    return False


def render_login() -> None:  # noqa: C901 - Pantalla Streamlit con validaciones visibles.
    notice = st.session_state.pop("auth_notice", "")
    light_logo = design.ASSETS / "tcs-logo-light.jpeg"
    dark_logo = design.ASSETS / "tcs-logo-dark.jpeg"

    st.markdown(design.brand_html("Acceso al ATS"), unsafe_allow_html=True)
    if light_logo.exists():
        st.image(str(light_logo), width=360)
    st.title("TalentIA centraliza vacantes, candidatos y revisiones humanas.")
    st.write(
        "La IA ayuda a ordenar evidencia documental, pero no aprueba, "
        "rechaza ni contrata personas automáticamente."
    )
    st.info(
        "Diseñado para uso diario: pocas opciones visibles, estados claros "
        "y acciones sensibles siempre confirmadas."
    )

    st.subheader("Iniciar sesión")
    st.caption("Usa tu usuario corporativo o entra al laboratorio local si está disponible.")
    if notice:
        st.warning(notice)

    base_url = st.text_input(
        "URL de la API",
        key="api_base_url",
        help="Por defecto usa la API local de TalentIA.",
    )
    api_ok = False
    lab_available = False
    try:
        health = anonymous_client().health()
        api_ok = True
        lab_available = health.get("environment") == "development"
        st.success("API disponible.")
        if lab_available:
            st.info("Entorno de laboratorio: trabaja solo con datos ficticios.")
    except ApiError:
        st.error(f"No se pudo conectar con la API en {base_url}.")

    show_password = st.checkbox("Mostrar contraseña", value=False)
    with st.form("login-form"):
        email = st.text_input("Usuario o correo", placeholder="usuario@example.test")
        password = st.text_input(
            "Contraseña",
            type="default" if show_password else "password",
            placeholder="Escribe tu contraseña",
        )
        submitted = st.form_submit_button(
            "Entrar a TalentIA",
            type="primary",
            disabled=not api_ok,
            width="stretch",
        )

    if submitted:
        try:
            with st.spinner("Verificando acceso..."):
                pair = anonymous_client().login(email.strip(), password)
                _store_login(pair)
            st.rerun()
        except ApiError as exc:
            if exc.status_code == 401:
                st.error("Credenciales incorrectas. Revisa usuario y contraseña.")
            else:
                design.api_error(exc, "No se pudo iniciar sesión")

    if lab_available:
        if st.button("Continuar en laboratorio", width="stretch"):
            try:
                profile = anonymous_client().me()
                _store_lab_session(profile)
                st.rerun()
            except ApiError as exc:
                design.api_error(exc, "El laboratorio no está disponible")

    if dark_logo.exists():
        st.caption("Marca institucional cargada desde los archivos proporcionados.")


def render_sidebar_footer() -> None:
    user = current_user()
    role_text = role_label(str(user.get("role", "")))
    st.sidebar.divider()
    st.sidebar.caption("Sesión")
    st.sidebar.write(user.get("email", "Sin correo"))
    st.sidebar.write(role_text)
    if is_lab_session():
        st.sidebar.warning("Laboratorio local")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        logout()
