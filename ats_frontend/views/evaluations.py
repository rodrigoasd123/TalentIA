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

    dimensions = evaluation.get("dimensions", []) or []
    calculated = evaluation.get("score_calculated", bool(dimensions))
    score_label = score(evaluation.get("score")) if calculated else "No calculada"
    design.metric_grid(
        [
            ("Puntaje orientativo", score_label, "Calculado por el backend" if calculated else "Evaluación semántica no ejecutada"),
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
    gaps = evaluation.get("gaps", []) or []
    missing = evaluation.get("missing_requirements", []) or []

    tabs = st.tabs(["Requisitos", "Dimensiones", "Brechas", "Trazabilidad"])
    with tabs[0]:
        if not hard_filters:
            st.caption("No hay filtros determinísticos para mostrar.")
        for item in hard_filters:
            status = item.get("status", "passed" if item.get("passed") else "failed")
            tone = "success" if status == "passed" else "warning" if status == "unverified" else "danger"
            label = item.get("label", "Requisito")
            if status == "unverified":
                label += " · No acreditado"
            elif item.get("mode") == "weighted":
                label += " · Ponderado"
            design.badge_row([(label, tone)])
            st.write(item.get("explanation", ""))
            if status != "passed" and item.get("mode") == "weighted":
                st.caption(f"Penalización configurada: {item.get('penalty_percent', 0):g}%")

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
        current_evaluation = result.get("evaluation", result)
        _render_evaluation(current_evaluation)
    elif session.has_permission("candidate:pii:read"):
        try:
            detail = session.client().candidate_360(selected)
            current_evaluation = detail.get("current_evaluation") or {}
            _render_evaluation(current_evaluation)
        except ApiError:
            current_evaluation = {}
            design.empty_state(
                "Sin evaluación visible",
                "Ejecuta la evaluación o abre Candidate 360 para revisar el expediente.",
            )
    else:
        current_evaluation = {}

    selected_application = next(item for item in applications if item["id"] == selected)
    filters = current_evaluation.get("hard_filters", []) if current_evaluation else []
    needs_validation = any(item.get("status") == "unverified" for item in filters)
    if session.has_permission("review:decide") and (needs_validation or current_evaluation.get("missing_requirements")):
        st.divider()
        st.subheader("Seguimiento humano")
        if selected_application.get("has_open_review"):
            st.info("Esta postulación ya tiene un caso abierto en Revisión humana.")
        else:
            note = st.text_area(
                "Nota para RR. HH.",
                value="Validar información no acreditada en el CV (por ejemplo, nivel de inglés).",
                key=f"manual_review_note_{selected}",
            )
            if st.button("Enviar a revisión humana", type="primary"):
                try:
                    response = session.client().request_manual_review(
                        selected, reason="criterion_unverified", note=note
                    )
                    if response.get("created"):
                        st.success("Caso creado en la cola de Revisión humana.")
                    else:
                        st.info("Ya existía un caso abierto; no se creó un duplicado.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo solicitar la revisión")


render()
