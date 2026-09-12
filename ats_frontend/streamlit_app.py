"""Aplicación Streamlit principal de TalentIA."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import role_label  # noqa: E402

PAGES = [
    {
        "group": "Trabajo diario",
        "path": "views/home.py",
        "title": "Inicio",
        "icon": ":material/home:",
        "permissions": (),
    },
    {
        "group": "Trabajo diario",
        "path": "views/jobs.py",
        "title": "Vacantes",
        "icon": ":material/business_center:",
        "permissions": ("job:read",),
    },
    {
        "group": "Trabajo diario",
        "path": "views/candidates.py",
        "title": "Candidatos",
        "icon": ":material/groups:",
        "permissions": ("candidate:read", "application:read"),
    },
    {
        "group": "Trabajo diario",
        "path": "views/applications.py",
        "title": "Postulaciones",
        "icon": ":material/assignment:",
        "permissions": ("application:read", "candidate:write"),
    },
    {
        "group": "Seguimiento",
        "path": "views/pipeline.py",
        "title": "Pipeline",
        "icon": ":material/view_kanban:",
        "permissions": ("application:read",),
    },
    {
        "group": "Seguimiento",
        "path": "views/evaluations.py",
        "title": "Evaluaciones",
        "icon": ":material/rule:",
        "permissions": ("evaluation:run", "application:read"),
    },
    {
        "group": "Seguimiento",
        "path": "views/reviews.py",
        "title": "Revisión humana",
        "icon": ":material/verified_user:",
        "permissions": ("review:decide",),
    },
    {
        "group": "Seguimiento",
        "path": "views/imports.py",
        "title": "Importación histórica",
        "icon": ":material/upload_file:",
        "permissions": ("import:read", "import:upload"),
    },
    {
        "group": "Expediente",
        "path": "views/candidate360.py",
        "title": "Candidate 360",
        "icon": ":material/account_circle:",
        "permissions": ("candidate:pii:read",),
    },
    {
        "group": "Expediente",
        "path": "views/document_analysis.py",
        "title": "Análisis documental",
        "icon": ":material/document_search:",
        "permissions": ("candidate:pii:read",),
    },
    {
        "group": "Control",
        "path": "views/reports.py",
        "title": "Reportes",
        "icon": ":material/monitoring:",
        "permissions": ("application:read",),
    },
    {
        "group": "Inteligencia Artificial",
        "path": "views/ai_usage.py",
        "title": "Consumo de IA",
        "icon": ":material/analytics:",
        "permissions": (),
    },
    {
        "group": "Sistema",
        "path": "views/audit.py",
        "title": "Registro de auditoría",
        "icon": ":material/history:",
        "permissions": ("audit:read",),
    },
    {
        "group": "Control",
        "path": "views/settings.py",
        "title": "Configuración",
        "icon": ":material/settings:",
        "permissions": (),
    },
]


def _allowed(page: dict[str, object]) -> bool:
    required = tuple(page.get("permissions", ()))
    return session.has_any(*required)


def _navigation() -> dict[str, list[st.Page]]:
    groups: dict[str, list[st.Page]] = {}
    for page in PAGES:
        if not _allowed(page):
            continue
        groups.setdefault(str(page["group"]), []).append(
            st.Page(
                APP_DIR / str(page["path"]),
                title=str(page["title"]),
                icon=str(page["icon"]),
            )
        )
    return {group: pages for group, pages in groups.items() if pages}


def _sidebar_status() -> None:
    design.render_sidebar_brand()
    user = session.current_user()

    st.sidebar.caption("Usuario")
    st.sidebar.write(user.get("email", "Sin usuario"))
    st.sidebar.markdown(
        design.badge(role_label(str(user.get("role", ""))), "info"),
        unsafe_allow_html=True,
    )

    if session.is_lab_session():
        st.sidebar.warning("Entorno de laboratorio. Usa solo datos ficticios.")

    with st.sidebar.expander("Estado de la API", expanded=False):
        try:
            health = session.client().health()
            st.success("API disponible")
            st.write(f"Ambiente: {health.get('environment', '-')}")
            st.write(f"Base de datos: {health.get('database', '-')}")
            st.write(f"Version: {health.get('version', '-')}")
        except ApiError as exc:
            st.error("API no disponible")
            st.caption(str(exc))

    session.render_sidebar_footer()


def main() -> None:
    design.configure_page()
    session.init_state()
    design.inject_css()

    if not session.ensure_session():
        st.stop()

    pages = _navigation()
    if not pages:
        design.page_header("Sin secciones disponibles", "Tu rol no tiene páginas asignadas.")
        st.stop()

    current = st.navigation(pages, position="sidebar", expanded=True)
    _sidebar_status()
    current.run()


if __name__ == "__main__":
    main()
