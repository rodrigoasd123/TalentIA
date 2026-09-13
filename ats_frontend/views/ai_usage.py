"""Vista autorizada de observabilidad de IA, siempre a través de la API."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402

st.set_page_config(page_title="Consumo de IA | TalentIA", page_icon="📈", layout="wide")
design.apply_theme()
session.require_login()

design.page_header(
    "Observabilidad de IA",
    "Consumo técnico agregado sin exponer prompts, respuestas, CVs ni credenciales.",
    "Control",
)

if not session.has_permission("settings:read"):
    st.warning("Tu rol no permite consultar la observabilidad de IA.")
    st.stop()

try:
    telemetry = session.client().llm_observability()
except ApiError as exc:
    design.api_error(exc, "No se pudo consultar la observabilidad")
    st.stop()

st.caption(str(telemetry.get("privacy", "")))
design.badge_row(
    [
        ("MLflow activo" if telemetry.get("enabled") else "MLflow desactivado", "info"),
        ("Instalado" if telemetry.get("installed") else "No instalado", "muted"),
    ]
)
rows = telemetry.get("usage", [])
if not rows:
    design.empty_state("Sin llamadas registradas", "Ejecuta una evaluación o benchmark.")
else:
    total_calls = sum(int(row.get("calls", 0)) for row in rows)
    total_tokens = sum(int(row.get("total_tokens", 0)) for row in rows)
    total_errors = sum(int(row.get("errors", 0)) for row in rows)
    design.metric_grid(
        [
            ("Llamadas", str(total_calls), ""),
            ("Tokens", str(total_tokens), ""),
            ("Errores", str(total_errors), ""),
        ]
    )
    st.dataframe(rows, width="stretch", hide_index=True)
