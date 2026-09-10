"""Auditoría: registro inmutable y verificación de integridad."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Auditoría · VERA ATS", page_icon="📜", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

ACTOR_ICON = {"user": "👤", "ai_agent": "🤖", "system": "⚙️"}
SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}

st.title("📜 Auditoría")
st.caption(
    "Registro de solo inserción. Ningún camino de la aplicación permite modificar "
    "ni eliminar un evento."
)

try:
    integrity = client.verify_audit()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

# ── Integridad ───────────────────────────────────────────────────────────────

if integrity["verified"]:
    st.success(integrity["message"], icon="🔐")
else:
    st.error(integrity["message"], icon="🚨")

with st.expander("Cómo funciona la verificación", expanded=not integrity["verified"]):
    st.markdown(
        """
        Cada evento incorpora el hash del evento anterior, formando una cadena.
        Alterar un evento pasado cambia su hash, y eso rompe el enlace de todos
        los posteriores.

        La verificación recorre la cadena completa y señala **el primer punto**
        donde deja de cuadrar. Detecta tanto la modificación de un evento como su
        eliminación: al borrar una fila, el enlace del siguiente deja de apuntar
        a nada válido.

        En producción esto se refuerza con permisos de rol de base de datos que
        impiden `UPDATE` y `DELETE` sobre la tabla, incluso por SQL directo.
        """
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("Eventos registrados", integrity["total_events"])
by_severity = integrity["by_severity"]
c2.metric("Críticos", by_severity.get("critical", 0))
c3.metric("Altos", by_severity.get("high", 0))
c4.metric("Cadena", "Íntegra" if integrity["verified"] else "Comprometida")

st.divider()

# ── Filtros ──────────────────────────────────────────────────────────────────

f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
with f1:
    action_filter = st.text_input(
        "Acción", placeholder="por ejemplo: evaluation.completed"
    )
with f2:
    resource_filter = st.text_input("Identificador de recurso", placeholder="candidatura o candidato")
with f3:
    severity_filter = st.selectbox(
        "Severidad", options=["(todas)", "critical", "high", "medium", "low", "info"]
    )
with f4:
    limit = st.number_input("Máximo", min_value=10, max_value=1000, value=150, step=50)

try:
    events = client.audit_events(
        action=action_filter or None,
        resource_id=resource_filter or None,
        severity=None if severity_filter.startswith("(") else severity_filter,
        limit=int(limit),
    )
except ApiError as exc:
    st.error(str(exc))
    st.stop()

st.caption(f"{len(events)} evento(s)")

# ── Incidentes de seguridad ──────────────────────────────────────────────────

security = [e for e in events if e["severity"] in {"critical", "high"}]
if security:
    st.subheader("🚨 Incidentes de seguridad")
    for event in security:
        with st.container(border=True):
            st.markdown(
                f"{SEVERITY_ICON.get(event['severity'], '•')} **{event['action']}** · "
                f"{event['timestamp'][:19]}"
            )
            st.caption(
                f"Recurso `{event['resource_id'][:12]}` · actor "
                f"{ACTOR_ICON.get(event['actor_type'], '')} {event['actor_id']}"
            )
            if event["metadata"]:
                st.json(event["metadata"], expanded=False)
    st.divider()

# ── Registro ─────────────────────────────────────────────────────────────────

st.subheader("Registro completo")
st.dataframe(
    [
        {
            "Fecha": e["timestamp"][:19],
            "Actor": f"{ACTOR_ICON.get(e['actor_type'], '')} {e['actor_id'][:14]}",
            "Acción": e["action"],
            "Recurso": e["resource_id"][:12],
            "Severidad": f"{SEVERITY_ICON.get(e['severity'], '')} {e['severity']}",
            "Política": e["policy_result"][:60],
            "Traza": e["trace_id"][:10],
        }
        for e in events
    ],
    use_container_width=True,
    hide_index=True,
    height=420,
)

# ── Detalle ──────────────────────────────────────────────────────────────────

if events:
    st.subheader("Detalle de un evento")
    selected = st.selectbox(
        "Evento",
        options=[e["event_id"] for e in events],
        format_func=lambda i: next(
            f"{e['timestamp'][:19]} · {e['action']}" for e in events if e["event_id"] == i
        ),
    )
    event = next(e for e in events if e["event_id"] == selected)

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Estado anterior**")
        st.json(event["previous_state"] or {}, expanded=True)
    with d2:
        st.markdown("**Estado nuevo**")
        st.json(event["new_state"] or {}, expanded=True)

    st.markdown("**Metadatos**")
    st.json(event["metadata"] or {}, expanded=False)

    st.caption(
        f"Identificador `{event['event_id']}` · traza `{event['trace_id']}` · "
        f"actor `{event['actor_id']}`"
    )
