"""Cola de revisión humana.

Es la pantalla donde el sistema devuelve el control a una persona, así que está
construida para que decidir bien sea más fácil que decidir rápido: la evidencia
se muestra antes que los botones, y la justificación es obligatoria.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Revisión · VERA ATS", page_icon="👤", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

PRIORITY_STYLE = {
    "critical": ("🔴", "Crítica"),
    "high": ("🟠", "Alta"),
    "medium": ("🟡", "Media"),
    "low": ("🔵", "Baja"),
    "info": ("⚪", "Informativa"),
}

REASON_LABELS = {
    "injection_detected": "Intento de manipulación en el CV",
    "bias_detected": "Posible sesgo en el razonamiento",
    "evidence_unverifiable": "Evidencia no verificable",
    "hard_filter_failed": "No cumple requisitos obligatorios",
    "score_borderline": "Puntuación en zona gris",
    "low_parse_confidence": "Extracción poco fiable",
    "incomplete_resume": "CV incompleto",
    "senior_candidate": "Perfil senior",
    "llm_failure": "Fallo del modelo",
    "budget_exceeded": "Presupuesto de IA agotado",
    "possible_duplicate": "Posible candidatura duplicada",
    "score_override": "Puntuación modificada manualmente",
}

st.title("👤 Revisión humana")
st.caption(
    "Casos que el sistema no resuelve por su cuenta. La decisión y su "
    "justificación quedan registradas de forma permanente."
)

try:
    queue = client.review_queue()
    stats = client.review_statistics()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Pendientes", stats["pending"])
m2.metric("Fuera de plazo", stats["overdue"], delta=None if not stats["overdue"] else "atención")
m3.metric("Críticos", stats["by_priority"].get("critical", 0))
m4.metric("Altos", stats["by_priority"].get("high", 0))

if stats["overdue"]:
    st.warning(
        f"{stats['overdue']} elemento(s) han superado su plazo. Al vencer no se "
        "resuelven solos: se liberan, suben de prioridad y siguen esperando a una "
        "persona.",
        icon="⏰",
    )

st.divider()

if not queue:
    st.success("La cola está vacía.", icon="✅")
    st.stop()

# ── Selección ────────────────────────────────────────────────────────────────

left, right = st.columns([1, 2])

with left:
    st.subheader("Cola")
    st.caption("Ordenada por prioridad y, dentro de cada nivel, por antigüedad.")
    for item in queue:
        icon, label = PRIORITY_STYLE.get(item["priority"], ("⚪", item["priority"]))
        vencido = " ⏰" if item["is_overdue"] else ""
        etiqueta = (
            f"{icon} {item['candidate_name'][:26]}{vencido}\n"
            f"{item['job_code']} · {label}"
        )
        if st.button(etiqueta, key=f"pick-{item['id']}", use_container_width=True):
            st.session_state["review_item"] = item["id"]

selected_id = st.session_state.get("review_item") or queue[0]["id"]
item = next((i for i in queue if i["id"] == selected_id), queue[0])

with right:
    icon, label = PRIORITY_STYLE.get(item["priority"], ("⚪", item["priority"]))
    st.subheader(f"{icon} {item['candidate_name']}")
    st.caption(
        f"Vacante `{item['job_code']}` · prioridad {label} · "
        f"plazo {item['sla_hours']} h"
        + (" · **fuera de plazo**" if item["is_overdue"] else "")
    )

    motivos = [REASON_LABELS.get(r, r) for r in item["reasons"]]
    st.markdown("**Por qué está aquí:**")
    for motivo, código in zip(motivos, item["reasons"], strict=True):
        alerta = código in {"injection_detected", "bias_detected"}
        st.markdown(("🚨 " if alerta else "• ") + motivo)

    if item.get("score") is not None:
        st.metric("Puntuación propuesta", f"{item['score']:.1f}")

    # ── Evidencia antes que botones ──────────────────────────────────────────
    try:
        detail = client.candidate_360(item["application_id"])
    except ApiError as exc:
        st.error(str(exc))
        detail = {}

    evaluation = detail.get("current_evaluation")
    if evaluation:
        with st.expander("📊 Evaluación completa", expanded=True):
            st.caption(evaluation.get("summary", ""))

            if evaluation["hard_filters"]:
                st.markdown("**Requisitos obligatorios**")
                for f in evaluation["hard_filters"]:
                    marca = "✅" if f["passed"] else "❌"
                    st.markdown(f"{marca} {f['label']} — {f['explanation']}")

            if evaluation["dimensions"]:
                st.markdown("**Puntuación por dimensión y evidencia citada**")
                for d in evaluation["dimensions"]:
                    st.markdown(
                        f"**{d['dimension']}** · {d['score']:.0f}/100 (peso {d['weight']:.0f}%)"
                    )
                    for span in d["evidence"]:
                        marca = "✅" if span["verified"] else "❌"
                        st.markdown(
                            f"&nbsp;&nbsp;{marca} _«{span['quote'][:180]}»_",
                            unsafe_allow_html=True,
                        )
            st.caption(
                f"Evidencia verificada: {evaluation['evidence_rate']:.0%} · "
                f"modelo `{evaluation['model']}` · agente `{evaluation['agent_version']}`"
            )

    if detail.get("resume"):
        with st.expander("📄 CV original (con datos personales)"):
            st.caption(
                "El revisor ve el documento completo; el modelo lo evaluó "
                "anonimizado. Es deliberado: la persona necesita contexto que a la "
                "IA no le corresponde tener."
            )
            st.info(
                f"Fichero `{detail['resume']['filename']}` · "
                f"{detail['resume']['chars']} caracteres"
                + (" · ⚠️ marcado como sospechoso" if detail["resume"]["is_suspicious"] else "")
            )

    st.divider()

    # ── Decisión ─────────────────────────────────────────────────────────────
    st.subheader("Decisión")

    if item["assigned_to"] is None:
        if st.button("🙋 Asignarme este caso", use_container_width=True):
            try:
                client.claim_review(item["id"])
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))
    else:
        st.caption(f"Asignado a `{item['assigned_to']}`")

    decision = st.radio(
        "Qué decides",
        options=["approve", "reject", "modify", "reevaluate", "escalate"],
        format_func=lambda d: {
            "approve": "✅ Aprobar — avanza a preseleccionado",
            "reject": "🔴 Rechazar — cierra la candidatura",
            "modify": "✏️ Modificar la puntuación",
            "reevaluate": "🔄 Solicitar nueva evaluación",
            "escalate": "⬆️ Escalar a un responsable",
        }[d],
        horizontal=False,
    )

    score_override = None
    if decision == "modify":
        score_override = st.slider(
            "Nueva puntuación",
            0.0, 100.0,
            float(item.get("score") or 50.0), step=0.5,
        )
        st.caption(
            "La evaluación original no se modifica: es inmutable. Se registra tu "
            "anulación junto a ella, con ambos valores."
        )

    if decision == "reject":
        st.warning(
            "Un rechazo es irreversible y afecta a una persona real. La "
            "justificación que escribas formará parte del expediente y podrá "
            "mostrarse si el candidato solicita explicación.",
            icon="⚠️",
        )

    justification = st.text_area(
        "Justificación (obligatoria)",
        placeholder=(
            "Explica en qué te basas. Por ejemplo: «He verificado la experiencia "
            "en FastAPI en el proyecto descrito y coincide con lo que pide la "
            "vacante»."
        ),
        height=110,
    )

    if st.button("Registrar decisión", type="primary", use_container_width=True):
        if len(justification.strip()) < 10:
            st.error("La justificación es obligatoria y debe explicar el motivo.")
        else:
            try:
                result = client.decide_review(
                    item["id"],
                    decision=decision,
                    justification=justification,
                    score_override=score_override,
                )
                st.success(
                    f"Decisión registrada. La candidatura pasa a "
                    f"«{result['application_status']}».",
                    icon="✅",
                )
                st.session_state.pop("review_item", None)
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))

st.divider()
with st.expander("Motivos de revisión más frecuentes"):
    st.caption(
        "Si un motivo domina la cola, suele indicar un umbral mal calibrado más "
        "que un problema con las candidaturas."
    )
    st.dataframe(
        [
            {"Motivo": REASON_LABELS.get(k, k), "Casos": v}
            for k, v in stats["by_reason"].items()
        ],
        use_container_width=True, hide_index=True,
    )
