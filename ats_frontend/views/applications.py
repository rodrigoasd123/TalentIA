"""Postulaciones e ingreso de candidatos."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status, date_short, days_from_hours, score  # noqa: E402

MAX_CV_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _selected_job_label(job_id: str, jobs: list[dict]) -> str:
    job = next((item for item in jobs if item["id"] == job_id), None)
    if not job:
        return job_id
    return f"{job['code']} · {job['title']}"


def _validate_file(uploaded) -> list[str]:
    errors = []
    if uploaded is None:
        return ["Carga un CV en PDF o DOCX."]
    suffix = Path(uploaded.name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        errors.append("El CV debe ser PDF o DOCX.")
    if uploaded.size > MAX_CV_BYTES:
        errors.append("El CV supera el límite de 20 MB.")
    return errors


def _render_intake(jobs: list[dict]) -> None:  # noqa: C901 - Formulario guiado.
    if not session.has_permission("candidate:write"):
        st.info("Tu rol puede consultar postulaciones, pero no registrar candidatos.")
        return

    open_jobs = [job for job in jobs if job["status"] == "open"]
    if not open_jobs:
        design.empty_state(
            "No hay vacantes abiertas",
            "Crea o aprueba una vacante antes de registrar postulaciones.",
        )
        return

    design.progress_steps(
        [
            "Vacante",
            "Datos básicos",
            "Consentimiento",
            "CV",
            "Revisión",
        ],
        1,
    )

    with st.form("intake-form", clear_on_submit=False):
        st.subheader("Nueva postulación")
        job_id = st.selectbox(
            "Vacante",
            options=[job["id"] for job in open_jobs],
            format_func=lambda value: _selected_job_label(value, open_jobs),
            key="intake_job_id",
        )
        c1, c2 = st.columns(2)
        with c1:
            full_name = st.text_input("Nombre completo", key="intake_full_name")
            email = st.text_input("Correo", key="intake_email", placeholder="persona@example.test")
        with c2:
            phone = st.text_input("Teléfono opcional", key="intake_phone")
            source = st.selectbox(
                "Origen",
                ["manual", "linkedin_manual", "referido", "historico"],
                key="intake_source",
            )

        consent = st.checkbox(
            "Confirmo que existe consentimiento o base legal para este proceso",
            key="intake_consent",
        )
        uploaded = st.file_uploader(
            "CV",
            type=["pdf", "docx"],
            key="intake_file",
            help="TalentIA valida tipo y tamaño antes de enviar el archivo.",
        )
        st.caption("El contenido del documento no se renderiza como HTML.")

        st.markdown("**Resumen antes de crear**")
        st.write(f"Vacante: {_selected_job_label(job_id, open_jobs)}")
        st.write(f"Candidato: {full_name or '-'}")
        st.write(f"Archivo: {uploaded.name if uploaded else '-'}")
        confirmed = st.checkbox("He revisado los datos y deseo crear la postulación")
        submit = st.form_submit_button("Crear postulación", type="primary")

    if submit:
        errors = []
        if len(full_name.strip()) < 2:
            errors.append("Completa el nombre del candidato.")
        if "@" not in email:
            errors.append("Ingresa un correo válido.")
        if not consent:
            errors.append("Confirma consentimiento o base legal antes de continuar.")
        if not confirmed:
            errors.append("Revisa y confirma los datos antes de crear la postulación.")
        errors.extend(_validate_file(uploaded))

        if errors:
            for error in errors:
                st.error(error)
            return

        try:
            with st.spinner("Cargando CV y creando postulación..."):
                result = session.client().intake_application(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    job_id=job_id,
                    consent_granted=consent,
                    source=source,
                    filename=uploaded.name,
                    content=uploaded.getvalue(),
                    content_type=uploaded.type or "application/octet-stream",
                )
            st.success("Postulación creada correctamente.")
            if result.get("was_existing_candidate"):
                st.info("TalentIA reutilizó la ficha de una persona ya registrada.")
            for warning in result.get("warnings", []):
                st.warning(warning)
            st.code(result["application_id"], language="text")
        except ApiError as exc:
            design.api_error(exc, "No se pudo crear la postulación")


def _render_list(applications: list[dict]) -> None:
    st.subheader("Postulaciones registradas")
    if not applications:
        design.empty_state("Sin postulaciones", "Aún no hay candidatos en proceso.")
        return

    query = st.text_input("Buscar en postulaciones", key="applications_search")
    filtered = applications
    if query.strip():
        needle = query.strip().lower()
        filtered = [
            item
            for item in filtered
            if needle
            in " ".join(
                [item["candidate_name"], item["job_code"], item["status"], item["id"]]
            ).lower()
        ]

    st.dataframe(
        [
            {
                "Candidato": item["candidate_name"],
                "Vacante": item["job_code"],
                "Estado": app_status(item["status"]),
                "Puntaje": score(item.get("score")),
                "Registro": date_short(item.get("applied_at")),
                "Tiempo en etapa": days_from_hours(item.get("hours_in_stage")),
            }
            for item in filtered
        ],
        width="stretch",
        hide_index=True,
    )


def render() -> None:
    if not session.has_any("application:read", "candidate:write"):
        design.page_header("Acceso denegado", "Esta sección no está disponible para tu rol.")
        return

    design.page_header(
        "Postulaciones",
        "Registra candidatos sin perder datos cuando ocurra un error recuperable.",
        "Trabajo diario",
    )

    try:
        jobs = session.client().list_jobs()
        applications = (
            session.client().list_applications()
            if session.has_permission("application:read")
            else []
        )
    except ApiError as exc:
        design.api_error(exc, "No se pudo cargar la página")
        return

    new_tab, list_tab = st.tabs(["Nueva postulación", "Listado"])
    with new_tab:
        _render_intake(jobs)
    with list_tab:
        _render_list(applications)


render()
