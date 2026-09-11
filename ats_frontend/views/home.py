"""Inicio operativo de TalentIA."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:  # pragma: no cover - Streamlit suele instalar Altair como dependencia.
    alt = None

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status, days_from_hours, score  # noqa: E402


def _bar_chart(frame: pd.DataFrame, x: str, y: str, height: int = 260) -> None:
    if frame.empty:
        design.empty_state("Sin datos", "Todavía no hay información suficiente para graficar.")
        return
    if alt is None:
        st.bar_chart(frame.set_index(y)[x], horizontal=True)
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(color="#2563EB")
        .encode(
            x=alt.X(f"{x}:Q", title=x),
            y=alt.Y(f"{y}:N", title="", sort="-x"),
            tooltip=list(frame.columns),
        )
        .properties(height=height)
    )
    st.altair_chart(chart, width="stretch")


def render() -> None:  # noqa: C901 - Dashboard operativo en una sola pantalla.
    design.page_header(
        "Inicio",
        "Resumen simple de la operación: vacantes, postulaciones, revisiones y alertas.",
        "TalentIA",
    )
    st.info(
        "Los puntajes son orientativos. TalentIA no toma decisiones de contratación por sí solo."
    )

    client = session.client()
    try:
        summary = client.dashboard_summary()
        jobs = client.list_jobs()
        applications = client.list_applications()
    except ApiError as exc:
        design.api_error(exc, "No se pudo cargar el inicio")
        return

    design.metric_grid(
        [
            ("Vacantes abiertas", str(summary.get("active_jobs", 0)), "Procesos disponibles"),
            ("Candidatos", str(summary.get("total_candidates", 0)), "Personas únicas"),
            (
                "Postulaciones",
                str(summary.get("total_applications", 0)),
                "Participaciones en vacantes",
            ),
            ("Pendientes", str(summary.get("pending_review", 0)), "Revisión humana"),
            ("Puntaje medio", score(summary.get("avg_score")), "Solo evaluaciones existentes"),
        ]
    )

    design.section_label("Filtros rápidos")
    f1, f2 = st.columns([1, 1])
    with f1:
        selected_job = st.selectbox(
            "Vacante",
            options=["Todas"] + [job["code"] for job in jobs],
            key="home_job_filter",
        )
    with f2:
        selected_status = st.selectbox(
            "Estado",
            options=["Todos", *sorted({app["status"] for app in applications})],
            format_func=lambda value: value if value in {"Todas", "Todos"} else app_status(value),
            key="home_status_filter",
        )

    visible_apps = applications
    if selected_job != "Todas":
        visible_apps = [app for app in visible_apps if app["job_code"] == selected_job]
    if selected_status != "Todos":
        visible_apps = [app for app in visible_apps if app["status"] == selected_status]

    tab_estado, tab_embudo, tab_alertas = st.tabs(["Estado actual", "Embudo", "Alertas"])

    with tab_estado:
        by_status: dict[str, int] = {}
        for app in visible_apps:
            by_status[app["status"]] = by_status.get(app["status"], 0) + 1
        frame = pd.DataFrame(
            [
                {"Etapa": app_status(status), "Candidaturas": count}
                for status, count in by_status.items()
            ]
        )
        _bar_chart(frame, "Candidaturas", "Etapa")
        if visible_apps:
            st.dataframe(
                [
                    {
                        "Candidato": app["candidate_name"],
                        "Vacante": app["job_code"],
                        "Estado": app_status(app["status"]),
                        "Puntaje": score(app.get("score")),
                        "Tiempo en etapa": days_from_hours(app.get("hours_in_stage")),
                    }
                    for app in visible_apps[:200]
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            design.empty_state("Sin resultados", "Cambia los filtros para ver postulaciones.")

    with tab_embudo:
        job_id = None
        if selected_job != "Todas":
            job_id = next((job["id"] for job in jobs if job["code"] == selected_job), None)
        try:
            funnel = client.funnel(job_id)
        except ApiError as exc:
            design.api_error(exc, "No se pudo cargar el embudo")
            funnel = []
        frame = pd.DataFrame(
            [{"Etapa": app_status(row["stage"]), "Candidaturas": row["count"]} for row in funnel]
        )
        _bar_chart(frame, "Candidaturas", "Etapa", height=320)
        st.caption(
            "El embudo cuenta candidaturas que alcanzaron cada etapa. "
            "No es una decisión automática."
        )

    with tab_alertas:
        try:
            alerts = client.sla_alerts(72)
        except ApiError as exc:
            design.api_error(exc, "No se pudieron cargar las alertas")
            alerts = []
        if alerts:
            st.warning("Hay postulaciones con más de 72 horas en la misma etapa.")
            st.dataframe(
                [
                    {
                        "Candidato": alert["candidate"],
                        "Vacante": alert["job_code"],
                        "Etapa": app_status(alert["status"]),
                        "Dias": alert["days"],
                    }
                    for alert in alerts
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.success("No hay alertas operativas con el umbral actual.")

        if session.has_permission("settings:read"):
            try:
                agent = client.agent_health()
                provider = "Simulado" if agent.get("is_simulated") else agent.get("provider", "-")
                design.badge_row(
                    [
                        (
                            f"Proveedor IA: {provider}",
                            "warning" if agent.get("is_simulated") else "success",
                        ),
                        (f"Modelo: {agent.get('model', '-')}", "info"),
                    ]
                )
            except ApiError:
                st.info("El estado del proveedor de IA no está disponible para este momento.")


render()
