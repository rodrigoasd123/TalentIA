"""Cola de revisión humana."""

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
    app_status,
    date_short,
    recommendation,
    review_reason,
    score,
)

DECISIONS = {
    "approve": "Avanzar a preselección",
    "reject": "Cerrar candidatura",
    "modify": "Modificar puntaje",
    "reevaluate": "Solicitar nueva evaluación",
    "escalate": "Escalar a responsable",
}


def _item_label(item: dict) -> str:
    overdue = " · fuera de plazo" if item.get("is_overdue") else ""
    return f"{item['candidate_name']} · {item['job_code']} · {item['priority']}{overdue}"


def _render_context(item: dict) -> None:
    st.subheader(item["candidate_name"])
    st.caption(
        f"Vacante {item['job_code']} · creado {date_short(item.get('created_at'))} · "
        f"plazo {item.get('sla_hours', '-')} horas"
    )
    design.badge_row(
        [
            (
                item.get("priority", "sin prioridad"),
                "danger" if item.get("is_overdue") else "warning",
            ),
            (item.get("status", "pendiente"), "info"),
        ]
    )
    st.markdown("**Motivos de revisión**")
    for reason in item.get("reasons", []) or []:
        st.write(f"- {review_reason(reason)}")

    if item.get("summary"):
        st.info(item["summary"])
    if item.get("score") is not None:
        st.metric("Puntaje propuesto", score(item["score"]))

    if session.has_permission("candidate:pii:read"):
        try:
            detail = session.client().candidate_360(item["application_id"])
            evaluation = detail.get("current_evaluation")
        except ApiError as exc:
            design.api_error(exc, "No se pudo cargar evidencia")
            evaluation = None
        if evaluation:
            with st.expander("Evidencia de evaluación", expanded=True):
                st.write(evaluation.get("summary") or "Sin resumen.")
                st.caption(f"Resultado: {recommendation(evaluation.get('recommendation', ''))}")
                for dimension in evaluation.get("dimensions", []) or []:
                    st.write(
                        f"**{dimension.get('dimension')}** · {score(dimension.get('score'))}/100"
                    )
                    for evidence in dimension.get("evidence", []) or []:
                        st.write(f"- {evidence.get('quote', '')}")
                st.caption("El endpoint actual no devuelve número de página por cita.")


def _decision_form(item: dict) -> None:
    st.subheader("Decisión humana")
    if item.get("assigned_to"):
        st.caption(f"Asignado a {item['assigned_to']}")
    else:
        if st.button("Asignarme este caso"):
            try:
                session.client().claim_review(item["id"])
                st.success("Caso asignado.")
                st.rerun()
            except ApiError as exc:
                design.api_error(exc, "No se pudo asignar el caso")

    decision = st.radio(
        "Acción",
        options=list(DECISIONS),
        format_func=lambda value: DECISIONS[value],
    )
    score_override = None
    if decision == "modify":
        score_override = st.slider(
            "Nuevo puntaje",
            min_value=0.0,
            max_value=100.0,
            value=float(item.get("score") or 50.0),
            step=0.5,
        )
        st.caption("La evaluación original queda intacta; se registra la modificación.")

    justification = st.text_area(
        "Justificación obligatoria",
        placeholder="Describe la evidencia revisada y el motivo de la decisión.",
        height=120,
    )
    sensitive = decision == "reject"
    if sensitive:
        st.warning("Cerrar una candidatura es una acción sensible. Debe quedar justificada.")
    confirmed = st.checkbox("Confirmo que registré una decisión humana consciente")
    disabled = len(justification.strip()) < 10 or not confirmed
    if st.button("Registrar decisión", type="primary", disabled=disabled):
        try:
            result = session.client().decide_review(
                item["id"],
                decision=decision,
                justification=justification.strip(),
                score_override=score_override,
            )
            st.success(
                f"Decisión registrada. Estado de la postulación: "
                f"{app_status(result['application_status'])}."
            )
            st.session_state.pop("review_item_id", None)
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo registrar la decisión")


def render() -> None:
    if not session.require_permission("review:decide"):
        return

    design.page_header(
        "Revisión humana",
        "Casos que requieren juicio humano, justificación y trazabilidad.",
        "Seguimiento",
    )

    status = st.selectbox(
        "Estado de la cola",
        ["Todos", "pending", "assigned", "in_progress", "expired"],
        format_func=lambda value: "Todos" if value == "Todos" else value,
    )

    try:
        queue = session.client().review_queue(None if status == "Todos" else status)
        stats = session.client().review_statistics()
    except ApiError as exc:
        design.api_error(exc, "No se pudo cargar la cola")
        return

    design.metric_grid(
        [
            ("Pendientes", str(stats.get("pending", 0)), ""),
            ("Fuera de plazo", str(stats.get("overdue", 0)), ""),
            ("Críticos", str(stats.get("by_priority", {}).get("critical", 0)), ""),
            ("Altos", str(stats.get("by_priority", {}).get("high", 0)), ""),
        ]
    )

    if not queue:
        st.success("La cola está vacía.")
        return

    selected = st.selectbox(
        "Caso",
        options=[item["id"] for item in queue],
        format_func=lambda value: _item_label(next(item for item in queue if item["id"] == value)),
        key="review_item_id",
    )
    item = next(item for item in queue if item["id"] == selected)

    context_col, decision_col = st.columns([1.2, 1], gap="large")
    with context_col:
        _render_context(item)
    with decision_col:
        _decision_form(item)

    with st.expander("Motivos frecuentes"):
        by_reason = stats.get("by_reason", {}) or {}
        if by_reason:
            st.dataframe(
                [
                    {"Motivo": review_reason(key), "Casos": value}
                    for key, value in by_reason.items()
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("No hay motivos acumulados.")


render()
