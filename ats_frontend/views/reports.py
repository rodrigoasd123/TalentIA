"""Reportes y dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:  # pragma: no cover
    alt = None

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status, percent, score  # noqa: E402


def _chart(frame: pd.DataFrame, x: str, y: str) -> None:
    if frame.empty:
        design.empty_state("Sin datos", "No hay datos suficientes para mostrar esta vista.")
        return
    if alt is None:
        st.bar_chart(frame.set_index(y)[x], horizontal=True)
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(color="#2563EB")
        .encode(x=alt.X(f"{x}:Q"), y=alt.Y(f"{y}:N", sort="-x"), tooltip=list(frame.columns))
        .properties(height=300)
    )
    st.altair_chart(chart, width="stretch")


def render() -> None:  # noqa: C901 - Reporte resumido con pestañas.
    if not session.require_permission("application:read"):
        return

    design.page_header(
        "Reportes",
        "Vista previa de indicadores. "
        "Las exportaciones se muestran solo cuando existe endpoint real.",
        "Control",
    )

    try:
        summary = session.client().dashboard_summary()
        jobs = session.client().list_jobs()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar reportes")
        return

    design.metric_grid(
        [
            ("Vacantes abiertas", str(summary.get("active_jobs", 0)), ""),
            ("Postulaciones", str(summary.get("total_applications", 0)), ""),
            ("Esta semana", str(summary.get("applications_this_week", 0)), ""),
            ("Preselección", percent(summary.get("shortlist_rate")), ""),
            ("Revisión", str(summary.get("pending_review", 0)), "Pendientes"),
        ]
    )

    selected_job = st.selectbox(
        "Vacante",
        options=["Todas"] + [job["code"] for job in jobs],
        key="reports_job",
    )
    job_id = (
        None
        if selected_job == "Todas"
        else next(
            (job["id"] for job in jobs if job["code"] == selected_job),
            None,
        )
    )

    funnel_tab, sources_tab, equity_tab, exports_tab = st.tabs(
        ["Embudo", "Fuentes y tiempos", "Equidad", "Exportaciones"]
    )

    with funnel_tab:
        try:
            funnel = session.client().funnel(job_id)
        except ApiError as exc:
            design.api_error(exc, "No se pudo cargar el embudo")
            funnel = []
        frame = pd.DataFrame(
            [{"Etapa": app_status(row["stage"]), "Candidaturas": row["count"]} for row in funnel]
        )
        _chart(frame, "Candidaturas", "Etapa")
        st.caption("Los puntajes y embudos orientan la operación; no constituyen decisión.")

    with sources_tab:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Fuentes")
            try:
                sources = session.client().source_analytics()
            except ApiError as exc:
                design.api_error(exc, "No se pudieron cargar fuentes")
                sources = []
            if sources:
                st.dataframe(
                    [
                        {
                            "Fuente": item["source"],
                            "Postulaciones": item["applications"],
                            "Puntaje medio": score(item.get("avg_score")),
                            "Avance": percent(item.get("shortlist_rate")),
                        }
                        for item in sources
                    ],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("Sin datos de origen.")
        with col_b:
            st.subheader("Tiempo por etapa")
            try:
                durations = session.client().stage_durations(job_id)
            except ApiError as exc:
                design.api_error(exc, "No se pudieron cargar tiempos")
                durations = {}
            if durations:
                st.dataframe(
                    [
                        {
                            "Etapa": app_status(stage),
                            "Horas promedio": value,
                            "Días": round(value / 24, 1),
                        }
                        for stage, value in sorted(durations.items(), key=lambda item: -item[1])
                    ],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("Sin tiempos registrados.")

    with equity_tab:
        if not session.has_permission("audit:read"):
            st.info("El panel de equidad requiere permiso de auditoría.")
        else:
            try:
                report = session.client().equity_report(job_id)
            except ApiError as exc:
                design.api_error(exc, "No se pudo cargar el panel de equidad")
                report = {}
            if not report or report.get("sample_size", 0) == 0:
                design.empty_state("Sin evaluaciones", "Aún no hay muestra para analizar equidad.")
            else:
                metrics = report.get("metrics", {}) or {}
                design.metric_grid(
                    [
                        ("Evaluaciones", str(metrics.get("evaluations", 0)), ""),
                        ("Puntaje medio", score(metrics.get("score_mean")), ""),
                        ("Revisión humana", percent(metrics.get("human_review_rate")), ""),
                        ("Alertas sesgo", percent(metrics.get("bias_flag_rate")), ""),
                    ]
                )
                if not report.get("reliable"):
                    st.warning("La muestra es pequeña; interpreta estos indicadores con cautela.")
                findings = report.get("findings", []) or []
                if findings:
                    for finding in findings:
                        with st.container(border=True):
                            st.write(f"**{finding.get('title', '-')}**")
                            st.write(finding.get("detail", ""))
                            st.caption(f"Recomendación: {finding.get('recommendation', '-')}")
                else:
                    st.success("No se detectaron patrones anómalos en la muestra actual.")

    with exports_tab:
        st.subheader("Disponibilidad de exportaciones")
        st.dataframe(
            [
                {
                    "Reporte": "Traza de decisión por postulación",
                    "CSV": "Disponible en Candidate 360",
                    "Excel": "Sin endpoint",
                    "PDF": "Sin endpoint",
                },
                {
                    "Reporte": "Dashboard general",
                    "CSV": "Sin endpoint",
                    "Excel": "Sin endpoint",
                    "PDF": "Sin endpoint",
                },
                {
                    "Reporte": "Historial de reportes",
                    "CSV": "Sin endpoint",
                    "Excel": "Sin endpoint",
                    "PDF": "Sin endpoint",
                },
            ],
            width="stretch",
            hide_index=True,
        )
        st.info("TalentIA no simula descargas: si no hay archivo real, el botón no aparece.")


render()
