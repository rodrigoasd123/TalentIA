"""Auditoría de TalentIA."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import date_short, short_id, tone_for_status  # noqa: E402

PII_KEYS = {"email", "phone", "full_name", "national_id", "recipient", "candidate_name"}


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("***" if key in PII_KEYS else _mask(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value


def render() -> None:
    if not session.require_permission("audit:read"):
        return

    design.page_header(
        "Auditoría",
        "Registro de eventos, cambios y verificaciones de integridad.",
        "Control",
    )

    try:
        integrity = session.client().verify_audit()
    except ApiError as exc:
        design.api_error(exc, "No se pudo verificar la auditoría")
        return

    if integrity.get("verified"):
        st.success(integrity.get("message", "Cadena íntegra."))
    else:
        st.error(integrity.get("message", "La cadena presenta inconsistencias."))
        st.warning(
            integrity.get("diagnostic")
            or "La evidencia histórica debe investigarse; no se modifica automáticamente."
        )
        st.caption(
            "Acción recomendada: conserva una copia de la base, identifica el evento "
            "indicado y revisa si la base fue importada o alterada fuera de TalentIA."
        )

    design.metric_grid(
        [
            ("Eventos", str(integrity.get("total_events", 0)), ""),
            ("Críticos", str(integrity.get("by_severity", {}).get("critical", 0)), ""),
            ("Altos", str(integrity.get("by_severity", {}).get("high", 0)), ""),
            ("Cadena", "Íntegra" if integrity.get("verified") else "Revisar", ""),
        ]
    )

    f1, f2, f3, f4 = st.columns([1.3, 1.3, 1, 0.8])
    with f1:
        action = st.text_input("Acción", placeholder="evaluation.completed")
    with f2:
        resource = st.text_input("Recurso", placeholder="ID de postulación")
    with f3:
        severity = st.selectbox("Severidad", ["Todas", "critical", "high", "medium", "low", "info"])
    with f4:
        limit = st.number_input("Máximo", min_value=10, max_value=1000, value=150, step=50)

    try:
        events = session.client().audit_events(
            action=action or None,
            resource_id=resource or None,
            severity=None if severity == "Todas" else severity,
            limit=int(limit),
        )
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar eventos")
        return

    if not events:
        design.empty_state("Sin eventos", "No hay registros con los filtros actuales.")
        return

    st.dataframe(
        [
            {
                "Fecha": date_short(event.get("timestamp")),
                "Actor": event.get("actor_type", "-"),
                "Acción": event.get("action", "-"),
                "Recurso": (
                    f"{event.get('resource_type', '-')}:"
                    f"{short_id(event.get('resource_id', ''))}"
                ),
                "Severidad": event.get("severity", "-"),
                "Política": (event.get("policy_result") or "-")[:80],
                "Traza": short_id(event.get("trace_id", "")),
            }
            for event in events
        ],
        width="stretch",
        hide_index=True,
    )

    selected = st.selectbox(
        "Detalle",
        options=[event["event_id"] for event in events],
        format_func=lambda value: next(
            f"{date_short(event.get('timestamp'))} · {event.get('action')}"
            for event in events
            if event["event_id"] == value
        ),
    )
    event = next(event for event in events if event["event_id"] == selected)
    design.badge_row([(event.get("severity", "info"), tone_for_status(event.get("severity", "")))])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Estado anterior")
        st.json(_mask(event.get("previous_state") or {}), expanded=False)
    with c2:
        st.subheader("Estado nuevo")
        st.json(_mask(event.get("new_state") or {}), expanded=False)
    st.subheader("Metadatos")
    st.json(_mask(event.get("metadata") or {}), expanded=False)


render()
