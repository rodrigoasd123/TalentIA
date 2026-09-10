"""Importación histórica gobernada desde CSV/XLSX."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import DEFAULT_BASE_URL, ApiError, VeraApiClient

st.set_page_config(page_title="Importación histórica · TalentIA", page_icon="📥", layout="wide")


def client() -> VeraApiClient:
    return VeraApiClient(
        st.session_state.get("api_base_url", DEFAULT_BASE_URL),
        access_token=st.session_state.get("access_token", ""),
    )


st.title("📥 Importación histórica")
st.warning(
    "Piloto local: utiliza únicamente archivos con datos ficticios. La validación "
    "trabaja en staging y no crea candidatos hasta la confirmación humana.",
    icon="🛡️",
)

with st.expander("Sesión de HR Manager para confirmar", expanded=False):
    with st.form("import-login"):
        email = st.text_input("Correo", value="manager@vera-lab.test")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Iniciar sesión")
    if submitted:
        try:
            pair = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL)).login(
                email, password
            )
            st.session_state["access_token"] = pair["access_token"]
            st.success("Sesión autorizada para las operaciones permitidas por el rol.")
        except ApiError as exc:
            st.error(str(exc))

with st.form("upload-import"):
    source = st.text_input("Fuente o proveedor", value="historical")
    uploaded = st.file_uploader("Archivo CSV o XLSX", type=["csv", "xlsx"])
    upload = st.form_submit_button("Cargar en staging", type="primary")

if upload and uploaded:
    try:
        result = client().upload_historical_import(
            filename=uploaded.name,
            content=uploaded.getvalue(),
            source=source,
            content_type=uploaded.type or "application/octet-stream",
        )
        st.session_state["import_batch_id"] = result["id"]
        st.success("Lote existente reutilizado." if result["reused"] else "Lote cargado.")
    except ApiError as exc:
        st.error(str(exc))

batch_id = st.session_state.get("import_batch_id", "")
if batch_id:
    try:
        batch = client().get_import(batch_id)
    except ApiError as exc:
        st.error(str(exc))
        st.stop()

    st.subheader(f"Lote {batch_id[:8]} · {batch['status']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Filas", batch["row_count"])
    col2.metric("Fuente", batch["source"])
    col3.metric("Versión", batch["version"])

    sheet_names = batch.get("summary", {}).get("sheet_names", [])
    if len(sheet_names) > 1:
        current_sheet = batch.get("sheet_name") or sheet_names[0]
        selected_sheet = st.selectbox(
            "Hoja XLSX",
            options=sheet_names,
            index=sheet_names.index(current_sheet),
        )
        if selected_sheet != current_sheet and st.button("Usar esta hoja"):
            try:
                client().select_import_sheet(
                    batch_id,
                    sheet_name=selected_sheet,
                    expected_version=batch["version"],
                )
                st.success(f"Hoja seleccionada: {selected_sheet}")
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))

    headers = batch.get("summary", {}).get("headers", [])
    suggestions = batch.get("suggested_mapping", {})
    canonical = [
        "full_name", "email", "phone", "national_id", "location", "source",
        "job_code", "historical_status", "applied_at", "legal_basis_status",
        "linkedin_url",
    ]
    mapping: dict[str, str] = {}
    with st.form("mapping"):
        st.markdown("#### Mapeo de columnas")
        for field in canonical:
            options = ["", *headers]
            suggested = suggestions.get(field, "")
            index = options.index(suggested) if suggested in options else 0
            selected = st.selectbox(field, options=options, index=index, key=f"map-{field}")
            if selected:
                mapping[field] = selected
        template_name = st.text_input("Guardar como plantilla (opcional)")
        validate = st.form_submit_button("Validar lote")
    if validate:
        try:
            batch = client().validate_import(
                batch_id, mapping=mapping, expected_version=batch["version"],
                template_name=template_name,
            )
            st.success(f"Validación completada: {batch['status']}")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))

    if batch["status"] in {"ready_for_review", "partially_valid", "rejected", "imported"}:
        rows = client().import_rows(batch_id, limit=200)
        st.markdown("#### Previsualización")
        st.dataframe(rows["rows"], use_container_width=True, hide_index=True)
        st.json(batch.get("summary", {}))

    if batch["status"] in {"ready_for_review", "partially_valid"}:
        st.info(
            "Solo se confirmarán filas NEW o EXACT_DUPLICATE. Casos ambiguos, "
            "inválidos o ya activos permanecerán en staging."
        )
        if st.button("Confirmar importación", type="primary"):
            try:
                result = client().confirm_import(
                    batch_id,
                    idempotency_key=f"ui-{batch_id}-{uuid4().hex[:12]}",
                    expected_version=batch["version"],
                )
                st.success(f"Importación confirmada: {result['summary']}")
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))
