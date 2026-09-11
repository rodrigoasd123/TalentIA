"""Agente de consulta limitado al contexto de TalentIA."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402
from talentia.formatters import app_status, recommendation, review_reason, score  # noqa: E402

OFFENSIVE_MARKERS = {"idiota", "estupido", "estúpido", "imbecil", "imbécil"}
SECRET_MARKERS = {"prompt", "token", "jwt", "secreto", "api key", "clave", "contraseña"}
DECISION_MARKERS = {"contratar", "rechazar", "aprobar", "descartar", "decide", "decidir"}


def _application_label(application_id: str, applications: list[dict]) -> str:
    app = next((item for item in applications if item["id"] == application_id), None)
    if not app:
        return application_id
    return f"{app['candidate_name']} · {app['job_code']} · {app_status(app['status'])}"


def _join(items: list[str], empty: str = "No hay información registrada.") -> str:
    clean = [item for item in items if item]
    if not clean:
        return empty
    return "\n".join(f"- {item}" for item in clean)


def _answer(question: str, data: dict, provider_label: str) -> dict[str, object]:  # noqa: C901
    text = question.strip().lower()
    candidate = data.get("candidate") or {}
    application = data.get("application") or {}
    job = data.get("job") or {}
    resume = data.get("resume") or {}
    evaluation = data.get("current_evaluation") or {}
    extraction = resume.get("extraction") or {}

    if not text:
        return {
            "origin": "local",
            "answer": "Escribe una pregunta sobre el expediente activo.",
            "evidence": [],
        }

    if any(marker in text for marker in OFFENSIVE_MARKERS):
        return {
            "origin": "blocked",
            "answer": (
                "No puedo continuar con lenguaje ofensivo. "
                "Reformula la pregunta de manera respetuosa."
            ),
            "evidence": [],
        }

    if any(marker in text for marker in SECRET_MARKERS):
        return {
            "origin": "blocked",
            "answer": (
                "No revelo prompts, claves, tokens, secretos ni detalles internos "
                "no autorizados."
            ),
            "evidence": [],
        }

    if any(marker in text for marker in DECISION_MARKERS):
        return {
            "origin": "blocked",
            "answer": (
                "No ejecuto ni recomiendo decisiones de contratación. Puedo explicar evidencia "
                "del expediente para que una persona autorizada decida."
            ),
            "evidence": [],
        }

    if any(greeting in text for greeting in {"hola", "buenos dias", "buenos días", "buenas"}):
        return {
            "origin": "local",
            "answer": (
                "Hola. Soy el agente de consulta de TalentIA. Respondo solo sobre la vacante, "
                "postulación o candidato que tienes seleccionado."
            ),
            "evidence": ["Contexto activo de la sesión"],
        }

    if "gemini" in text or "modelo" in text or "proveedor" in text:
        return {
            "origin": "local",
            "answer": (
                f"El contexto actual indica proveedor: {provider_label}. "
                "No se muestra ninguna clave."
            ),
            "evidence": ["Estado público del proveedor"],
        }

    if "vacante" in text or "puesto" in text:
        return {
            "origin": "local",
            "answer": f"Vacante activa: {job.get('code', '-')} · {job.get('title', '-')}.",
            "evidence": ["Candidate 360: vacante"],
        }

    if "estado" in text or "etapa" in text:
        return {
            "origin": "local",
            "answer": (
                f"La postulación está en {app_status(application.get('status', ''))}. "
                "Consentimiento/base legal: "
                f"{'vigente' if candidate.get('consent_valid') else 'no vigente'}."
            ),
            "evidence": ["Candidate 360: postulación y candidato"],
        }

    if "puntaje" in text or "evaluacion" in text or "evaluación" in text:
        if not evaluation:
            return {
                "origin": "local",
                "answer": "No hay evaluación vigente para esta postulación.",
                "evidence": ["Candidate 360: evaluación"],
            }
        reasons = ", ".join(
            review_reason(reason) for reason in evaluation.get("review_reasons", []) or []
        )
        return {
            "origin": "local",
            "answer": (
                f"Puntaje orientativo: {score(evaluation.get('score'))}. "
                f"Resultado: {recommendation(evaluation.get('recommendation', ''))}. "
                + (f"Motivos de revisión: {reasons}." if reasons else "")
            ),
            "evidence": ["Evaluación actual"],
        }

    if "requisito" in text or "filtro" in text:
        filters = evaluation.get("hard_filters", []) or []
        missing = evaluation.get("missing_requirements", []) or []
        answer = "Requisitos evaluados:\n" + _join(
            [
                f"{item.get('label', '-')}: {'cumple' if item.get('passed') else 'no acreditado'}"
                for item in filters
            ],
            "No hay requisitos determinísticos registrados.",
        )
        if missing:
            answer += "\n\nInformación no encontrada:\n" + _join(missing)
        return {"origin": "local", "answer": answer, "evidence": ["Evaluación actual: filtros"]}

    if "habilidad" in text or "tecnologia" in text or "tecnología" in text:
        skills = sorted(
            set((extraction.get("skills", []) or []) + (extraction.get("technologies", []) or []))
        )
        return {
            "origin": "local",
            "answer": "Habilidades detectadas:\n" + _join(skills),
            "evidence": ["CV procesado: extracción"],
        }

    if "experiencia" in text:
        experiences = extraction.get("experiences", []) or []
        rows = [
            f"{item.get('role', '-')} en {item.get('company', '-')} "
            f"({item.get('start_date', '-')} a {item.get('end_date') or 'actualidad'})"
            for item in experiences
        ]
        return {
            "origin": "local",
            "answer": "Experiencia detectada:\n" + _join(rows),
            "evidence": ["CV procesado: experiencia"],
        }

    if "educacion" in text or "educación" in text or "formacion" in text or "formación" in text:
        education = extraction.get("education", []) or []
        rows = [f"{item.get('degree', '-')} · {item.get('level', '-')}" for item in education]
        return {
            "origin": "local",
            "answer": "Formación detectada:\n" + _join(rows),
            "evidence": ["CV procesado: educación"],
        }

    return {
        "origin": "local",
        "answer": (
            "No encuentro evidencia suficiente en el contexto activo para responder. "
            "Prueba preguntando por vacante, estado, puntaje, requisitos, "
            "experiencia, educación o habilidades."
        ),
        "evidence": ["Contexto activo insuficiente"],
    }


def render() -> None:  # noqa: C901 - Flujo conversacional compacto en una página.
    if not session.require_permission("candidate:pii:read", "application:read"):
        return

    design.page_header(
        "Agente de consulta",
        "Preguntas simples sobre el expediente seleccionado, con contexto visible.",
        "Expediente",
    )

    try:
        applications = session.client().list_applications()
    except ApiError as exc:
        design.api_error(exc, "No se pudieron cargar postulaciones")
        return
    if not applications:
        design.empty_state("Sin contexto", "Registra una postulación antes de consultar al agente.")
        return

    preselected = st.session_state.get("selected_application")
    options = [item["id"] for item in applications]
    index = options.index(preselected) if preselected in options else 0
    selected = st.selectbox(
        "Contexto documental activo",
        options=options,
        index=index,
        format_func=lambda value: _application_label(value, applications),
    )
    st.session_state["selected_application"] = selected

    try:
        data = session.client().candidate_360(selected)
    except ApiError as exc:
        design.api_error(exc, "No se pudo cargar el contexto")
        return

    provider_label = "fallback local"
    if session.has_permission("settings:read"):
        try:
            agent = session.client().agent_health()
            provider_label = (
                "simulado" if agent.get("is_simulated") else agent.get("provider", "configurado")
            )
        except ApiError:
            provider_label = "no disponible"

    resume = data.get("resume") or {}
    job = data.get("job") or {}
    design.badge_row(
        [
            (f"Vacante {job.get('code', '-')}", "info"),
            (f"CV versión {resume.get('version', '-')}", "muted"),
            (
                f"Proveedor: {provider_label}",
                "warning" if provider_label in {"simulado", "fallback local"} else "success",
            ),
        ]
    )
    st.caption(
        "Este agente no cambia estados, no envía correos y no revela secretos. "
        "Las respuestas son locales porque no existe endpoint conversacional ATS."
    )

    key = f"agent_messages_{selected}"
    st.session_state.setdefault(key, [])

    for message in st.session_state[key]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message["role"] == "assistant":
                design.badge_row([(message.get("origin", "local"), "info")])
                evidence = message.get("evidence", [])
                if evidence:
                    st.caption("Evidencia: " + ", ".join(evidence))

    question = st.chat_input("Pregunta sobre el expediente activo")
    if question:
        st.session_state[key].append({"role": "user", "content": question})
        result = _answer(question, data, provider_label)
        st.session_state[key].append(
            {
                "role": "assistant",
                "content": result["answer"],
                "origin": result["origin"],
                "evidence": result["evidence"],
            }
        )
        st.rerun()


render()
