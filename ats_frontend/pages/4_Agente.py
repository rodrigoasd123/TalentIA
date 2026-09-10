"""Inspección del agente: grafo, prompts y guardrails."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Agente · VERA ATS", page_icon="🤖", layout="wide")

client = VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))

st.title("🤖 VERA")
st.caption("Verified Evidence & Ranking Agent — arquitectura y controles")

try:
    agent = client.agent_health()
    graphs = client.agent_graph()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Versión", agent["version"])
c2.metric("Grafo", agent["graph"].split("@")[0])
c3.metric("Motor", "LangGraph" if agent["langgraph_available"] else "Nativo")
c4.metric("Prompts", len(agent["prompts"]))

st.divider()

tabs = st.tabs(["🗺️ Grafo", "🛡️ Guardrails", "📝 Prompts", "🔧 Herramientas", "🔄 Ciclo de vida"])

with tabs[0]:
    st.subheader("Grafo de evaluación")
    st.caption(
        "Diagrama generado a partir de la definición real del grafo, no escrito a "
        "mano. No puede quedar desactualizado respecto al código."
    )
    st.code(graphs["evaluation_graph"], language="text")
    st.markdown(
        """
        **Once nodos, de los cuales solo cuatro invocan un modelo.** La proporción es
        deliberada: cada decisión que puede tomarse con una regla es una decisión que
        no depende de un sistema probabilístico, no cuesta dinero y no puede
        manipularse mediante el contenido de un CV.

        Dos detalles del cableado que conviene notar:

        - **Los filtros duros cortocircuitan la evaluación semántica.** Quien no
          cumple un requisito obligatorio no se puntúa con el modelo.
        - **El nodo de cálculo se alcanza por ambos caminos.** No existe una ruta
          alternativa que produzca una decisión sin pasar por las reglas.
        """
    )

with tabs[1]:
    st.subheader("Siete capas de guardrails")
    st.caption("Cada capa asume que las anteriores pueden haber fallado.")

    layers = [
        ("G1", "Validación de entrada", "Tipo real de fichero, tamaño, longitud, codificación.",
         "Determinística"),
        ("G2", "Anti prompt injection",
         "Normalización de evasiones, detección por categoría y severidad, "
         "neutralización de delimitadores.", "Determinística"),
        ("G3", "Anonimización de PII",
         "Retira atributos protegidos e indicadores indirectos antes de cruzar hacia "
         "el modelo. Verificado por un test de frontera.", "Determinística"),
        ("G4", "Salida estructurada",
         "Validación Pydantic estricta. Ningún texto libre del modelo decide nada.",
         "Determinística"),
        ("G5", "Verificación de evidencia",
         "Cada cita debe localizarse en el documento fuente. Superar el umbral de "
         "citas no verificables invalida la evaluación.", "Determinística"),
        ("G6", "Auditoría de sesgo",
         "Capa léxica siempre activa más, opcionalmente, un segundo modelo que "
         "audita el razonamiento del primero.", "Mixta"),
        ("G7", "Motor de políticas",
         "Última palabra sobre toda acción: permitir, denegar o exigir aprobación "
         "humana. Deniega por defecto.", "Determinística"),
    ]
    for code, name, description, kind in layers:
        with st.container(border=True):
            head, tag = st.columns([4, 1])
            head.markdown(f"**{code} · {name}**")
            tag.caption(kind)
            st.caption(description)

with tabs[2]:
    st.subheader("Prompts versionados")
    st.caption(
        "Los prompts viven en ficheros YAML fuera del código. Cada evaluación "
        "registra con qué versión se hizo, y una versión publicada no se edita: se "
        "crea otra."
    )
    st.dataframe(
        [
            {
                "Prompt": p["id"],
                "Esquema de salida": p["schema"],
                "Checksum": p["checksum"],
            }
            for p in agent["prompts"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.info(
        "El checksum es del contenido literal del fichero. Si alguien edita una "
        "versión ya publicada, el checksum deja de coincidir con el registrado en las "
        "evaluaciones anteriores y la manipulación queda a la vista.",
        icon="🔐",
    )

with tabs[3]:
    left, right = st.columns(2)

    with left:
        st.subheader("✅ Herramientas permitidas")
        st.caption("Lista de permitidos. Lo que no está aquí, no existe para el agente.")
        for tool in [
            "get_candidate", "get_job", "get_job_requirements", "get_application",
            "evaluate_candidate", "request_human_review", "prepare_email",
        ]:
            st.markdown(f"- `{tool}`")

    with right:
        st.subheader("⛔ Capacidades inexistentes")
        st.caption("No están restringidas: no existen en el sistema.")
        for capability in [
            "execute_sql", "delete_record", "read_environment", "filesystem_write",
            "shell_exec", "arbitrary_python", "http_request", "send_arbitrary_email",
            "modify_policy", "modify_prompt", "read_audit_log",
        ]:
            st.markdown(f"- `{capability}`")

    st.info(
        "**`read_audit_log` merece explicación.** Si el agente pudiera leer su propia "
        "auditoría, un atacante podría usarla para descubrir qué defensas se activaron "
        "y adaptar el siguiente intento.",
        icon="🔍",
    )

    st.warning(
        "En la fase de evaluación, los agentes **no tienen herramienta alguna**: son "
        "transformadores puros de datos. Los datos los aportan nodos determinísticos "
        "que consultan los repositorios. Eso elimina de raíz toda la categoría de "
        "ataques por inyección de herramientas.",
        icon="🛡️",
    )

with tabs[4]:
    st.subheader("Ciclo de vida de una candidatura")
    st.caption(
        "Generado desde la propia máquina de estados. Las transiciones marcadas con "
        "👤 exigen decisión de una persona."
    )
    st.code(graphs["application_lifecycle"], language="text")
