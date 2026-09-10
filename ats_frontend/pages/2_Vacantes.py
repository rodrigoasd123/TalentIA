"""Convocatorias y sus criterios de evaluación."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Vacantes · VERA ATS", page_icon="📋", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

st.title("📋 Convocatorias")
st.caption("Bases de convocatoria ficticias y los criterios que VERA aplica sobre ellas.")

try:
    jobs = client.list_jobs()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not jobs:
    st.warning("No hay convocatorias cargadas.")
    st.stop()

selected_code = st.selectbox(
    "Vacante",
    options=[job["code"] for job in jobs],
    format_func=lambda code: next(
        f"{j['code']} — {j['title']}" for j in jobs if j["code"] == code
    ),
)
job = next(j for j in jobs if j["code"] == selected_code)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Puntuación mínima", f"{job['minimum_score']:.0f}")
col2.metric("Margen de revisión", f"± {job['review_threshold']:.0f}")
col3.metric("Experiencia mínima", f"{job['min_years_experience']:.0f} años")
col4.metric("Filtros definidos", job["hard_filter_count"])

st.divider()

with st.expander("🔎 Búsqueda manual asistida en LinkedIn"):
    st.caption("VERA prepara la consulta; no abre, navega ni extrae información de LinkedIn.")
    if st.button("Generar consulta Boolean"):
        try:
            suggestion = client.sourcing_query(job["id"])
            st.code(suggestion["boolean_query"], language="text")
            st.info(suggestion["notice"])
        except ApiError as exc:
            st.error(str(exc))

st.divider()

tab_criterios, tab_bases = st.tabs(["⚖️ Criterios aplicados", "📄 Bases de convocatoria"])

with tab_criterios:
    left, right = st.columns([1, 1])

    with left:
        st.subheader("Pesos de evaluación")
        st.caption(
            "Solo se aplican a la fase semántica. El total lo calcula el backend a "
            "partir de estos pesos, no el modelo."
        )
        weights = job["weights"]
        st.bar_chart(weights, horizontal=True)
        total = sum(weights.values())
        if abs(total - 100) > 0.01:
            st.error(f"Los pesos suman {total:.1f} y deben sumar 100.")
        else:
            st.success(f"Los pesos suman {total:.0f}.", icon="✅")

    with right:
        st.subheader("Requisitos obligatorios")
        st.caption(
            "Se evalúan en código, de forma determinística. Ningún filtro excluyente "
            "depende del modelo de lenguaje."
        )
        for skill in job["mandatory_skills"]:
            st.markdown(f"- `{skill}`")
        if not job["mandatory_skills"]:
            st.caption("No se han declarado habilidades obligatorias.")

        st.info(
            "Cada filtro excluyente declara en su definición una **base legal**: por "
            "qué ese criterio es pertinente para el puesto. Un requisito que nadie "
            "puede justificar por escrito probablemente no debería excluir a nadie.",
            icon="⚖️",
        )

    st.divider()
    st.subheader("Cómo se decide")
    st.markdown(
        f"""
        1. Se aplican los **{job['hard_filter_count']} filtros determinísticos**. Quien
           no cumple un requisito obligatorio no llega a consumir una llamada al modelo.
        2. Quien los supera pasa a **evaluación semántica**, que puntúa cada dimensión
           y debe citar evidencia literal del CV.
        3. Cada cita se **verifica contra el documento**. Si demasiadas no se
           localizan, la evaluación se descarta.
        4. El **total se calcula en código** con los pesos de arriba.
        5. Una puntuación entre **{job['minimum_score'] - job['review_threshold']:.0f}**
           y **{job['minimum_score'] + job['review_threshold']:.0f}** cae en zona gris
           y pasa a revisión humana.
        """
    )

with tab_bases:
    try:
        brief = client.job_brief(selected_code)
        st.markdown(brief)
    except ApiError as exc:
        st.error(str(exc))
