"""Vacantes y criterios."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import job_status, score, tone_for_status  # noqa: E402


def _job_label(job: dict) -> str:
    return f"{job.get('code', '-')} · {job.get('title', '-')}"


def _payload_from_form(prefix: str) -> dict:
    return {
        "code": st.session_state.get(f"{prefix}_code", "").strip(),
        "title": st.session_state.get(f"{prefix}_title", "").strip(),
        "description": st.session_state.get(f"{prefix}_description", "").strip(),
        "department": st.session_state.get(f"{prefix}_department", "").strip(),
        "location": st.session_state.get(f"{prefix}_location", "").strip(),
        "mandatory_skills": [
            skill.strip()
            for skill in st.session_state.get(f"{prefix}_skills", "").split(",")
            if skill.strip()
        ],
        "minimum_score": float(st.session_state.get(f"{prefix}_minimum_score", 70)),
        "review_threshold": float(st.session_state.get(f"{prefix}_review_threshold", 5)),
        "min_years_experience": float(st.session_state.get(f"{prefix}_min_years", 0)),
        "criteria_approved": bool(st.session_state.get(f"{prefix}_approved", False)),
    }


def render() -> None:  # noqa: C901 - Gestión de vacantes concentrada para RR. HH.
    if not session.require_permission("job:read"):
        return

    design.page_header(
        "Vacantes",
        "Crea, revisa y aprueba criterios antes de evaluar postulaciones.",
        "Trabajo diario",
    )
    st.caption(
        "Modificar requisitos, puntajes o experiencia mínima devuelve la vacante a borrador."
    )

    client = session.client()
    try:
        jobs = client.list_jobs()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar las vacantes")
        return

    search, status_filter = st.columns([2, 1])
    with search:
        query = st.text_input("Buscar", placeholder="Código, puesto, área o ubicación")
    with status_filter:
        selected_status = st.selectbox(
            "Estado",
            options=["Todos", *sorted({job["status"] for job in jobs})],
            format_func=lambda value: value if value == "Todos" else job_status(value),
        )

    filtered = jobs
    if query.strip():
        needle = query.strip().lower()
        filtered = [
            job
            for job in filtered
            if needle
            in " ".join(
                [
                    job.get("code", ""),
                    job.get("title", ""),
                    job.get("department", ""),
                    job.get("location", ""),
                ]
            ).lower()
        ]
    if selected_status != "Todos":
        filtered = [job for job in filtered if job["status"] == selected_status]

    design.metric_grid(
        [
            ("Total", str(len(jobs)), "Vacantes registradas"),
            ("Abiertas", str(sum(job["status"] == "open" for job in jobs)), "Listas para postular"),
            (
                "Borrador",
                str(sum(job["status"] == "draft" for job in jobs)),
                "Requieren aprobación",
            ),
        ]
    )

    if not jobs:
        design.empty_state("Sin vacantes", "Crea una vacante para comenzar el proceso.")
    elif not filtered:
        design.empty_state("Sin resultados", "No hay vacantes que coincidan con los filtros.")
    else:
        st.dataframe(
            [
                {
                    "Código": job["code"],
                    "Puesto": job["title"],
                    "Área": job["department"],
                    "Ubicación": job["location"],
                    "Estado": job_status(job["status"]),
                    "Puntaje mínimo": score(job["minimum_score"]),
                    "Experiencia": f"{job['min_years_experience']:.0f} años",
                }
                for job in filtered
            ],
            width="stretch",
            hide_index=True,
        )

    selected_job = None
    if jobs:
        selected_code = st.selectbox(
            "Vacante para revisar",
            options=[job["code"] for job in jobs],
            format_func=lambda code: _job_label(next(job for job in jobs if job["code"] == code)),
        )
        selected_job = next(job for job in jobs if job["code"] == selected_code)

    if selected_job:
        st.divider()
        design.section_label("Detalle")
        design.badge_row(
            [
                (job_status(selected_job["status"]), tone_for_status(selected_job["status"])),
                (
                    "Versión de criterios: "
                    f"{selected_job.get('requirements_version', 'no disponible')}",
                    "muted",
                ),
            ]
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Puntaje mínimo", score(selected_job["minimum_score"]))
        m2.metric("Zona gris", f"± {score(selected_job['review_threshold'])}")
        m3.metric("Experiencia", f"{selected_job['min_years_experience']:.0f} años")
        m4.metric("Filtros", selected_job["hard_filter_count"])

        left, right = st.columns([1, 1], gap="large")
        with left:
            st.subheader("Requisitos obligatorios")
            if selected_job["mandatory_skills"]:
                for skill in selected_job["mandatory_skills"]:
                    st.write(f"- {skill}")
            else:
                st.caption("No hay habilidades obligatorias definidas.")

        with right:
            st.subheader("Pesos")
            weights = selected_job.get("weights", {})
            if weights:
                st.bar_chart(weights, horizontal=True)
            else:
                st.caption("El endpoint no devolvió pesos configurados.")

        with st.expander("Bases de convocatoria"):
            try:
                st.markdown(client.job_brief(selected_job["code"]))
            except ApiError as exc:
                design.api_error(exc, "No se pudieron cargar las bases")

        with st.expander("Búsqueda manual para LinkedIn"):
            st.caption("TalentIA solo prepara la consulta. No abre LinkedIn ni extrae datos.")
            if st.button("Generar consulta Boolean", width="stretch"):
                try:
                    suggestion = client.sourcing_query(selected_job["id"])
                    st.code(suggestion["boolean_query"], language="text")
                    st.info(suggestion["notice"])
                except ApiError as exc:
                    design.api_error(exc, "No se pudo generar la consulta")

    if session.has_permission("job:write"):
        st.divider()
        create_tab, edit_tab = st.tabs(["Crear vacante", "Editar criterios"])
        with create_tab:
            with st.form("create-job"):
                c1, c2 = st.columns(2)
                with c1:
                    st.text_input("Código", key="new_code", placeholder="LAB-005")
                    st.text_input("Puesto", key="new_title")
                    st.text_input("Área", key="new_department")
                    st.text_input("Ubicación", key="new_location")
                with c2:
                    st.text_area("Descripción breve", key="new_description", height=124)
                    st.text_input(
                        "Habilidades obligatorias", key="new_skills", help="Separadas por coma"
                    )
                s1, s2, s3 = st.columns(3)
                s1.slider("Puntaje mínimo", 0, 100, 70, key="new_minimum_score")
                s2.slider("Margen de revisión", 0, 50, 5, key="new_review_threshold")
                s3.number_input(
                    "Años de experiencia",
                    min_value=0.0,
                    max_value=80.0,
                    value=0.0,
                    key="new_min_years",
                )
                st.checkbox(
                    "Confirmo que una persona revisó y aprobó estos criterios",
                    key="new_approved",
                )
                create = st.form_submit_button("Crear vacante", type="primary")
            if create:
                payload = _payload_from_form("new")
                if not payload["code"] or not payload["title"]:
                    st.error("Completa al menos código y puesto.")
                else:
                    try:
                        created = client.create_job(payload)
                        state = job_status(created["status"])
                        st.success(
                            f"Vacante {created['code']} creada en estado {state}."
                        )
                        st.rerun()
                    except ApiError as exc:
                        design.api_error(exc, "No se pudo crear la vacante")

        with edit_tab:
            if not selected_job:
                st.info("Selecciona una vacante para editarla.")
            else:
                with st.form("edit-job"):
                    st.text_input("Puesto", value=selected_job["title"], key="edit_title")
                    st.text_area(
                        "Descripción breve",
                        value=selected_job.get("description", ""),
                        key="edit_description",
                    )
                    e1, e2 = st.columns(2)
                    e1.text_input("Área", value=selected_job["department"], key="edit_department")
                    e2.text_input("Ubicación", value=selected_job["location"], key="edit_location")
                    st.text_input(
                        "Habilidades obligatorias",
                        value=", ".join(selected_job["mandatory_skills"]),
                        key="edit_skills",
                    )
                    s1, s2, s3 = st.columns(3)
                    s1.slider(
                        "Puntaje mínimo",
                        0,
                        100,
                        int(selected_job["minimum_score"]),
                        key="edit_minimum_score",
                    )
                    s2.slider(
                        "Margen de revisión",
                        0,
                        50,
                        int(selected_job["review_threshold"]),
                        key="edit_review_threshold",
                    )
                    s3.number_input(
                        "Años de experiencia",
                        min_value=0.0,
                        max_value=80.0,
                        value=float(selected_job["min_years_experience"]),
                        key="edit_min_years",
                    )
                    st.warning("Si cambias criterios, la aprobación anterior deja de ser válida.")
                    st.checkbox("Confirmo la actualización de criterios", key="edit_confirm")
                    update = st.form_submit_button("Guardar cambios", type="primary")
                if update:
                    if not st.session_state.get("edit_confirm"):
                        st.error("Confirma la actualización antes de guardar.")
                    else:
                        payload = _payload_from_form("edit")
                        payload.pop("code", None)
                        payload.pop("criteria_approved", None)
                        if "description" not in selected_job:
                            payload.pop("description", None)
                        try:
                            updated = client.update_job(selected_job["id"], payload)
                            st.success(
                                f"Vacante actualizada. Estado: {job_status(updated['status'])}."
                            )
                            st.rerun()
                        except ApiError as exc:
                            design.api_error(exc, "No se pudo actualizar la vacante")

                if selected_job["status"] != "open":
                    st.info("Para abrir la vacante, aprueba los criterios de forma explícita.")
                    approved = st.checkbox(
                        "Confirmo que apruebo estos criterios", key="approve_confirm"
                    )
                    if st.button("Aprobar criterios", type="primary", disabled=not approved):
                        try:
                            updated = client.update_job(
                                selected_job["id"], {"criteria_approved": True}
                            )
                            state = job_status(updated["status"])
                            st.success(
                                f"Criterios aprobados. La vacante queda {state}."
                            )
                            st.caption(
                                "El endpoint actual no devuelve aprobador y fecha en el detalle; "
                                "la acción queda registrada en auditoría."
                            )
                            st.rerun()
                        except ApiError as exc:
                            design.api_error(exc, "No se pudieron aprobar los criterios")


render()
