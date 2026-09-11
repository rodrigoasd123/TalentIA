"""Gestión centralizada de la base general de candidatos."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.candidate_table import (  # noqa: E402
    application_states,
    candidate_csv,
    candidate_rows,
    filter_candidates,
)
from talentia.formatters import app_status  # noqa: E402


def _date_or_none(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _number(label: str, value: Any = None, **kwargs: Any) -> int | float | None:
    return st.number_input(label, value=value, **kwargs)


def _candidate_fields(
    current: dict[str, Any] | None = None,
    *,
    reveal_pii: bool,
    key_prefix: str,
) -> dict[str, Any]:
    candidate = current or {}
    general, work = st.columns(2)
    with general:
        full_name = st.text_input(
            "Nombre completo *",
            value=candidate.get("full_name", ""),
            key=f"{key_prefix}_full_name",
        )
        client = st.text_input(
            "Cliente", value=candidate.get("client", ""), key=f"{key_prefix}_client"
        )
        record_date = st.date_input(
            "Fecha de registro",
            value=_date_or_none(candidate.get("record_date")) or date.today(),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}_record_date",
        )
        recruiter = st.text_input(
            "Reclutador",
            value=candidate.get("recruiter", ""),
            key=f"{key_prefix}_recruiter",
        )
        source = st.text_input(
            "Fuente",
            value=candidate.get("source", "manual"),
            key=f"{key_prefix}_source",
        )
        q_value = st.text_input(
            "Q", value=candidate.get("q", ""), key=f"{key_prefix}_q"
        )
        location = st.text_input(
            "Ubicación",
            value=candidate.get("location", ""),
            key=f"{key_prefix}_location",
        )
    with work:
        requested = st.text_input(
            "Perfil solicitado",
            value=candidate.get("requested", ""),
            key=f"{key_prefix}_requested",
        )
        availability = st.text_input(
            "Disponibilidad",
            value=candidate.get("availability", ""),
            key=f"{key_prefix}_availability",
        )
        technical = st.text_area(
            "Conocimientos técnicos",
            value=candidate.get("technical_knowledge", ""),
            key=f"{key_prefix}_technical",
        )

    payload: dict[str, Any] = {
        "full_name": full_name.strip(),
        "client": client.strip(),
        "record_date": record_date.isoformat(),
        "recruiter": recruiter.strip(),
        "source": source.strip(),
        "q": q_value.strip(),
        "location": location.strip(),
        "requested": requested.strip(),
        "availability": availability.strip(),
        "technical_knowledge": technical.strip(),
    }
    if not reveal_pii:
        st.caption("Los datos personales sensibles no están disponibles para tu rol.")
        return payload

    st.markdown("**Datos personales y económicos**")
    pii_left, pii_right = st.columns(2)
    with pii_left:
        email = st.text_input(
            "Correo", value=candidate.get("email", ""), key=f"{key_prefix}_email"
        )
        phone = st.text_input(
            "Teléfono", value=candidate.get("phone", ""), key=f"{key_prefix}_phone"
        )
        birth_date = st.date_input(
            "Fecha de nacimiento",
            value=_date_or_none(candidate.get("birth_date")),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key=f"{key_prefix}_birth_date",
        )
        age = _number(
            "Edad reportada si no hay fecha de nacimiento",
            candidate.get("age") if not candidate.get("birth_date") else None,
            min_value=0,
            max_value=120,
            step=1,
            key=f"{key_prefix}_age",
            disabled=bool(birth_date),
        )
        national_id = st.text_input(
            "DNI", value=candidate.get("national_id", ""), key=f"{key_prefix}_dni"
        )
        bgc = st.text_input(
            "BGC", value=candidate.get("bgc", ""), key=f"{key_prefix}_bgc"
        )
    with pii_right:
        equifax = _number(
            "Deuda Equifax",
            candidate.get("equifax_debt"),
            min_value=0.0,
            key=f"{key_prefix}_equifax",
        )
        salary = _number(
            "Expectativa salarial",
            candidate.get("salary_expectation"),
            min_value=0.0,
            key=f"{key_prefix}_salary",
        )
        role_ctc = _number(
            "CTC para el rol",
            candidate.get("role_ctc"),
            min_value=0.0,
            key=f"{key_prefix}_role_ctc",
        )
        variation = _number(
            "Variación CTC (%)",
            candidate.get("ctc_variation_pct"),
            min_value=-1000.0,
            max_value=1000.0,
            key=f"{key_prefix}_variation",
        )
        notes = st.text_area(
            "Observaciones",
            value=candidate.get("notes", ""),
            key=f"{key_prefix}_notes",
        )
    payload.update(
        {
            "email": email.strip(),
            "phone": phone.strip(),
            "birth_date": birth_date.isoformat() if birth_date else None,
            "age": None if birth_date else age,
            "national_id": national_id.strip(),
            "bgc": bgc.strip(),
            "equifax_debt": equifax,
            "salary_expectation": salary,
            "role_ctc": role_ctc,
            "ctc_variation_pct": variation,
            "notes": notes.strip(),
        }
    )
    return payload


def _column_config(reveal_pii: bool) -> dict[str, Any]:
    config: dict[str, Any] = {
        "Candidato": st.column_config.TextColumn("Candidato", pinned=True, width="medium"),
        "Estados por postulación": st.column_config.TextColumn(width="large"),
        "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Conocimientos técnicos": st.column_config.TextColumn(width="large"),
    }
    if reveal_pii:
        config.update(
            {
                "Fecha de nacimiento": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Deuda Equifax": st.column_config.NumberColumn(format="localized"),
                "Expectativa salarial": st.column_config.NumberColumn(format="localized"),
                "CTC para el rol": st.column_config.NumberColumn(format="localized"),
                "Variación CTC (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "Observaciones": st.column_config.TextColumn(width="large"),
            }
        )
    return config


def _candidate_form(
    candidate: dict[str, Any] | None,
    *,
    reveal_pii: bool,
    mode: str,
) -> None:
    is_create = mode == "create"
    candidate_key = candidate.get("id", "new") if candidate else "new"
    title = "Nuevo candidato" if is_create else f"Editar: {candidate['full_name']}"
    with st.container(border=True):
        st.subheader(title)
        if not is_create:
            st.caption(
                "Los estados de selección se administran en Pipeline y pertenecen a una vacante."
            )
        with st.form(f"candidate_{mode}_{candidate_key}"):
            payload = _candidate_fields(
                candidate,
                reveal_pii=reveal_pii,
                key_prefix=f"candidate_{mode}_{candidate_key}",
            )
            submitted = st.form_submit_button(
                "Registrar candidato" if is_create else "Guardar cambios",
                type="primary",
                icon=":material/save:",
            )
        if is_create and st.button(
            "Cancelar",
            icon=":material/close:",
            key="cancel_candidate_create",
        ):
            st.session_state["candidate_create_open"] = False
            st.rerun()
        if not submitted:
            return
        if len(payload["full_name"]) < 2:
            st.error("Escribe el nombre completo del candidato.")
            return
        try:
            if is_create:
                session.client().create_candidate(payload)
                st.session_state["candidate_notice"] = "Candidato registrado en la base general."
                st.session_state["candidate_create_open"] = False
            else:
                payload["expected_version"] = candidate["version"]
                session.client().update_candidate(candidate["id"], payload)
                st.session_state["candidate_notice"] = "Ficha actualizada correctamente."
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo guardar la ficha")


if not session.require_permission("candidate:read", "application:read"):
    st.stop()

design.page_header(
    "Candidatos",
    "Consulta y actualiza la base general desde un solo lugar.",
    "Trabajo diario",
)
notice = st.session_state.pop("candidate_notice", "")
if notice:
    st.success(notice)

try:
    candidates = session.client().list_candidates()
    applications = session.client().list_applications()
except ApiError as exc:
    design.api_error(exc, "No se pudo cargar la base general")
    st.stop()

can_write = session.has_permission("candidate:write")
reveal_pii = session.has_permission("candidate:pii:read")
formatted_applications = [
    {**application, "status_label": app_status(application.get("status", ""))}
    for application in applications
]
states = application_states(formatted_applications)

recruiters = [
    "Todos",
    *sorted({item.get("recruiter", "") for item in candidates if item.get("recruiter")}),
]
sources = [
    "Todas",
    *sorted({item.get("source", "") for item in candidates if item.get("source")}),
]
filters = st.container(horizontal=True, wrap=True)
query = filters.text_input(
    "Buscar candidatos",
    placeholder="Nombre, cliente, perfil, reclutador o vacante",
    key="candidate_query",
)
recruiter = filters.selectbox("Reclutador", recruiters, key="candidate_recruiter")
source = filters.selectbox("Fuente", sources, key="candidate_source")

visible = filter_candidates(
    candidates,
    states,
    query=query,
    recruiter=recruiter,
    source=source,
)
rows = candidate_rows(visible, states, reveal_pii=reveal_pii)

with st.container(horizontal=True, vertical_alignment="center"):
    st.caption(f"{len(visible)} de {len(candidates)} candidatos")
    if can_write and st.button("Nuevo candidato", icon=":material/person_add:"):
        st.session_state["candidate_create_open"] = True
        st.session_state.pop("selected_candidate_id", None)
    st.download_button(
        "Exportar vista",
        data=candidate_csv(rows),
        file_name="talentia-candidatos.csv",
        mime="text/csv",
        icon=":material/download:",
        disabled=not rows,
    )

if not candidates:
    design.empty_state(
        "La base está vacía",
        "Registra el primer candidato aquí o usa la importación histórica opcional.",
    )
elif not rows:
    design.empty_state("Sin resultados", "Prueba con otros términos o limpia los filtros.")
else:
    table = pd.DataFrame(rows)
    event = st.dataframe(
        table,
        column_config=_column_config(reveal_pii),
        hide_index=True,
        height=520 if st.session_state.get("ui_density") == "Compacta" else 440,
        key="candidate_registry",
        on_select="rerun",
        selection_mode="single-row",
    )
    st.caption("Selecciona una fila para consultar o editar su ficha completa.")
    if event.selection.rows:
        selected_position = event.selection.rows[0]
        if selected_position < len(visible):
            st.session_state["selected_candidate_id"] = visible[selected_position]["id"]

st.caption("SQLite es la fuente de verdad. CSV y Excel se usan solo para importar o exportar.")

if st.session_state.get("candidate_create_open"):
    if can_write:
        _candidate_form(None, reveal_pii=reveal_pii, mode="create")
    else:
        st.info("Tu rol no tiene permiso para registrar candidatos.")
    st.stop()

selected_id = st.session_state.get("selected_candidate_id")
selected = next((item for item in candidates if item["id"] == selected_id), None)
if selected:
    if can_write:
        _candidate_form(selected, reveal_pii=reveal_pii, mode="edit")
    else:
        with st.container(border=True):
            st.subheader(selected["full_name"])
            st.info("Tu rol puede consultar esta ficha, pero no editarla.")
