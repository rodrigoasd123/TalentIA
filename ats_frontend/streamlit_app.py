"""VERA ATS — interfaz de laboratorio.

Streamlit actúa aquí como **cliente del backend y nada más**: no importa el
dominio, no abre la base de datos y no contiene reglas de negocio. Todo lo que
muestra procede de la API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(
    page_title="VERA ATS",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_client() -> VeraApiClient:
    base_url = st.session_state.get("api_base_url", DEFAULT_BASE_URL)
    return VeraApiClient(base_url)


def sidebar_status() -> None:
    """Estado del backend y del proveedor de IA, visible en todas las páginas."""
    with st.sidebar:
        st.markdown("### VERA")
        st.caption("Verified Evidence & Ranking Agent")

        st.text_input(
            "URL del backend",
            value=st.session_state.get("api_base_url", DEFAULT_BASE_URL),
            key="api_base_url",
            help="Dirección de la API de FastAPI.",
        )

        client = get_client()
        try:
            health = client.health()
            agent = client.agent_health()
        except ApiError as exc:
            st.error("Backend no disponible")
            st.caption(str(exc))
            return

        st.success(f"Backend activo · {health['environment']}")

        if agent["is_simulated"]:
            st.warning("Modo simulado")
            st.caption(
                "No hay proveedor de IA real configurado. Los resultados los produce "
                "el adaptador simulado y no deben interpretarse como evaluaciones."
            )
        else:
            st.info(f"Modelo: {agent['model']}")

        st.caption(
            f"Grafo: {agent['graph']}  \n"
            f"Motor: {'LangGraph' if agent['langgraph_available'] else 'nativo'}  \n"
            f"Presupuesto: ${agent['budget_usd']:.2f}"
        )


def main() -> None:
    sidebar_status()

    st.title("VERA ATS")
    st.caption(
        "Applicant Tracking System empresarial con agente de IA gobernado — "
        "entorno de laboratorio con datos ficticios"
    )

    st.info(
        "**Principio del sistema:** VERA propone, el backend decide. El agente no "
        "cambia estados, no envía correos y no ejecuta acciones. Produce "
        "evaluaciones con evidencia verificada y propone acciones que el motor de "
        "políticas valida antes de que ocurra nada.",
        icon="🛡️",
    )

    client = get_client()
    try:
        jobs = client.list_jobs()
        resumes = client.list_resumes()
        agent = client.agent_health()
    except ApiError as exc:
        st.error(str(exc))
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Convocatorias", len(jobs))
    col2.metric("CVs ficticios", len(resumes))
    col3.metric("Prompts versionados", len(agent["prompts"]))
    col4.metric(
        "Proveedor",
        "Simulado" if agent["is_simulated"] else agent["provider"].capitalize(),
    )

    if agent["is_simulated"]:
        st.warning(
            "**Aún no has configurado un modelo real.** Ve a la página "
            "**Configuración** para añadir tu API key de Gemini. Hasta entonces, "
            "todo funciona con el adaptador simulado.",
            icon="⚙️",
        )

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Qué puedes hacer aquí")
        st.markdown(
            """
            **Configuración** — Añade tu API key de Gemini, elige el modelo y
            configura las credenciales de Google OAuth. Los secretos se guardan
            cifrados y nunca se muestran completos.

            **Vacantes** — Consulta las bases de convocatoria ficticias y los
            criterios que VERA aplica: filtros excluyentes, pesos y umbrales.

            **Evaluación** — Ejecuta el agente sobre una combinación de vacante y
            CV, y examina la puntuación, la evidencia verificada y las acciones
            propuestas.

            **Agente** — Inspecciona el grafo, los prompts versionados y las
            capas de guardrails.
            """
        )

    with right:
        st.subheader("Piezas de prueba incluidas")
        st.markdown(
            """
            Entre los CVs ficticios hay dos diseñados para poner a prueba los
            controles del sistema:

            - **CV-007** contiene intentos de manipulación del agente (anulación
              de instrucciones, suplantación de rol, orden de envío de correo).
              Debe detectarse, registrarse como incidente y **no** alterar la
              puntuación.

            - **CV-008** incluye abundante información personal irrelevante para
              el empleo. Debe anonimizarse por completo antes de que nada llegue
              al modelo.

            Ejecútalos desde la página **Evaluación** y comprueba el resultado.
            """
        )

    st.divider()
    st.caption(
        "Todos los datos de este entorno son ficticios. Ninguna persona, empresa "
        "ni proceso descrito corresponde a la realidad."
    )


if __name__ == "__main__":
    main()
