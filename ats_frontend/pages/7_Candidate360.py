"""Candidate 360: toda la información de una candidatura en una pantalla."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Candidate 360 · VERA ATS", page_icon="🧑", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

st.title("🧑 Candidate 360")

try:
    applications = client.list_applications()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not applications:
    st.info("No hay candidaturas registradas. Ejecuta `python scripts/seed.py`.")
    st.stop()

preselected = st.session_state.get("selected_application")
options = [a["id"] for a in applications]
index = options.index(preselected) if preselected in options else 0

selected = st.selectbox(
    "Candidatura",
    options=options,
    index=index,
    format_func=lambda i: next(
        f"{a['candidate_name']} — {a['job_code']} ({a['status']})"
        for a in applications if a["id"] == i
    ),
)
st.session_state["selected_application"] = selected

try:
    data = client.candidate_360(selected)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

candidate = data.get("candidate") or {}
application = data["application"]
job = data.get("job") or {}

# ── Cabecera ─────────────────────────────────────────────────────────────────

st.subheader(candidate.get("full_name", "—"))
st.caption(
    f"{job.get('code', '—')} — {job.get('title', '')} · "
    f"candidatura registrada el {application['applied_at'][:10]} · "
    f"origen «{application['source']}»"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Estado", application["status"])
c2.metric("Puntuación", f"{application['score']:.1f}" if application["score"] else "—")
c3.metric("Días en etapa", f"{application['hours_in_stage'] / 24:.1f}")
c4.metric("Consentimiento", "Vigente" if candidate.get("consent_valid") else "Caducado")

if not candidate.get("consent_valid"):
    st.error(
        "El consentimiento de este candidato no está vigente. El sistema no "
        "procesará sus datos hasta que se renueve.",
        icon="🔒",
    )

if data.get("open_review"):
    review = data["open_review"]
    st.warning(
        f"Hay un caso abierto en la cola de revisión (prioridad "
        f"{review['priority']}, motivos: {', '.join(review['reasons'])})"
        + (" — **fuera de plazo**" if review["is_overdue"] else ""),
        icon="👤",
    )

st.divider()

tabs = st.tabs([
    "📊 Evaluación", "📄 CV y datos extraídos", "🕐 Historial",
    "✉️ Comunicaciones", "📜 Traza de decisión",
])

# ── Evaluación ───────────────────────────────────────────────────────────────

with tabs[0]:
    evaluation = data.get("current_evaluation")
    if not evaluation:
        st.info("Esta candidatura todavía no se ha evaluado.")
        if st.button("▶️ Evaluar ahora", type="primary"):
            try:
                with st.spinner("Ejecutando VERA…"):
                    client.evaluate_application(selected, dry_run=False)
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))
    else:
        e1, e2, e3 = st.columns(3)
        e1.metric("Puntuación", f"{evaluation['score']:.1f}" if evaluation["score"] else "—")
        e2.metric("Recomendación", evaluation["recommendation"])
        e3.metric("Evidencia verificada", f"{evaluation['evidence_rate']:.0%}")

        st.info(evaluation["summary"] or "Sin resumen.", icon="📄")

        if evaluation["review_reasons"]:
            st.warning(
                "Motivos de revisión: " + ", ".join(evaluation["review_reasons"]),
                icon="👤",
            )

        bias = evaluation.get("bias_audit")
        if bias and bias.get("bias_detected"):
            st.error(
                f"Auditoría de sesgo: {bias.get('explanation', '')}", icon="🚨"
            )

        st.markdown("#### Requisitos obligatorios")
        for f in evaluation["hard_filters"]:
            marca = "✅" if f["passed"] else "❌"
            tipo = "obligatorio" if f["mandatory"] else "valorable"
            st.markdown(f"{marca} **{f['label']}** _({tipo})_ — {f['explanation']}")

        if evaluation["dimensions"]:
            st.markdown("#### Puntuación por dimensión")
            for d in evaluation["dimensions"]:
                with st.container(border=True):
                    head, score = st.columns([3, 1])
                    head.markdown(f"**{d['dimension']}** · peso {d['weight']:.0f}%")
                    score.metric("", f"{d['score']:.0f}")
                    if d["reasoning"]:
                        st.caption(d["reasoning"])
                    for span in d["evidence"]:
                        marca = "✅" if span["verified"] else "❌"
                        st.markdown(
                            f"{marca} _«{span['quote']}»_ "
                            f"<span style='opacity:.6'>· {span['match_ratio']:.0%}</span>",
                            unsafe_allow_html=True,
                        )

        col_a, col_b = st.columns(2)
        with col_a:
            if evaluation["strengths"]:
                st.markdown("#### Fortalezas")
                for s in evaluation["strengths"]:
                    st.markdown(f"- {s}")
        with col_b:
            if evaluation["missing_requirements"]:
                st.markdown("#### Requisitos no acreditados")
                for s in evaluation["missing_requirements"]:
                    st.markdown(f"- {s}")

        st.caption(
            f"Modelo `{evaluation['model']}` · agente `{evaluation['agent_version']}` · "
            f"prompts {evaluation['prompt_versions']} · coste ${evaluation['cost_usd']:.5f}"
        )

        if len(data["evaluation_history"]) > 1:
            with st.expander(f"Historial de evaluaciones ({len(data['evaluation_history'])})"):
                st.caption(
                    "Las evaluaciones son inmutables. Reevaluar crea una nueva y "
                    "marca la anterior como sustituida, de modo que siempre se puede "
                    "reconstruir con qué criterios se decidió en cada momento."
                )
                for h in data["evaluation_history"]:
                    estado = "vigente" if h["is_current"] else "sustituida"
                    st.markdown(
                        f"- {h['created_at'][:16]} · **{h['score']:.1f}** · "
                        f"{h['recommendation']} _({estado})_"
                        if h["score"] else f"- {h['created_at'][:16]} · _{estado}_"
                    )

# ── CV ───────────────────────────────────────────────────────────────────────

with tabs[1]:
    resume = data.get("resume")
    if not resume:
        st.info("No hay CV asociado a esta candidatura.")
    else:
        st.caption(
            f"`{resume['filename']}` · versión {resume['version']} · "
            f"{resume['chars']} caracteres"
        )
        if resume["is_suspicious"]:
            st.error(
                "Este documento fue marcado como sospechoso: contiene texto que "
                "intenta dirigirse al sistema automático. La puntuación no se vio "
                "alterada, pero conviene revisarlo con atención.",
                icon="🚨",
            )

        extraction = resume.get("extraction")
        if extraction:
            x1, x2, x3 = st.columns(3)
            x1.metric("Experiencia", f"{extraction['total_years_experience']:.0f} años")
            x2.metric("Nivel", extraction["seniority"])
            x3.metric("Tecnologías", len(extraction.get("technologies", [])))

            st.markdown("#### Habilidades detectadas")
            skills = sorted(set(extraction.get("skills", []) + extraction.get("technologies", [])))
            st.write(" · ".join(f"`{s}`" for s in skills) or "—")

            if extraction.get("experiences"):
                st.markdown("#### Experiencia")
                for exp in extraction["experiences"]:
                    st.markdown(
                        f"- **{exp['role']}** en {exp['company']} "
                        f"({exp['start_date']} – {exp['end_date'] or 'actualidad'}) "
                        f"· {exp['years']:.0f} años"
                    )

            if extraction.get("education"):
                st.markdown("#### Formación")
                for edu in extraction["education"]:
                    st.markdown(f"- {edu['degree']} _{edu['level']}_")

            if extraction.get("languages"):
                st.markdown("#### Idiomas")
                st.write(
                    " · ".join(
                        f"{lang['language']} {lang['level'].upper()}"
                        for lang in extraction["languages"]
                    )
                )

            confianza = extraction.get("field_confidence", {})
            if confianza:
                media = sum(confianza.values()) / len(confianza)
                if media < 0.65:
                    st.warning(
                        f"Confianza media de la extracción: {media:.0%}. El documento "
                        "es ambiguo y los datos de arriba pueden ser incompletos.",
                        icon="⚠️",
                    )

        st.markdown("#### Datos de contacto")
        st.caption(
            "El modelo no vio nada de esto: se anonimiza antes de cualquier llamada "
            "al proveedor de IA."
        )
        st.markdown(
            f"- Correo: `{candidate.get('email', '—')}`\n"
            f"- Teléfono: `{candidate.get('phone') or '—'}`\n"
            f"- Ubicación: {candidate.get('location') or '—'}"
        )

# ── Historial ────────────────────────────────────────────────────────────────

with tabs[2]:
    st.caption("Cada paso registrado, en orden cronológico.")
    for step in data["timeline"]:
        icono = {"user": "👤", "ai_agent": "🤖", "system": "⚙️"}.get(step["actor_type"], "•")
        alerta = "🚨 " if step["severity"] in {"high", "critical"} else ""
        st.markdown(
            f"{icono} **{step['timestamp'][:16]}** — {alerta}{step['description']}"
            + (f"  \n&nbsp;&nbsp;&nbsp;{step['detail']}" if step["detail"] else "")
        )

# ── Comunicaciones ───────────────────────────────────────────────────────────

with tabs[3]:
    try:
        provider = client.email_provider()
        templates = client.email_templates()
    except ApiError as exc:
        st.error(str(exc))
        provider, templates = {}, []

    if provider.get("is_simulated"):
        st.warning(
            "Gmail no está configurado: los envíos se simulan y no llega nada a "
            "nadie. Configúralo en **Configuración → Google / Gmail**.",
            icon="✉️",
        )

    if data["emails"]:
        st.markdown("#### Enviadas")
        for mail in data["emails"]:
            st.markdown(
                f"- **{mail['subject']}** → {mail['recipient']} · "
                f"`{mail['status']}`"
                + (f" · {mail['sent_at'][:16]}" if mail["sent_at"] else "")
            )
    else:
        st.caption("No se ha enviado ninguna comunicación todavía.")

    st.markdown("#### Preparar una comunicación")
    if templates:
        code = st.selectbox(
            "Plantilla",
            options=[t["code"] for t in templates],
            format_func=lambda c: next(
                f"{t['code']}" + (" · requiere aprobación" if t["requires_human_approval"] else "")
                for t in templates if t["code"] == c
            ),
        )
        use_ai = st.toggle(
            "Rellenar variables con IA", value=False,
            help=(
                "El modelo solo completa las variables declaradas por la plantilla. "
                "No redacta el mensaje ni decide el destinatario."
            ),
        )
        if st.button("Preparar borrador"):
            try:
                draft = client.prepare_email(
                    application_id=selected, template_code=code, use_ai=use_ai
                )
                st.success("Borrador creado.", icon="✅")
                st.text_input("Asunto", draft["subject"], disabled=True)
                st.text_area("Cuerpo", draft["body"], height=240, disabled=True)
                st.caption(
                    f"Destinatario: {draft['recipient']} · estado `{draft['status']}`"
                )
                if draft["requires_approval"]:
                    st.info(
                        "Esta categoría exige aprobación humana antes de enviarse. "
                        "Puedes aprobarla desde la página de Comunicaciones.",
                        icon="👤",
                    )
            except ApiError as exc:
                st.error(str(exc))

# ── Traza de decisión ────────────────────────────────────────────────────────

with tabs[4]:
    st.caption(
        "Documento completo de trazabilidad. Es lo que se entrega si el candidato "
        "solicita explicación o si llega una auditoría."
    )
    try:
        markdown = client.decision_trail(selected, fmt="markdown")
        csv = client.decision_trail(selected, fmt="csv")
    except ApiError as exc:
        st.error(str(exc))
        st.stop()

    d1, d2 = st.columns(2)
    d1.download_button(
        "⬇️ Descargar informe (Markdown)",
        data=markdown,
        file_name=f"traza-{selected[:8]}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    d2.download_button(
        "⬇️ Descargar historial (CSV)",
        data=csv,
        file_name=f"traza-{selected[:8]}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.divider()
    st.markdown(markdown)
