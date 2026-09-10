"""Dashboard ejecutivo, embudo de conversión y panel de equidad."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Dashboard · VERA ATS", page_icon="📈", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}

st.title("📈 Dashboard")

try:
    summary = client.dashboard_summary()
    jobs = client.list_jobs()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

# ── Métricas principales ─────────────────────────────────────────────────────

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Vacantes activas", summary["active_jobs"])
m2.metric("Candidatos", summary["total_candidates"])
m3.metric("Candidaturas", summary["total_applications"])
m4.metric("Esta semana", summary["applications_this_week"])
m5.metric("Pendientes de revisión", summary["pending_review"])

n1, n2, n3, n4 = st.columns(4)
n1.metric(
    "Puntuación media",
    f"{summary['avg_score']:.1f}" if summary["avg_score"] else "—",
)
n2.metric(
    "Tasa de preselección",
    f"{summary['shortlist_rate']:.0%}" if summary["shortlist_rate"] is not None else "—",
)
n3.metric(
    "Tasa de rechazo",
    f"{summary['rejection_rate']:.0%}" if summary["rejection_rate"] is not None else "—",
)
n4.metric("Eventos auditados", summary["audit_events"])

st.divider()

tabs = st.tabs(["🔻 Embudo", "⚖️ Equidad", "📊 Fuentes y etapas"])

# ── Embudo ───────────────────────────────────────────────────────────────────

with tabs[0]:
    job_filter = st.selectbox(
        "Vacante",
        options=["(todas)"] + [j["code"] for j in jobs],
        key="funnel_job",
    )
    job_id = (
        None if job_filter == "(todas)"
        else next(j["id"] for j in jobs if j["code"] == job_filter)
    )

    try:
        funnel = client.funnel(job_id)
    except ApiError as exc:
        st.error(str(exc))
        funnel = []

    if funnel:
        st.caption(
            "Se cuentan las candidaturas que **alcanzaron o superaron** cada etapa, "
            "no las que están en ella ahora. Contar solo el estado actual daría un "
            "embudo lleno de ceros en cuanto la gente avanza."
        )
        frame = pd.DataFrame(
            [
                {
                    "Etapa": row["stage"],
                    "Candidaturas": row["count"],
                    "Conversión desde la etapa previa": (
                        f"{row['conversion_from_previous']:.0%}"
                        if row["conversion_from_previous"] is not None else "—"
                    ),
                    "Conversión total": (
                        f"{row['conversion_from_start']:.0%}"
                        if row["conversion_from_start"] is not None else "—"
                    ),
                }
                for row in funnel
            ]
        )
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.bar_chart(frame.set_index("Etapa")["Candidaturas"], horizontal=True)

# ── Equidad ──────────────────────────────────────────────────────────────────

with tabs[1]:
    st.subheader("Panel de equidad")
    st.markdown(
        """
        Un sesgo algorítmico casi nunca es visible caso a caso: ninguna evaluación
        dice «he penalizado a esta persona por X». Lo que ocurre es que, al mirar
        el conjunto, aparece un patrón.

        Lo que se analiza aquí **no son atributos protegidos** — el sistema no los
        almacena para evaluar, y esa es precisamente la protección. Se miden
        indicadores observables de la calidad del proceso.
        """
    )

    equity_job = st.selectbox(
        "Ámbito",
        options=["(todas las vacantes)"] + [j["code"] for j in jobs],
        key="equity_job",
    )
    equity_job_id = (
        None if equity_job.startswith("(")
        else next(j["id"] for j in jobs if j["code"] == equity_job)
    )

    try:
        report = client.equity_report(equity_job_id)
    except ApiError as exc:
        st.error(str(exc))
        st.stop()

    if report["sample_size"] == 0:
        st.info("No hay evaluaciones en este ámbito todavía.")
        st.stop()

    if not report["reliable"]:
        st.warning(
            f"Muestra de solo {report['sample_size']} evaluaciones. Con tan pocos "
            "casos cualquier patrón es ruido estadístico: los indicadores se "
            "muestran, pero no deberían usarse para tomar decisiones.",
            icon="📉",
        )

    metrics = report["metrics"]
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Evaluaciones", metrics["evaluations"])
    e2.metric(
        "Puntuación media",
        f"{metrics['score_mean']:.1f}" if metrics["score_mean"] else "—",
    )
    e3.metric(
        "Dispersión",
        f"±{metrics['score_stdev']:.1f}" if metrics["score_stdev"] is not None else "—",
        help="Desviación típica. Si es muy baja, el sistema no está diferenciando perfiles.",
    )
    e4.metric(
        "Revisión humana",
        f"{metrics['human_review_rate']:.0%}" if metrics["human_review_rate"] is not None else "—",
    )

    f1, f2, f3 = st.columns(3)
    f1.metric(
        "Evidencia verificada",
        f"{metrics['evidence_rate_mean']:.0%}" if metrics["evidence_rate_mean"] is not None else "—",
        help="Solo sobre las evaluaciones que llegaron a la fase semántica.",
    )
    agreement = metrics.get("human_agreement", {})
    f2.metric(
        "Acuerdo con la IA",
        f"{agreement['agreement_rate']:.0%}" if agreement.get("agreement_rate") is not None else "—",
        help=(
            "De las revisiones ya resueltas. Un acuerdo del 100% puede significar "
            "que la IA acierta siempre o que nadie la está revisando de verdad."
        ),
    )
    f3.metric(
        "Alertas de sesgo",
        f"{metrics['bias_flag_rate']:.0%}" if metrics["bias_flag_rate"] is not None else "—",
    )

    st.divider()

    if report["findings"]:
        st.subheader("Patrones detectados")
        for finding in report["findings"]:
            icono = SEVERITY_ICON.get(finding["severity"], "•")
            with st.container(border=True):
                st.markdown(f"{icono} **{finding['title']}**")
                st.write(finding["detail"])
                st.caption(f"Recomendación: {finding['recommendation']}")
    else:
        st.success(
            "No se han detectado patrones anómalos en la distribución agregada.",
            icon="✅",
        )

    if metrics.get("failed_filters"):
        with st.expander("Filtros que más excluyen"):
            st.caption(
                "Un filtro que descarta a casi todo el mundo suele indicar un "
                "criterio mal calibrado, no un mercado laboral vacío."
            )
            st.dataframe(
                [
                    {"Filtro": k, "Candidaturas excluidas": v}
                    for k, v in metrics["failed_filters"].items()
                ],
                use_container_width=True, hide_index=True,
            )

# ── Fuentes y etapas ─────────────────────────────────────────────────────────

with tabs[2]:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Origen de las candidaturas")
        try:
            sources = client.source_analytics()
        except ApiError as exc:
            st.error(str(exc))
            sources = []
        if sources:
            st.dataframe(
                [
                    {
                        "Origen": s["source"],
                        "Candidaturas": s["applications"],
                        "Puntuación media": s["avg_score"] or "—",
                        "Tasa de avance": (
                            f"{s['shortlist_rate']:.0%}"
                            if s["shortlist_rate"] is not None else "—"
                        ),
                    }
                    for s in sources
                ],
                use_container_width=True, hide_index=True,
            )

    with col_b:
        st.subheader("Tiempo medio por etapa")
        st.caption("Horas que las candidaturas llevan en su etapa actual.")
        try:
            durations = client.stage_durations()
        except ApiError as exc:
            st.error(str(exc))
            durations = {}
        if durations:
            st.dataframe(
                [
                    {"Etapa": k, "Horas (media)": v, "Días": round(v / 24, 1)}
                    for k, v in sorted(durations.items(), key=lambda x: -x[1])
                ],
                use_container_width=True, hide_index=True,
            )

    st.divider()
    st.subheader("Distribución por estado")
    if summary["by_status"]:
        st.bar_chart(pd.Series(summary["by_status"]), horizontal=True)
