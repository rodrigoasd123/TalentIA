"""Candidate 360."""

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
    days_from_hours,
    percent,
    recommendation,
    review_reason,
    score,
)


def _application_label(application_id: str, applications: list[dict]) -> str:
    app = next((item for item in applications if item["id"] == application_id), None)
    if not app:
        return application_id
    return f"{app['candidate_name']} · {app['job_code']} · {app_status(app['status'])}"


def _render_evaluation(evaluation: dict | None) -> None:
    if not evaluation:
        design.empty_state(
            "Sin evaluación", "Esta postulación todavía no tiene evaluación vigente."
        )
        return

    design.metric_grid(
        [
            ("Puntaje", score(evaluation.get("score")), "Orientativo"),
            ("Resultado", recommendation(evaluation.get("recommendation", "")), ""),
            ("Evidencia", percent(evaluation.get("evidence_rate")), "Verificada"),
            ("Revisión humana", "Sí" if evaluation.get("requires_human_review") else "No", ""),
        ]
    )
    st.write(evaluation.get("summary") or "Sin resumen.")
    if evaluation.get("review_reasons"):
        st.warning(
            "Motivos de revisión: "
            + ", ".join(review_reason(reason) for reason in evaluation["review_reasons"])
        )

    dimensions = evaluation.get("dimensions", []) or []
    if dimensions:
        for dimension in dimensions:
            with st.container(border=True):
                st.write(f"**{dimension.get('dimension')}** · {score(dimension.get('score'))}/100")
                st.caption(f"Peso {score(dimension.get('weight'))}%")
                if dimension.get("reasoning"):
                    st.write(dimension["reasoning"])
                for evidence in dimension.get("evidence", []) or []:
                    st.write(f"- {evidence.get('quote', '')}")
                    st.caption(
                        "Evidencia verificada"
                        if evidence.get("verified")
                        else "Evidencia insuficiente o no verificada"
                    )
        st.caption("El endpoint actual no devuelve número de página por cita.")


def _render_resume(data: dict, candidate: dict) -> None:
    resume = data.get("resume")
    if not resume:
        design.empty_state("Sin CV", "Esta postulación no tiene CV asociado.")
        return

    design.badge_row(
        [
            (f"Archivo: {resume.get('filename', '-')}", "info"),
            (f"Versión {resume.get('version', '-')}", "muted"),
            (f"{resume.get('chars', 0)} caracteres", "muted"),
        ]
    )
    if resume.get("is_suspicious"):
        st.error("El documento fue marcado como sospechoso por posible manipulación.")

    extraction = resume.get("extraction") or {}
    if not extraction:
        st.info("No hay datos extraídos disponibles.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Experiencia", f"{extraction.get('total_years_experience', 0):.0f} años")
        c2.metric("Senioridad", extraction.get("seniority", "-"))
        c3.metric("Tecnologías", len(extraction.get("technologies", []) or []))

        skills = sorted(
            set((extraction.get("skills", []) or []) + (extraction.get("technologies", []) or []))
        )
        if skills:
            st.subheader("Habilidades")
            st.write(", ".join(skills))

        if extraction.get("experiences"):
            st.subheader("Experiencia")
            for item in extraction["experiences"]:
                st.write(
                    f"- {item.get('role', '-')} en {item.get('company', '-')} "
                    f"({item.get('start_date', '-')} a {item.get('end_date') or 'actualidad'})"
                )

        if extraction.get("education"):
            st.subheader("Educación")
            for item in extraction["education"]:
                st.write(f"- {item.get('degree', '-')} · {item.get('level', '-')}")

    st.subheader("Contacto protegido")
    st.caption("Estos datos no se envían al proveedor de IA.")
    st.write(f"Correo: {candidate.get('email') or '-'}")
    st.write(f"Teléfono: {candidate.get('phone') or '-'}")
    st.write(f"Ubicación: {candidate.get('location') or '-'}")


