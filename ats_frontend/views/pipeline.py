"""Pipeline de selección."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import (  # noqa: E402
    APPLICATION_STAGES,
    app_status,
    days_from_hours,
    score,
    tone_for_status,
)

TERMINAL_STATUSES = {"rejected", "hired", "withdrawn"}


def _application_label(application_id: str, applications: list[dict]) -> str:
    app = next((item for item in applications if item["id"] == application_id), None)
    if not app:
        return application_id
    return f"{app['candidate_name']} · {app['job_code']} · {app_status(app['status'])}"


def _render_board(columns: dict[str, list[dict]], only_active: bool) -> None:
    stages = [
        status
        for status in APPLICATION_STAGES
        if columns.get(status) and not (only_active and status in TERMINAL_STATUSES)
    ]
    if not stages:
        design.empty_state("Sin postulaciones", "No hay tarjetas para los filtros actuales.")
        return
    for start in range(0, len(stages), 4):
        row = stages[start : start + 4]
        view_columns = st.columns(len(row))
        for column, status in zip(view_columns, row, strict=True):
            with column:
                st.markdown(f"### {app_status(status)}")
                cards = columns.get(status, [])
                st.caption(f"{len(cards)} postulaciones")
                for card in cards[:12]:
                    with st.container(border=True):
                        st.write(f"**{card['candidate_name']}**")
                        st.caption(
                            f"{card['job_code']} · Puntaje {score(card.get('score'))} · "
                            f"{days_from_hours(card.get('hours_in_stage'))}"
                        )
                if len(cards) > 12:
                    st.caption(f"{len(cards) - 12} más")


def _render_table(applications: list[dict]) -> None:
    if not applications:
        design.empty_state("Sin postulaciones", "No hay registros para mostrar.")
        return
    st.dataframe(
        [
            {
                "Candidato": item["candidate_name"],
                "Vacante": item["job_code"],
                "Estado": app_status(item["status"]),
                "Puntaje": score(item.get("score")),
                "Tiempo en etapa": days_from_hours(item.get("hours_in_stage")),
                "ID": item["id"][:8],
            }
            for item in applications
        ],
        width="stretch",
        hide_index=True,
    )


def _transition_panel(applications: list[dict]) -> None:
    if not session.has_permission("application:transition"):
        st.info("Tu rol puede consultar el pipeline, pero no cambiar estados.")
        return
    if not applications:
        return

    st.subheader("Cambiar estado")
    selected = st.selectbox(
        "Postulación",
        options=[item["id"] for item in applications],
        format_func=lambda value: _application_label(value, applications),
        key="pipeline_transition_application",
    )
    current = next(item for item in applications if item["id"] == selected)
    current_status = current["status"]
    targets = [status for status in APPLICATION_STAGES if status != current_status]
    target = st.selectbox(
        "Nuevo estado",
        options=targets,
        format_func=app_status,
        key="pipeline_target_status",
    )
    needs_reason = target in TERMINAL_STATUSES or current_status in TERMINAL_STATUSES
    reason = st.text_area(
        "Motivo",
        placeholder="Explica el motivo del cambio.",
        key="pipeline_transition_reason",
    )
    if needs_reason:
        st.warning("Este cambio es sensible y requiere motivo.")
    confirmed = st.checkbox("Confirmo que deseo solicitar este cambio al backend")
    disabled = not confirmed or (needs_reason and len(reason.strip()) < 5)
    if st.button("Actualizar estado", type="primary", disabled=disabled):
        try:
            with st.spinner("Validando transición con el backend..."):
                result = session.client().transition(
                    selected, target_status=target, reason=reason.strip()
                )
            st.success(
                f"Estado actualizado: {app_status(result['from'])} -> {app_status(result['to'])}."
            )
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo cambiar el estado")


def render() -> None:
    if not session.require_permission("application:read"):
        return

    design.page_header(
        "Pipeline",
        "Sigue el avance de postulaciones por etapa, sin depender de arrastrar y soltar.",
        "Seguimiento",
    )

    try:
        jobs = session.client().list_jobs()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar vacantes")
        return

    f1, f2 = st.columns([2, 1])
    with f1:
        selected_job = st.selectbox(
            "Vacante",
            options=["Todas"] + [job["code"] for job in jobs],
            key="pipeline_job",
        )
    with f2:
        only_active = st.toggle("Ocultar estados cerrados", value=True)

    job_id = None
    if selected_job != "Todas":
        job_id = next((job["id"] for job in jobs if job["code"] == selected_job), None)

    try:
        applications = session.client().list_applications(job_id)
    except ApiError as exc:
        design.api_error(exc, "No se pudo cargar el pipeline")
        return

    q1, q2, q3 = st.columns([1.5, 1, 1])
    with q1:
        query = st.text_input("Buscar candidato o ID", key="pipeline_search")
    with q2:
        status_filter = st.selectbox(
            "Estado",
            ["Todos"] + APPLICATION_STAGES,
            format_func=lambda value: value if value == "Todos" else app_status(value),
            key="pipeline_status_filter",
        )
    with q3:
        cv_filter = st.selectbox(
            "CV",
            ["Todos", "Asociado", "Pendiente"],
            key="pipeline_cv_filter",
        )

    visible_applications = applications
    if query.strip():
        needle = query.strip().lower()
        visible_applications = [
            item for item in visible_applications
            if needle in f"{item['candidate_name']} {item['id']} {item['job_code']}".lower()
        ]
    if status_filter != "Todos":
        visible_applications = [
            item for item in visible_applications if item["status"] == status_filter
        ]
    if cv_filter != "Todos":
        expected = cv_filter == "Asociado"
        visible_applications = [
            item for item in visible_applications if item.get("has_resume") is expected
        ]
    columns = {
        status: [item for item in visible_applications if item["status"] == status]
        for status in APPLICATION_STAGES
    }

    review_state_count = sum(
        1 for item in applications if item["status"] == "human_review"
    )
    open_review_count = sum(1 for item in applications if item.get("has_open_review"))
    design.metric_grid(
        [
            ("Postulaciones", str(len(visible_applications)), "En los filtros actuales"),
            ("Estado revisión", str(review_state_count), "Etapa del pipeline"),
            ("Casos abiertos", str(open_review_count), "Cola humana real"),
            ("Preselección", str(len(columns.get("shortlisted", []))), ""),
        ]
    )
    if review_state_count != open_review_count:
        st.info(
            "Las cifras de revisión representan conceptos distintos: "
            f"{review_state_count} postulaciones están en esa etapa y "
            f"{open_review_count} tienen un caso abierto en la cola."
        )

    board_tab, table_tab, action_tab = st.tabs(["Tablero", "Tabla", "Cambiar estado"])
    with board_tab:
        for status in APPLICATION_STAGES:
            if status in columns:
                design.badge_row([(app_status(status), tone_for_status(status))])
        _render_board(columns, only_active)
    with table_tab:
        visible = [
            item
            for item in visible_applications
            if not (only_active and item["status"] in TERMINAL_STATUSES)
        ]
        _render_table(visible)
    with action_tab:
        _transition_panel(visible_applications)


render()
