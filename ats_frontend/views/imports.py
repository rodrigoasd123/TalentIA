"""Importación histórica CSV/XLSX."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia.formatters import (  # noqa: E402
    import_status,
    row_classification,
    short_id,
    tone_for_status,
)

from talentia import design, session  # noqa: E402

MAX_IMPORT_BYTES = 20 * 1024 * 1024

FIELDS = {
    "full_name": "Nombre completo",
    "email": "Correo",
    "phone": "Teléfono",
    "national_id": "Documento",
    "location": "Ubicación",
    "source": "Origen",
    "job_code": "Código de vacante",
    "historical_status": "Estado histórico",
    "applied_at": "Fecha de postulación",
    "legal_basis_status": "Base legal",
    "linkedin_url": "LinkedIn",
}


def _current_step(batch: dict | None) -> int:
    if not batch:
        return 1
    status = batch.get("status")
    if status == "uploaded":
        return 3
    if status in {"ready_for_review", "partially_valid", "rejected"}:
        return 4
    if status in {"imported", "cancelled"}:
        return 5
    return 2


def _flatten_rows(rows: list[dict]) -> list[dict]:
    flattened = []
    for row in rows:
        data = row.get("data", {}) or {}
        flattened.append(
            {
                "Fila": row.get("row_number"),
                "Estado": row_classification(row.get("classification", "")),
                "Nombre": data.get("full_name", ""),
                "Correo": data.get("email", ""),
                "Teléfono": data.get("phone", ""),
                "Vacante": data.get("job_code", ""),
                "Señales": ", ".join(row.get("signals", []) or []),
                "Errores": "; ".join(
                    error.get("message", "") for error in row.get("errors", []) or []
                ),
            }
        )
    return flattened


def _upload_section() -> None:
    if not session.has_permission("import:upload"):
        st.info("Tu rol puede consultar importaciones, pero no cargar nuevos archivos.")
        return

    with st.form("upload-import", clear_on_submit=False):
        source = st.text_input(
            "Fuente", value="historical", help="Ejemplo: bolsa externa o archivo legado."
        )
        uploaded = st.file_uploader("Archivo CSV o XLSX", type=["csv", "xlsx"])
        st.caption("Límite visual: 20 MB. El backend vuelve a validar tamaño y filas.")
        submit = st.form_submit_button("Cargar en staging", type="primary")

    if submit:
        if uploaded is None:
            st.error("Selecciona un archivo CSV o XLSX.")
            return
        if uploaded.size > MAX_IMPORT_BYTES:
            st.error("El archivo supera el límite de 20 MB.")
            return
        try:
            with st.spinner("Cargando archivo en staging..."):
                result = session.client().upload_historical_import(
                    filename=uploaded.name,
                    content=uploaded.getvalue(),
                    source=source,
                    content_type=uploaded.type or "application/octet-stream",
                )
            st.session_state["import_batch_id"] = result["id"]
            st.success("Lote reutilizado." if result.get("reused") else "Lote cargado.")
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo cargar el archivo")


def _mapping_section(batch: dict) -> None:
    if not session.has_permission("import:upload"):
        return

    headers = batch.get("summary", {}).get("headers", []) or []
    suggestions = batch.get("suggested_mapping", {}) or {}
    if not headers:
        st.info("El lote aún no expone encabezados para mapear.")
        return

    templates = []
    try:
        templates = session.client().import_templates(batch.get("source", ""))
    except ApiError:
        templates = []

    chosen_template = st.selectbox(
        "Plantilla de mapeo",
        options=["Sugerencia automática"] + [template["id"] for template in templates],
        format_func=lambda value: (
            "Sugerencia automática"
            if value == "Sugerencia automática"
            else next(template["name"] for template in templates if template["id"] == value)
        ),
    )
    template_mapping = {}
    if chosen_template != "Sugerencia automática":
        template_mapping = next(
            template["mapping"] for template in templates if template["id"] == chosen_template
        )

    mapping = {}
    with st.form("mapping-form"):
        st.subheader("Mapeo de columnas")
        st.caption("Nombre completo y código de vacante son obligatorios.")
        for key, label in FIELDS.items():
            options = ["", *headers]
            suggested = template_mapping.get(key) or suggestions.get(key, "")
            index = options.index(suggested) if suggested in options else 0
            selected = st.selectbox(label, options=options, index=index, key=f"map_{key}")
            if selected:
                mapping[key] = selected
        template_name = st.text_input("Guardar este mapeo como plantilla", placeholder="Opcional")
        validate = st.form_submit_button("Validar filas", type="primary")

    if validate:
        try:
            with st.spinner("Validando filas en staging..."):
                session.client().validate_import(
                    batch["id"],
                    mapping=mapping,
                    expected_version=batch["version"],
                    template_name=template_name,
                )
            st.success("Validación completada. Revisa el resumen antes de confirmar.")
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo validar el lote")


def _sheet_section(batch: dict) -> None:
    sheet_names = batch.get("summary", {}).get("sheet_names", []) or []
    if len(sheet_names) <= 1 or not session.has_permission("import:upload"):
        return
    st.subheader("Hoja del archivo")
    current = batch.get("sheet_name") or sheet_names[0]
    selected = st.selectbox(
        "Selecciona hoja",
        options=sheet_names,
        index=sheet_names.index(current) if current in sheet_names else 0,
    )
    if selected != current and st.button("Usar esta hoja"):
        try:
            session.client().select_import_sheet(
                batch["id"], sheet_name=selected, expected_version=batch["version"]
            )
            st.success("Hoja seleccionada.")
            st.rerun()
        except ApiError as exc:
            design.api_error(exc, "No se pudo seleccionar la hoja")


def _review_section(batch: dict) -> None:  # noqa: C901 - Revisión guiada de lote.
    status = batch.get("status", "")
    if status not in {"ready_for_review", "partially_valid", "rejected", "imported"}:
        return

    st.subheader("Resultado de validación")
    summary = batch.get("summary", {}) or {}
    design.metric_grid(
        [
            ("Válidas", str(summary.get("new", 0)), "Nuevos candidatos"),
            ("Duplicados exactos", str(summary.get("exact_duplicate", 0)), "No crean duplicados"),
            ("Posibles duplicados", str(summary.get("possible_duplicate", 0)), "Revisión manual"),
            ("Con error", str(summary.get("invalid", 0)), "No se importan"),
            (
                "Requieren revisión",
                str(summary.get("manual_review_required", 0)),
                "Identidad insuficiente",
            ),
        ]
    )

    try:
        rows_payload = session.client().import_rows(batch["id"], limit=300)
        rows = rows_payload.get("rows", [])
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar las filas")
        rows = []

    if rows:
        st.dataframe(_flatten_rows(rows), width="stretch", hide_index=True)
    else:
        design.empty_state("Sin filas para mostrar", "El lote no devolvió filas de staging.")

    if status in {"partially_valid", "rejected"}:
        try:
            csv_report = session.client().import_error_report(batch["id"])
            st.download_button(
                "Descargar reporte de errores",
                data=csv_report,
                file_name=f"errores-{short_id(batch['id'])}.csv",
                mime="text/csv",
            )
        except ApiError:
            st.info("El reporte de errores no está disponible para este lote.")

    st.info(
        "La repetición idempotente de una confirmación no crea duplicados. "
        "La selección individual de filas requiere un endpoint adicional; hoy se "
        "confirman todas las elegibles."
    )

    can_confirm = session.role() == "hiring_manager" and session.has_permission("import:confirm")
    if status in {"ready_for_review", "partially_valid"}:
        if not can_confirm:
            st.warning("Solo un Responsable de RR. HH. autorizado puede confirmar la importación.")
        else:
            confirm = st.checkbox(
                "Confirmo que revisé el resumen y deseo importar las filas elegibles",
                key="confirm_import_checkbox",
            )
            if st.button("Confirmar importación", type="primary", disabled=not confirm):
                try:
                    result = session.client().confirm_import(
                        batch["id"],
                        idempotency_key=f"ui-{batch['id']}-{uuid4().hex[:12]}",
                        expected_version=batch["version"],
                    )
                    st.success(f"Importación confirmada: {import_status(result['status'])}.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo confirmar la importación")

    if session.has_permission("import:confirm") and status != "imported":
        with st.expander("Cancelar lote"):
            reason = st.text_area("Motivo de cancelación", key="cancel_import_reason")
            if st.button("Cancelar lote", disabled=len(reason.strip()) < 3):
                try:
                    session.client().cancel_import(batch["id"], reason=reason)
                    st.success("Lote cancelado.")
                    st.rerun()
                except ApiError as exc:
                    design.api_error(exc, "No se pudo cancelar el lote")


def render() -> None:
    if not session.require_permission("import:read", "import:upload"):
        return

    design.page_header(
        "Importación histórica",
        "Carga archivos CSV/XLSX en staging, valida filas y confirma solo con revisión humana.",
        "Seguimiento",
    )
    st.warning(
        "Los candidatos históricos ingresan con procesamiento restringido hasta "
        "revisión autorizada."
    )

    batch = None
    batch_id = st.session_state.get("import_batch_id", "")
    if batch_id:
        try:
            batch = session.client().get_import(batch_id)
        except ApiError as exc:
            design.api_error(exc, "No se pudo recuperar el lote")
            st.session_state.pop("import_batch_id", None)

    design.progress_steps(
        ["Archivo", "Hoja", "Mapeo", "Validación", "Confirmación"],
        _current_step(batch),
    )

    _upload_section()

    if not batch:
        return

    st.divider()
    design.badge_row(
        [
            (f"Lote {short_id(batch['id'])}", "info"),
            (import_status(batch["status"]), tone_for_status(batch["status"])),
            (f"{batch['row_count']} filas", "muted"),
            (f"Versión {batch['version']}", "muted"),
        ]
    )

    _sheet_section(batch)
    _mapping_section(batch)
    _review_section(batch)


render()
