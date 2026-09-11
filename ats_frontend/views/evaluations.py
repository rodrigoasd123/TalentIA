"""Evaluación asistida de postulaciones."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status, percent, recommendation, score  # noqa: E402


def _application_label(application_id: str, applications: list[dict]) -> str:
    app = next((item for item in applications if item["id"] == application_id), None)
    if not app:
        return application_id
    return f"{app['candidate_name']} · {app['job_code']} · {app_status(app['status'])}"


def _render_evaluation(evaluation: dict) -> None:  # noqa: C901 - Vista de resultado completa.
    if not evaluation:
        design.empty_state("Sin evaluación", "Ejecuta una evaluación para ver resultados.")
        return

    design.metric_grid(
        [
            ("Puntaje orientativo", score(evaluation.get("score")), "Calculado por el backend"),
            ("Resultado", recommendation(evaluation.get("recommendation", "")), ""),
            ("Evidencia", percent(evaluation.get("evidence_rate")), "Coincidencia documental"),
            ("Modelo", str(evaluation.get("model", "-")), "Proveedor configurado"),
        ]
    )

    if evaluation.get("requires_human_review"):
        st.warning("Esta postulación requiere revisión humana antes de cualquier decisión.")

    if evaluation.get("summary"):
        st.info(evaluation["summary"])

    hard_filters = evaluation.get("hard_filters", []) or []
    dimensions = evaluation.get("dimensions", []) or []
    gaps = evaluation.get("gaps", []) or []
    missing = evaluation.get("missing_requirements", []) or []

    tabs = st.tabs(["Requisitos", "Dimensiones", "Brechas", "Trazabilidad"])
    with tabs[0]:
        if not hard_filters:
            st.caption("No hay filtros determinísticos para mostrar.")
        for item in hard_filters:
            tone = "success" if item.get("passed") else "danger"
            design.badge_row([(item.get("label", "Requisito"), tone)])
            st.write(item.get("explanation", ""))

    with tabs[1]:
        if not dimensions:
            st.info("No hubo evaluación semántica o no hay dimensiones disponibles.")
        for dimension in dimensions:
            with st.container(border=True):
                dimension_title = dimension.get("dimension", "Dimensión")
                st.subheader(
                    f"{dimension_title} · {score(dimension.get('score'))}/100"
                )
                st.caption(f"Peso: {score(dimension.get('weight'))}%")
                if dimension.get("reasoning"):
                    st.write(dimension["reasoning"])
                evidence = dimension.get("evidence", []) or []
                if evidence:
                    st.markdown("**Evidencia documental**")
                    for span in evidence:
                        label = "Verificada" if span.get("verified") else "No verificada"
                        st.write(f"- {label}: {span.get('quote', '')}")
                        st.caption(f"Coincidencia: {percent(span.get('match_ratio'))}")
                else:
                    st.caption("Información no encontrada para esta dimensión.")

    with tabs[2]:
        if gaps:
            st.subheader("Brechas")
            for item in gaps:
                st.write(f"- {item}")
        if missing:
            st.subheader("Información no encontrada")
            for item in missing:
                st.write(f"- {item}")
        if not gaps and not missing:
            st.success("No hay brechas registradas en esta evaluación.")

    with tabs[3]:
        design.badge_row(
            [
                (f"Agente {evaluation.get('agent_version', '-')}", "info"),
                (f"Costo {evaluation.get('cost_usd', 0):.5f} USD", "muted"),
            ]
        )
        prompts = evaluation.get("prompt_versions", {}) or {}
        if prompts:
            st.dataframe(
                [{"Prompt": key, "Versión": value} for key, value in prompts.items()],
                width="stretch",
                hide_index=True,
            )
        if not session.has_permission("candidate:pii:read"):
            st.caption("Tu rol no permite ver evidencia con datos personales completos.")


def render() -> None:
    if not session.require_permission("evaluation:run", "application:read"):
        return

    design.page_header(
        "Evaluaciones",
        "Evalúa una postulación con evidencia documental y revisión humana cuando corresponda.",
        "Seguimiento",
    )
    st.info("TalentIA no ejecuta decisiones de contratación. La evaluación asistida solo orienta.")

    try:
        applications = session.client().list_applications()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar las postulaciones")
        return

    if not applications:
        design.empty_state("Sin postulaciones", "Registra una postulación antes de evaluar.")
        return

    selected = st.selectbox(
        "Postulación",
        options=[item["id"] for item in applications],
        format_func=lambda value: _application_label(value, applications),
        key="evaluation_application",
    )
    dry_run = st.toggle(
        "Simular sin cambiar estado",
        value=True,
        help="Recomendado para revisar el resultado antes de aplicarlo al proceso.",
    )
    if not dry_run:
        st.warning(
            "El backend puede crear revisión humana o cambiar estados permitidos por política."
        )
    confirmed = st.checkbox("Confirmo que deseo ejecutar esta evaluación")

    if st.button("Ejecutar evaluación asistida", type="primary", disabled=not confirmed):
        try:
            with st.spinner("Ejecutando evaluación asistida..."):
                result = session.client().evaluate_application(selected, dry_run=dry_run)
            st.session_state["last_evaluation_result"] = result
            st.session_state["last_evaluation_application"] = selected
            st.success("Evaluación completada.")
        except ApiError as exc:
            design.api_error(exc, "La evaluación falló")

    result = st.session_state.get("last_evaluation_result")
    if result and st.session_state.get("last_evaluation_application") == selected:
        _render_evaluation(result.get("evaluation", result))
    elif session.has_permission("candidate:pii:read"):
        try:
            detail = session.client().candidate_360(selected)
            _render_evaluation(detail.get("current_evaluation") or {})
        except ApiError:
            design.empty_state(
                "Sin evaluación visible",
                "Ejecuta la evaluación o abre Candidate 360 para revisar el expediente.",
            )


render()
