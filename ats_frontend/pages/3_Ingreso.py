"""Alta manual de vacantes y candidaturas ficticias."""
from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Ingreso · VERA ATS", page_icon="📝", layout="wide")
client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))
st.title("📝 Ingreso al proceso")
st.warning("Piloto local: utiliza únicamente datos ficticios. No cargues CV reales hasta contar con aprobación legal, de privacidad y seguridad.", icon="🛡️")
tab_candidate, tab_job = st.tabs(["Cargar candidatura", "Crear vacante"])

with tab_job:
    with st.form("create-job"):
        code = st.text_input("Código", placeholder="LAB-005")
        title = st.text_input("Título del puesto")
        description = st.text_area("Descripción")
        department = st.text_input("Área")
        location = st.text_input("Ubicación")
        skills = st.text_input("Habilidades obligatorias", help="Separadas por comas")
        minimum_score = st.slider("Puntaje mínimo", 0, 100, 70)
        criteria_approved = st.checkbox("Confirmo que una persona revisó y aprobó estos criterios")
        create = st.form_submit_button("Crear vacante", type="primary")
    if create:
        try:
            created = client.create_job({"code": code, "title": title, "description": description, "department": department, "location": location, "mandatory_skills": [s.strip() for s in skills.split(",") if s.strip()], "minimum_score": minimum_score, "criteria_approved": criteria_approved})
            st.success(f"Vacante {created['code']} creada en estado {created['status']}.")
        except ApiError as exc:
            st.error(str(exc))

with tab_candidate:
    try:
        jobs = [job for job in client.list_jobs() if job["status"] == "open"]
    except ApiError as exc:
        st.error(str(exc))
        jobs = []
    if not jobs:
        st.info("Primero crea y aprueba una vacante o ejecuta la siembra del laboratorio.")
    else:
        with st.form("intake"):
            job_id = st.selectbox("Vacante", options=[job["id"] for job in jobs], format_func=lambda value: next(f"{j['code']} — {j['title']}" for j in jobs if j["id"] == value))
            full_name = st.text_input("Nombre ficticio")
            email = st.text_input("Correo ficticio")
            phone = st.text_input("Teléfono ficticio (opcional)")
            source = st.selectbox("Origen", ["manual", "linkedin_manual", "referido"])
            uploaded = st.file_uploader("CV ficticio", type=["pdf", "docx"])
            consent = st.checkbox("Confirmo el consentimiento para este proceso de selección")
            submit = st.form_submit_button("Registrar candidatura", type="primary")
        if submit:
            if uploaded is None:
                st.error("Selecciona un PDF o DOCX.")
            else:
                try:
                    result = client.intake_application(full_name=full_name, email=email, phone=phone, job_id=job_id, consent_granted=consent, source=source, filename=uploaded.name, content=uploaded.getvalue(), content_type=uploaded.type or "application/octet-stream")
                    st.success("Candidatura registrada correctamente.")
                    st.code(result["application_id"], language="text")
                    for warning in result.get("warnings", []):
                        st.warning(warning)
                except ApiError as exc:
                    st.error(str(exc))