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
if telemetry.get("enabled") and telemetry.get("installed") and telemetry.get("ui_url"):
    st.link_button("Abrir MLflow", str(telemetry["ui_url"]), type="primary")
else:
    st.info("MLflow no está disponible; la telemetría local continúa operativa.")

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

st.subheader("Procesos y grafos")
status_filter = st.selectbox(
    "Estado",
    ["", "running", "completed", "awaiting_human", "failed", "cancelled"],
    format_func=lambda value: "Todos" if not value else value,
)
try:
    processes = session.client().observed_processes(limit=100, status=status_filter)
except ApiError as exc:
    design.api_error(exc, "No se pudieron cargar los procesos")
    processes = {"items": []}

process_rows = list(processes.get("items", []))
if not process_rows:
    design.empty_state("Sin procesos observados", "Ejecuta una evaluación para generar una traza.")
else:
    st.dataframe(
        [
            {
                "Inicio": item.get("started_at"),
                "Proceso": item.get("id"),
                "Traza": item.get("trace_id"),
                "Grafo": item.get("graph"),
                "Estado": item.get("status"),
                "Proveedor": item.get("provider"),
                "Modelo": item.get("model"),
                "Duración (s)": item.get("duration_seconds"),
                "Entrada": item.get("token_usage", {}).get("prompt_tokens", 0),
                "Salida": item.get("token_usage", {}).get("completion_tokens", 0),
                "Total": item.get("token_usage", {}).get("total_tokens", 0),
            }
            for item in process_rows
        ],
        width="stretch",
        hide_index=True,
    )
    selected = st.selectbox(
        "Inspeccionar proceso",
        process_rows,
        format_func=lambda item: (
            f"{item.get('started_at')} · {item.get('graph')} · {item.get('id')}"
        ),
    )
    try:
        detail = session.client().observed_process(str(selected["id"]))
        st.caption(str(detail.get("privacy", "")))
        nodes = list(detail.get("node_runs", []))
        st.dataframe(
            [
                {
                    "#": node.get("sequence"),
                    "Nodo": node.get("node"),
                    "Estado": node.get("status"),
                    "Intentos": node.get("attempts"),
                    "Duración (s)": node.get("duration_seconds"),
                    "Tokens entrada": node.get("prompt_tokens", 0),
                    "Tokens salida": node.get("completion_tokens", 0),
                    "Tokens total": node.get("total_tokens", 0),
                    "Error": node.get("error_type", ""),
                }
                for node in nodes
            ],
            width="stretch",
            hide_index=True,
        )
        with st.expander("Topología del grafo"):
            st.code(str(detail.get("topology", "Sin topología disponible")), language="mermaid")
    except ApiError as exc:
        design.api_error(exc, "No se pudo abrir la traza")

st.subheader("Histórico de benchmarking")
try:
    benchmarks = session.client().model_benchmarks(limit=25).get("items", [])
except ApiError as exc:
    design.api_error(exc, "No se pudo cargar el histórico de benchmarks")
    benchmarks = []

if not benchmarks:
    design.empty_state(
        "Sin benchmarks registrados",
        "Ejecuta una comparación gobernada desde Configuración.",
    )
else:
    selected_benchmark = st.selectbox(
        "Ejecución",
        benchmarks,
        format_func=lambda item: (
            f"{item.get('created_at')} · {item.get('suite_version')} · {item.get('id')}"
        ),
    )
    st.caption(
        f"Baseline: {selected_benchmark.get('baseline_model')} · "
        f"Suite: {selected_benchmark.get('suite_version')} "
        f"({selected_benchmark.get('suite_hash')})"
    )
    st.dataframe(selected_benchmark.get("ranking", []), width="stretch", hide_index=True)
