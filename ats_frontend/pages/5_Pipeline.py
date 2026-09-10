"""Pipeline visual del proceso de selección."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Pipeline · VERA ATS", page_icon="🗂️", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

#: Orden y etiqueta de cada columna. El catálogo es cerrado para que las métricas
#: sean comparables entre vacantes distintas.
STAGES = [
    ("new", "Nuevos", "⚪"),
    ("resume_processed", "CV procesado", "📄"),
    ("under_evaluation", "En evaluación", "⚙️"),
    ("human_review", "Revisión humana", "👤"),
    ("shortlisted", "Preseleccionados", "⭐"),
    ("approved_for_interview", "Aprobados", "✅"),
    ("interview_scheduled", "Entrevista agendada", "📅"),
    ("interviewed", "Entrevistados", "🗣️"),
    ("approved", "Finalistas", "🏆"),
    ("hired", "Contratados", "🎉"),
    ("rejected", "Rechazados", "🔴"),
    ("withdrawn", "Retirados", "⬅️"),
]

st.title("🗂️ Pipeline")
st.caption("Estado de todas las candidaturas del proceso.")

try:
    jobs = client.list_jobs()
    columns = client.pipeline()
    applications = client.list_applications()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

# ── Filtros ──────────────────────────────────────────────────────────────────

f1, f2, f3 = st.columns([2, 1, 1])
with f1:
    job_filter = st.selectbox(
        "Vacante",
        options=["(todas)"] + [j["code"] for j in jobs],
        format_func=lambda c: c if c == "(todas)"
        else next(f"{j['code']} — {j['title']}" for j in jobs if j["code"] == c),
    )
with f2:
    min_score = st.slider("Puntuación mínima", 0, 100, 0, step=5)
with f3:
    only_pending = st.toggle("Solo pendientes", value=False,
                             help="Oculta rechazados, contratados y retirados.")

if job_filter != "(todas)":
    job_id = next(j["id"] for j in jobs if j["code"] == job_filter)
    try:
        columns = client.pipeline(job_id)
        applications = client.list_applications(job_id)
    except ApiError as exc:
        st.error(str(exc))
        st.stop()

terminal = {"rejected", "hired", "withdrawn"}


def visible(card: dict) -> bool:
    if min_score and (card.get("score") or 0) < min_score:
        return False
    return True


# ── Resumen ──────────────────────────────────────────────────────────────────

total = len(applications)
in_review = len(columns.get("human_review", []))
shortlisted = sum(len(columns.get(s, [])) for s in ("shortlisted", "approved_for_interview"))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Candidaturas", total)
m2.metric("En revisión humana", in_review)
m3.metric("Preseleccionados", shortlisted)
m4.metric("Rechazados", len(columns.get("rejected", [])))

st.divider()

# ── Tablero ──────────────────────────────────────────────────────────────────

active_stages = [
    (key, label, icon)
    for key, label, icon in STAGES
    if columns.get(key) and not (only_pending and key in terminal)
]

if not active_stages:
    st.info("No hay candidaturas que coincidan con los filtros.")
    st.stop()

# Se reparten en filas de cuatro para que las tarjetas sigan siendo legibles.
for start in range(0, len(active_stages), 4):
    row = active_stages[start : start + 4]
    cols = st.columns(len(row))
    for column, (key, label, icon) in zip(cols, row, strict=True):
        cards = [c for c in columns.get(key, []) if visible(c)]
        with column:
            st.markdown(f"#### {icon} {label}")
            st.caption(f"{len(cards)} candidatura(s)")
            for card in cards[:15]:
                with st.container(border=True):
                    st.markdown(f"**{card['candidate_name']}**")
                    detalle = f"`{card['job_code']}`"
                    if card.get("score") is not None:
                        detalle += f" · **{card['score']:.1f}**"
                    st.caption(detalle)
                    horas = card.get("hours_in_stage", 0)
                    if horas > 72 and key not in terminal:
                        st.caption(f"⏱️ {horas / 24:.1f} días en esta etapa")
                    if st.button(
                        "Ver 360", key=f"go-{card['application_id']}",
                        use_container_width=True,
                    ):
                        st.session_state["selected_application"] = card["application_id"]
                        st.switch_page("pages/7_Candidate360.py")
            if len(cards) > 15:
                st.caption(f"… y {len(cards) - 15} más")

st.divider()

# ── Alertas de estancamiento ─────────────────────────────────────────────────

with st.expander("⏱️ Candidaturas estancadas"):
    st.caption(
        "Que alguien lleve días esperando sin que nadie lo sepa es un fallo de "
        "proceso, no de la persona."
    )
    horas = st.slider("Umbral (horas en la misma etapa)", 24, 720, 72, step=24)
    try:
        alerts = client.sla_alerts(horas)
    except ApiError as exc:
        st.error(str(exc))
        alerts = []
    if alerts:
        st.dataframe(
            [
                {
                    "Candidato": a["candidate"],
                    "Vacante": a["job_code"],
                    "Etapa": a["status"],
                    "Días": a["days"],
                }
                for a in alerts
            ],
            use_container_width=True, hide_index=True,
        )
    else:
        st.success("Ninguna candidatura supera el umbral.", icon="✅")
