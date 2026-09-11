"""Listado simple de candidatos."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status, days_from_hours, score  # noqa: E402


def _go_candidate360(application_id: str) -> None:
    st.session_state["selected_application"] = application_id
    try:
        st.switch_page(str(APP_DIR / "views" / "candidate360.py"))
    except Exception:
        st.success("Expediente seleccionado. Abre Candidate 360 desde el menú.")


def render() -> None:
    if not session.require_permission("candidate:read", "application:read"):
        return

    design.page_header(
        "Candidatos",
        "Una persona puede participar en varias vacantes. "
        "TalentIA mantiene una sola ficha por persona.",
        "Trabajo diario",
    )

    try:
        applications = session.client().list_applications()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar los candidatos")
        return

    if not applications:
        design.empty_state(
            "Sin candidatos",
            "Registra una postulación o carga una importación histórica para empezar.",
        )
        return

    grouped: dict[str, list[dict]] = defaultdict(list)
    for application in applications:
        grouped[application["candidate_id"]].append(application)

    query = st.text_input(
        "Buscar candidato o vacante", placeholder="Nombre, código de vacante o estado"
    )

    rows = []
    for candidate_id, items in grouped.items():
        first = items[0]
        jobs = ", ".join(sorted({item["job_code"] for item in items}))
        statuses = ", ".join(sorted({app_status(item["status"]) for item in items}))
        latest = sorted(items, key=lambda item: item["applied_at"], reverse=True)[0]
        row = {
            "candidate_id": candidate_id,
            "candidate_name": first["candidate_name"],
            "jobs": jobs,
            "applications": len(items),
            "statuses": statuses,
            "latest_application": latest["id"],
            "latest_status": latest["status"],
            "score": latest.get("score"),
            "hours_in_stage": latest.get("hours_in_stage"),
        }
        rows.append(row)

    if query.strip():
        needle = query.strip().lower()
        rows = [
            row
            for row in rows
            if needle
            in " ".join(
                [row["candidate_name"], row["jobs"], row["statuses"], row["candidate_id"]]
            ).lower()
        ]

    design.metric_grid(
        [
            ("Personas", str(len(grouped)), "Candidatos únicos"),
            ("Postulaciones", str(len(applications)), "Participaciones en vacantes"),
            ("Con evaluación", str(sum(app.get("score") is not None for app in applications)), ""),
        ]
    )

    if not rows:
        design.empty_state("Sin resultados", "Ajusta la búsqueda para ver candidatos.")
        return

    st.dataframe(
        [
            {
                "Candidato": row["candidate_name"],
                "Vacantes": row["jobs"],
                "Postulaciones": row["applications"],
                "Último estado": app_status(row["latest_status"]),
                "Puntaje": score(row["score"]),
                "Tiempo en etapa": days_from_hours(row["hours_in_stage"]),
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )

    selected_name = st.selectbox(
        "Abrir expediente",
        options=[row["latest_application"] for row in rows],
        format_func=lambda value: next(
            f"{row['candidate_name']} · {app_status(row['latest_status'])}"
            for row in rows
            if row["latest_application"] == value
        ),
    )

    if session.has_permission("candidate:pii:read"):
        if st.button("Ver Candidate 360", type="primary"):
            _go_candidate360(selected_name)
    else:
        st.info("Tu rol puede ver el listado, pero no el expediente con datos personales.")


render()
