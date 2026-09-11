"""Análisis documental integrado en TalentIA mediante la API."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_client import ApiError  # noqa: E402
from talentia import design, session  # noqa: E402


def render() -> None:  # noqa: C901
    if not session.require_permission("candidate:pii:read"):
        return
    design.page_header(
        "Análisis documental",
        "Compara CV con un perfil y consulta evidencia sin salir de TalentIA.",
        "Expediente",
    )
    st.info(
        "El resultado prioriza revisión documental. No aprueba, rechaza ni reemplaza "
        "la decisión humana."
    )
    profile = st.file_uploader("Perfil del puesto en PDF", type=["pdf"], key="doc_profile")
    cvs = st.file_uploader(
        "CV en PDF (máximo 25)", type=["pdf"], accept_multiple_files=True, key="doc_cvs"
    )
    mode_label = st.radio(
        "Método de lectura", ["Texto seleccionable", "OCR local"], horizontal=True
    )
    mode = "ocr" if mode_label == "OCR local" else "normal"
    if st.button("Analizar documentos", type="primary", disabled=not profile or not cvs):
        try:
            result = session.client().screen_documents(
                profile=(profile.name, profile.getvalue()),
                cvs=[(item.name, item.getvalue()) for item in cvs[:25]],
                mode=mode,
            )
            st.session_state["document_analysis_result"] = result
        except ApiError as exc:
            design.api_error(exc, "No se pudo completar el análisis documental")

    result = st.session_state.get("document_analysis_result")
    if not result:
        return
    criteria_tab, ranking_tab, query_tab = st.tabs(["Criterios", "Ranking", "Consulta RAG"])
    with criteria_tab:
        excluded = result.get("excluded_sensitive", [])
        if excluded:
            st.warning(
                f"Se excluyeron {len(excluded)} criterios sensibles del puntaje."
            )
        st.dataframe(
            [{"ID": row["id"], "Criterio": row["text"], "Página": row["page"]}
             for row in result.get("criteria", [])],
            width="stretch", hide_index=True,
        )
    with ranking_tab:
        ranking = result.get("ranking", [])
        st.dataframe(
            [{"CV": row["filename"], "Coincidencia documental": row["score"]}
             for row in ranking],
            width="stretch", hide_index=True,
        )
        for row in ranking:
            with st.expander(f"{row['filename']} · {row['score']} puntos"):
                st.dataframe(
                    [{
                        "Criterio": match["criterion"], "Estado": match["status"],
                        "Cobertura": f"{match['coverage']:.0%}",
                        "Evidencia": (match.get("evidence") or {}).get("text", ""),
                    } for match in row.get("matches", [])],
                    width="stretch", hide_index=True,
                )
        if result.get("errors"):
            st.warning(result["errors"])
    with query_tab:
        if not profile or not cvs:
            st.caption("Mantén los archivos cargados para consultar evidencia.")
            return
        names = [item.name for item in cvs[:25]]
        selected = st.selectbox("CV para consultar", names)
        question = st.text_input("Pregunta sobre el perfil y el CV")
        if st.button("Buscar evidencia", disabled=len(question.strip()) < 2):
            chosen = next(item for item in cvs if item.name == selected)
            try:
                answer = session.client().query_documents(
                    profile=(profile.name, profile.getvalue()),
                    cv=(chosen.name, chosen.getvalue()), question=question, mode=mode,
                )
                st.write(answer["answer"])
                for evidence in answer.get("evidence", []):
                    st.caption(f"Página {evidence['page']}: {evidence['text']}")
            except ApiError as exc:
                design.api_error(exc, "No se pudo consultar la evidencia")


render()
