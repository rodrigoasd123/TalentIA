"""Base general de candidatos: consulta, alta y edición."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status  # noqa: E402


def _number(label: str, value=None, **kwargs):
    return st.number_input(label, value=value, **kwargs)


def _fields(current: dict | None = None) -> dict:
    c = current or {}
    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("Nombre completo *", value=c.get("full_name", ""))
        client = st.text_input("Cliente", value=c.get("client", ""))
        record_date = st.date_input(
            "Fecha",
            value=date.fromisoformat(c["record_date"]) if c.get("record_date") else date.today(),
        )
        recruiter = st.text_input("Reclutador", value=c.get("recruiter", ""))
        source = st.text_input("Fuente de reclutamiento", value=c.get("source", "manual"))
        q = st.text_input("Q", value=c.get("q", ""))
        birth_text = st.text_input(
            "Fecha de nacimiento (AAAA-MM-DD)", value=c.get("birth_date") or ""
        )
        age = _number(
            "Edad (si no hay fecha de nacimiento)", c.get("age"), min_value=0, max_value=120, step=1
        )
        national_id = st.text_input("DNI", value=c.get("national_id", ""))
        bgc = st.text_input("BGC", value=c.get("bgc", ""))
    with col2:
        email = st.text_input("Correo", value=c.get("email", ""))
        phone = st.text_input("Teléfono", value=c.get("phone", ""))
        location = st.text_input("Ubicación", value=c.get("location", ""))
        technical = st.text_area("Conocimientos técnicos", value=c.get("technical_knowledge", ""))
        equifax = _number("Deuda Equifax", c.get("equifax_debt"), min_value=0.0)
        salary = _number("Expectativa salarial", c.get("salary_expectation"), min_value=0.0)
        requested = st.text_input("Solicitado", value=c.get("requested", ""))
        role_ctc = _number("CTC para el rol", c.get("role_ctc"), min_value=0.0)
        variation = _number(
            "% variación CTC", c.get("ctc_variation_pct"), min_value=-1000.0, max_value=1000.0
        )
        availability = st.text_input("Disponibilidad", value=c.get("availability", ""))
        notes = st.text_area("Otros datos / observaciones", value=c.get("notes", ""))
    birth_date = birth_text.strip() or None
    if birth_date:
        try:
            birth_date = date.fromisoformat(birth_date).isoformat()
        except ValueError:
            st.error("La fecha de nacimiento debe usar el formato AAAA-MM-DD.")
    return {
        "full_name": full_name.strip(),
        "client": client.strip(),
        "record_date": record_date.isoformat(),
        "recruiter": recruiter.strip(),
        "source": source.strip(),
        "q": q.strip(),
        "birth_date": birth_date,
        "age": age,
        "national_id": national_id.strip(),
        "bgc": bgc.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "location": location.strip(),
        "technical_knowledge": technical.strip(),
        "equifax_debt": equifax,
        "salary_expectation": salary,
        "requested": requested.strip(),
        "role_ctc": role_ctc,
        "ctc_variation_pct": variation,
        "availability": availability.strip(),
        "notes": notes.strip(),
    }


def render() -> None:  # noqa: C901
    if not session.require_permission("candidate:read", "application:read"):
        return
    design.page_header(
        "Base general de candidatos",
        "Una ficha por persona, independiente de sus postulaciones a vacantes.",
        "Trabajo diario",
    )
    try:
        candidates = session.client().list_candidates()
        applications = session.client().list_applications()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar los candidatos")
        return
    list_tab, create_tab, edit_tab = st.tabs(["Base general", "Registrar", "Editar"])
    with list_tab:
        query = st.text_input("Buscar", placeholder="Nombre, cliente, reclutador, DNI o vacante")
        states_by_candidate: dict[str, list[str]] = {}
        for application in applications:
            states_by_candidate.setdefault(application["candidate_id"], []).append(
                f"{application['job_code']}: {app_status(application['status'])}"
            )
        visible = candidates
        if query.strip():
            needle = query.casefold().strip()
            visible = [
                item
                for item in candidates
                if needle
                in " ".join(
                    str(item.get(key, ""))
                    for key in (
                        "full_name",
                        "client",
                        "recruiter",
                        "national_id",
                        "source",
                    )
                ).casefold()
            ]
        st.dataframe(
            [
                {
                    "Candidato": item["full_name"],
                    "Cliente": item.get("client", ""),
                    "Estados por postulación": ", ".join(
                        states_by_candidate.get(item["id"], [])
                    ) or "Sin postulación",
                    "Fecha": item.get("record_date"),
                    "Reclutador": item.get("recruiter", ""),
                    "Fuente": item.get("source", ""),
                    "Q": item.get("q", ""),
                    "Edad": item.get("age"),
                    "DNI": item.get("national_id", ""),
                    "Disponibilidad": item.get("availability", ""),
                }
                for item in visible
            ],
            width="stretch",
            hide_index=True,
        )
    can_write = session.has_permission("candidate:write")
    with create_tab:
        if not can_write:
            st.info("Tu rol no tiene permiso para registrar candidatos.")
        else:
            with st.form("candidate_create"):
                payload = _fields()
                submitted = st.form_submit_button("Registrar candidato", type="primary")
            if submitted:
                try:
                    session.client().create_candidate(payload)
                    st.success("Candidato registrado en la base general.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo registrar")
    with edit_tab:
        if not can_write:
            st.info("Tu rol no tiene permiso para editar candidatos.")
        elif not candidates:
            design.empty_state("Sin candidatos", "Registra una persona para poder editarla.")
        else:
            selected_id = st.selectbox(
                "Candidato",
                [item["id"] for item in candidates],
                format_func=lambda value: next(
                    item["full_name"] for item in candidates if item["id"] == value
                ),
            )
            current = next(item for item in candidates if item["id"] == selected_id)
            with st.form(f"candidate_edit_{selected_id}"):
                st.caption(
                    "Los estados de selección se modifican en Pipeline y siempre "
                    "pertenecen a una postulación concreta."
                )
                payload = _fields(current)
                submitted = st.form_submit_button("Guardar cambios", type="primary")
            if submitted:
                payload["expected_version"] = current["version"]
                try:
                    session.client().update_candidate(selected_id, payload)
                    st.success("Ficha actualizada.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo actualizar")


render()
