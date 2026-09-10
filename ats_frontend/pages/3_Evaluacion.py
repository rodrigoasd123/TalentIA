"""Ejecución de VERA sobre una combinación de vacante y CV.

Esta pantalla es donde se ve el principio del sistema en funcionamiento: lo que
devuelve el agente son **propuestas**, y la interfaz lo dice de forma explícita
en lugar de presentar el resultado como una decisión tomada.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Evaluación · VERA ATS", page_icon="🔎", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

st.title("🔎 Evaluación")
st.caption("Ejecuta el agente y examina cómo llegó a su resultado.")

try:
    jobs = client.list_jobs()
    resumes = client.list_resumes()
    agent = client.agent_health()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

col_job, col_cv, col_run = st.columns([2, 2, 1])

with col_job:
    job_code = st.selectbox(
        "Vacante",
        options=[j["code"] for j in jobs],
        format_func=lambda c: next(f"{j['code']} — {j['title']}" for j in jobs if j["code"] == c),
    )

with col_cv:
    resume_code = st.selectbox(
        "Candidatura",
        options=[r["code"] for r in resumes],
        format_func=lambda c: next(
            f"{r['full_name']}" + (" ⚠️" if r["is_security_fixture"] else "")
            for r in resumes
            if r["code"] == c
        ),
    )

with col_run:
    st.write("")
    st.write("")
    run = st.button("▶️ Evaluar", type="primary", use_container_width=True)

selected_resume = next(r for r in resumes if r["code"] == resume_code)
if selected_resume["purpose"]:
    st.caption(f"**Propósito de esta pieza de prueba:** {selected_resume['purpose']}")

if agent["is_simulated"]:
    st.warning(
        "Modo simulado activo: el resultado lo produce el adaptador local, no un "
        "modelo real. Configura tu API key en **Configuración** para evaluar de verdad.",
        icon="🧪",
    )

if not run:
    st.stop()

with st.spinner("Ejecutando el grafo de evaluación…"):
    try:
        result = client.run_evaluation(job_code=job_code, resume_code=resume_code)
    except ApiError as exc:
        st.error(str(exc))
        st.stop()

st.divider()

# ── Resultado ────────────────────────────────────────────────────────────────

badge = {"shortlist": "🟢", "review": "🟡", "reject": "🔴"}[result["recommendation"]]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Puntuación", f"{result['total_score']:.1f}")
c2.metric("Recomendación", f"{badge} {result['recommendation']}")
c3.metric("Evidencia verificada", f"{result['evidence_verification_rate']:.0%}")
c4.metric("Coste", f"${result['cost_usd']:.5f}")

st.success(result["explanation"], icon="📄")

# Recordatorio permanente: nada de esto se ha aplicado.
st.info(
    "**Ninguna de estas acciones se ha ejecutado.** VERA propone; el backend decide. "
    "Las acciones propuestas aparecen más abajo junto con el veredicto del motor de "
    "políticas.",
    icon="🛡️",
)

# ── Alertas de seguridad ─────────────────────────────────────────────────────

alerts = []
if result["injection_detected"]:
    alerts.append(
        f"**Intento de manipulación detectado** (severidad {result['injection_severity']}). "
        "La puntuación no se vio alterada y el caso pasa a revisión humana."
    )
if result["bias_detected"]:
    alerts.append(
        "**Posible sesgo detectado** en el razonamiento del evaluador. "
        "La evaluación no se da por válida sin revisión."
    )
for alert in alerts:
    st.error(alert, icon="🚨")

if result["requires_human_review"]:
    reasons = ", ".join(result["review_reasons"]) or "automatización desactivada"
    st.warning(f"**Requiere revisión humana.** Motivos: {reasons}", icon="👤")

st.divider()

tabs = st.tabs(
    ["⚖️ Filtros", "📊 Dimensiones y evidencia", "🛡️ Privacidad y políticas", "🔬 Trazabilidad"]
)

# ── Filtros ──────────────────────────────────────────────────────────────────

with tabs[0]:
    st.subheader("Filtros determinísticos")
    st.caption("Evaluados en código. Ninguno depende del modelo de lenguaje.")
    for item in result["hard_filters"]:
        icon = "✅" if item["passed"] else "❌"
        tag = "obligatorio" if item["mandatory"] else "valorable"
        st.markdown(f"{icon} **{item['label']}** · _{tag}_  \n&nbsp;&nbsp;&nbsp;{item['explanation']}")
    if not result["hard_filters"]:
        st.caption("Esta vacante no define filtros.")

    if result["missing_requirements"]:
        st.markdown("#### Requisitos no acreditados")
        for item in result["missing_requirements"]:
            st.markdown(f"- {item}")

# ── Dimensiones ──────────────────────────────────────────────────────────────

with tabs[1]:
    if not result["dimensions"]:
        st.info(
            "No hubo evaluación semántica. Cuando una candidatura no supera un filtro "
            "obligatorio, el grafo la omite a propósito: no tiene sentido puntuar con "
            "detalle a quien ya está excluido por una regla, y evita gastar una llamada "
            "al modelo.",
            icon="ℹ️",
        )
    for dimension in result["dimensions"]:
        with st.container(border=True):
            head, score = st.columns([3, 1])
            head.markdown(f"**{dimension['dimension']}** · peso {dimension['weight']:.0f}%")
            score.metric("", f"{dimension['score']:.0f}")
            if dimension["reasoning"]:
                st.caption(dimension["reasoning"])
            if dimension["evidence"]:
                st.markdown("**Evidencia citada del CV:**")
                for span in dimension["evidence"]:
                    mark = "✅" if span["verified"] else "❌"
                    ratio = f"{span['match_ratio']:.0%}"
                    st.markdown(
                        f"{mark} _«{span['quote']}»_ "
                        f"<span style='opacity:.6'>· coincidencia {ratio}</span>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Sin evidencia aportada para esta dimensión.")

    if result["strengths"] or result["gaps"]:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Fortalezas")
            for item in result["strengths"]:
                st.markdown(f"- {item}")
        with right:
            st.markdown("#### Carencias")
            for item in result["gaps"]:
                st.markdown(f"- {item}")

# ── Privacidad y políticas ───────────────────────────────────────────────────

with tabs[2]:
    left, right = st.columns(2)

    with left:
        st.subheader("Anonimización")
        st.metric("Elementos retirados antes del modelo", result["pii_redactions"])
        if result["pii_categories"]:
            st.markdown("**Categorías retiradas:**")
            for category in result["pii_categories"]:
                st.markdown(f"- `{category}`")
        st.caption(
            "Estos datos no cruzaron hacia el proveedor de IA. La correspondencia con "
            "la identidad real se mantiene en el backend mediante identificadores "
            "internos."
        )

    with right:
        st.subheader("Motor de políticas")
        if result["policy_decisions"]:
            for decision in result["policy_decisions"]:
                icon = {
                    "allow": "✅", "deny": "⛔", "require_human_approval": "👤"
                }.get(decision.get("decision", ""), "•")
                st.markdown(
                    f"{icon} **{decision.get('decision')}** · `{decision.get('rule')}`  \n"
                    f"&nbsp;&nbsp;&nbsp;{decision.get('reason')}"
                )
        else:
            st.caption("No se evaluó ninguna acción con efecto.")

        st.subheader("Acciones propuestas")
        for action in result["proposed_actions"]:
            st.code(action, language="text")
        if not result["proposed_actions"]:
            st.caption("El agente no propuso ninguna acción.")

# ── Trazabilidad ─────────────────────────────────────────────────────────────

with tabs[3]:
    left, right = st.columns(2)

    with left:
        st.subheader("Reproducibilidad")
        st.markdown(
            f"""
            - **Agente:** `{result['agent']} {result['agent_version']}`
            - **Modelo:** `{result['model']}`{' (simulado)' if result['is_simulated'] else ''}
            - **Traza:** `{result['trace_id']}`
            - **Ejecución:** `{result['workflow_run_id']}`
            """
        )
        st.markdown("**Versiones de prompt utilizadas:**")
        for name, version in result["prompt_versions"].items():
            st.markdown(f"- `{name}` → `{version}`")
        st.caption(
            "Con estos datos, la decisión puede reconstruirse meses después: qué "
            "agente, qué modelo, qué prompt y qué criterios se aplicaron."
        )

    with right:
        st.subheader("Consumo")
        usage = result["token_usage"]
        st.markdown(
            f"""
            - Llamadas al modelo: **{usage.get('calls', 0)}**
            - Tokens de entrada: **{usage.get('prompt_tokens', 0):,}**
            - Tokens de salida: **{usage.get('completion_tokens', 0):,}**
            - Coste estimado: **${result['cost_usd']:.5f}**
            """
        )

    st.subheader("Nodos ejecutados")
    st.caption(
        "El grafo registra cada paso con su duración. Los nodos marcados con «!» "
        "fallaron y se recuperaron o derivaron el caso a revisión."
    )
    timings = result["node_timings"]
    st.dataframe(
        [
            {
                "Orden": index + 1,
                "Nodo": node,
                "Duración (s)": round(timings.get(node.rstrip("!"), 0.0), 4),
            }
            for index, node in enumerate(result["nodes_executed"])
        ],
        use_container_width=True,
        hide_index=True,
    )