def _render_communications(application_id: str, data: dict) -> None:
    st.subheader("Comunicaciones")
    emails = data.get("emails", []) or []
    if emails:
        st.dataframe(
            [
                {
                    "Asunto": item["subject"],
                    "Destinatario": item["recipient"],
                    "Estado": item["status"],
                    "Enviado": date_short(item.get("sent_at")),
                }
                for item in emails
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No hay comunicaciones registradas para esta postulación.")

    if session.has_permission("email:prepare"):
        with st.expander("Preparar borrador"):
            try:
                templates = session.client().email_templates()
                provider = session.client().email_provider()
            except ApiError as exc:
                design.api_error(exc, "No se pudieron cargar plantillas")
                return
            if provider.get("is_simulated"):
                st.info("El correo está en modo simulado o no configurado.")
            if not templates:
                st.caption("No hay plantillas aprobadas.")
                return
            template = st.selectbox(
                "Plantilla",
                options=[item["code"] for item in templates],
                format_func=lambda code: next(
                    item["code"]
                    + (" · requiere aprobación" if item["requires_human_approval"] else "")
                    for item in templates
                    if item["code"] == code
                ),
            )
            use_ai = st.toggle("Completar variables con IA", value=False)
            if st.button("Preparar borrador"):
                try:
                    draft = session.client().prepare_email(
                        application_id=application_id,
                        template_code=template,
                        use_ai=use_ai,
                    )
                    st.success("Borrador preparado.")
                    st.text_input("Asunto", draft["subject"], disabled=True)
                    st.text_area("Cuerpo", draft["body"], disabled=True, height=220)
                    st.caption(f"Destinatario: {draft['recipient']} · estado {draft['status']}")
                except ApiError as exc:
                    design.api_error(exc, "No se pudo preparar el borrador")


def _render_trail(application_id: str, data: dict) -> None:
    st.subheader("Timeline")
    timeline = data.get("timeline", []) or []
    if not timeline:
        st.caption("No hay eventos registrados para este expediente.")
    for step in timeline:
        st.write(f"**{date_short(step.get('timestamp'))}** · {step.get('description', '')}")
        if step.get("detail"):
            st.caption(step["detail"])

    if session.has_permission("audit:read"):
        st.divider()
        st.subheader("Traza exportable")
        try:
            markdown = session.client().decision_trail(application_id, fmt="markdown")
            csv = session.client().decision_trail(application_id, fmt="csv")
        except ApiError as exc:
            design.api_error(exc, "No se pudo cargar la traza")
            return
        c1, c2 = st.columns(2)
        c1.download_button(
            "Descargar Markdown",
            data=markdown,
            file_name=f"traza-{application_id[:8]}.md",
            mime="text/markdown",
            width="stretch",
        )
        c2.download_button(
            "Descargar CSV",
            data=csv,
            file_name=f"traza-{application_id[:8]}.csv",
            mime="text/csv",
            width="stretch",
        )


def render() -> None:
    if not session.require_permission("candidate:pii:read"):
        return

    design.page_header(
        "Candidate 360",
        "Ficha única del candidato y detalle de su participación en una vacante específica.",
        "Expediente",
    )
    design.badge_row(
        [("Candidate = persona", "info"), ("Application = postulación a una vacante", "muted")]
    )

    try:
        applications = session.client().list_applications()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar postulaciones")
        return
    if not applications:
        design.empty_state(
            "Sin postulaciones", "Registra una postulación para abrir un expediente."
        )
        return

    preselected = st.session_state.get("selected_application")
    options = [item["id"] for item in applications]
    index = options.index(preselected) if preselected in options else 0
    selected = st.selectbox(
        "Postulación",
        options=options,
        index=index,
        format_func=lambda value: _application_label(value, applications),
    )
    st.session_state["selected_application"] = selected

    try:
        data = session.client().candidate_360(selected)
    except ApiError as exc:
        design.api_error(exc, "No se pudo abrir Candidate 360")
        return

    candidate = data.get("candidate") or {}
    application = data.get("application") or {}
    job = data.get("job") or {}

    st.subheader(candidate.get("full_name", "-"))
    st.caption(
        f"{job.get('code', '-')} · {job.get('title', '-')} · "
        f"Registrada {date_short(application.get('applied_at'))}"
    )
    design.metric_grid(
        [
            ("Estado", app_status(application.get("status", "")), ""),
            ("Puntaje", score(application.get("score")), "Orientativo"),
            ("Tiempo en etapa", days_from_hours(application.get("hours_in_stage")), ""),
            ("Consentimiento", "Vigente" if candidate.get("consent_valid") else "No vigente", ""),
        ]
    )

    if not candidate.get("consent_valid"):
        st.error("El consentimiento o base legal no está vigente. No proceses este expediente.")
    if data.get("open_review"):
        review = data["open_review"]
        st.warning(
            "Hay una revisión humana abierta: "
            + ", ".join(review_reason(reason) for reason in review.get("reasons", []))
        )

    summary_tab, resume_tab, evaluation_tab, communications_tab, trail_tab = st.tabs(
        ["Resumen", "CV", "Evaluación", "Comunicaciones", "Trazabilidad"]
    )
    with summary_tab:
        st.write("**Persona única**")
        st.write(f"ID interno: {candidate.get('id', '-')}")
        st.write(f"Etiquetas: {', '.join(candidate.get('tags', []) or []) or '-'}")
        related = [item for item in applications if item["candidate_id"] == candidate.get("id")]
        st.write("**Postulaciones de esta persona**")
        st.dataframe(
            [
                {
                    "Vacante": item["job_code"],
                    "Estado": app_status(item["status"]),
                    "Puntaje": score(item.get("score")),
                    "Registro": date_short(item.get("applied_at")),
                }
                for item in related
            ],
            width="stretch",
            hide_index=True,
        )
    with resume_tab:
        _render_resume(data, candidate)
    with evaluation_tab:
        _render_evaluation(data.get("current_evaluation"))
    with communications_tab:
        _render_communications(selected, data)
    with trail_tab:
        _render_trail(selected, data)


render()
