from __future__ import annotations

import hashlib

import streamlit as st

from agente_postulacion import ApplicationAgent
from agente_postulacion.history import QueryHistory
from agente_postulacion.models import Evidence
from agente_postulacion.pdf_reader import PdfReadError, read_pdf

st.set_page_config(page_title="TalentIA", page_icon="📄", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');

    :root { --navy:#10233f; --blue:#1e66f5; --cyan:#43c7d5; --ink:#0f172a; --muted:#475569; --line:#e2e8f0; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
    
    /* General Text & Headings Contrast */
    h1, h2, h3, h4, h5, h6 { font-family:'Manrope',sans-serif !important; letter-spacing:-.025em; color:#10233f !important; }
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color: #1e293b !important; }
    
    .stApp { background:linear-gradient(180deg,#f8fafc 0,#ffffff 48%); }
    .block-container { max-width:1180px; padding-top:2.2rem; padding-bottom:4rem; }
    [data-testid="stHeader"] { background:transparent; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] { background:#0f213b; border-right:0; }
    [data-testid="stSidebar"] * { color:#f6f8fc !important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#aebbd0 !important; }
    [data-testid="stSidebar"] hr { border-color:#2a405e; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background:#172e4d; border:1px dashed #5c7ba6; border-radius:14px;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background:#fff; color:#10233f !important; border:0; border-radius:9px; font-weight:700;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * { color:#10233f !important; }
    
    .brand { display:flex; align-items:center; gap:11px; margin:4px 0 30px; }
    .brand-mark { width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#2c72ff,#43c7d5);display:grid;place-items:center;font-size:21px;box-shadow:0 8px 22px rgba(30,102,245,.28);color:#ffffff!important; }
    .brand-name { font-family:'Manrope',sans-serif;font-weight:800;font-size:20px;letter-spacing:-.03em;color:#ffffff!important; }
    .brand-name span { color:#76dbe5!important; }
    .side-label { color:#88a0c1!important;text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:700;margin-bottom:7px; }
    .prompt-chip { border:1px solid #304865;border-radius:10px;padding:9px 11px;margin:7px 0;color:#d8e2f0!important;font-size:13px;line-height:1.35; }
    
    /* Hero Banner */
    .hero { position:relative;overflow:hidden;background:linear-gradient(125deg,#10233f 0%,#18395f 64%,#166978 100%);border-radius:26px;padding:52px 54px;color:white!important;box-shadow:0 22px 55px rgba(16,35,63,.16); }
    .hero * { color:white!important; }
    .hero:after { content:'';position:absolute;width:320px;height:320px;border:1px solid rgba(255,255,255,.13);border-radius:50%;right:-80px;top:-130px;box-shadow:0 0 0 55px rgba(255,255,255,.035),0 0 0 110px rgba(255,255,255,.025); }
    .eyebrow { display:inline-flex;align-items:center;gap:8px;color:#8de8ef!important;font-size:12px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;margin-bottom:17px; }
    .hero h1 { color:white!important;font-size:48px!important;line-height:1.06;margin:0 0 16px!important;max-width:720px; }
    .hero p { color:#d3deed!important;font-size:18px;line-height:1.6;max-width:690px;margin:0; }
    .trust-row { display:flex;gap:22px;flex-wrap:wrap;margin-top:27px;color:#dce7f5!important;font-size:13px;font-weight:600; }
    .trust-row span:before { content:'✓';color:#70e0cb;margin-right:7px; }
    
    .section-head { margin:34px 0 15px; }
    .section-head h2 { font-size:28px;margin:0 0 5px;color:#10233f!important; }
    .section-head p { color:var(--muted)!important;margin:0; }
    
    .feature-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:10px 0 24px; }
    .feature-card { background:#fff;border:1px solid var(--line);border-radius:17px;padding:22px;box-shadow:0 8px 25px rgba(22,40,72,.055); }
    .feature-icon { width:42px;height:42px;border-radius:12px;background:#edf4ff;display:grid;place-items:center;font-size:20px;margin-bottom:16px;color:#1e66f5!important; }
    .feature-card h3 { font-size:17px;margin:0 0 7px;color:#10233f!important; }
    .feature-card p { color:var(--muted)!important;font-size:14px;line-height:1.5;margin:0; }
    
    .upload-callout { display:flex;align-items:center;justify-content:space-between;gap:24px;background:#edf5ff;border:1px solid #d7e7ff;border-radius:16px;padding:18px 22px;margin-top:18px; }
    .upload-callout strong { color:#164caa!important;display:block;margin-bottom:3px; }
    .upload-callout span { color:#5a6f8e!important;font-size:14px; }
    .privacy { display:flex;gap:11px;align-items:flex-start;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:14px;padding:14px 16px;color:#166534!important;font-size:14px;margin:18px 0; }
    .privacy strong { color:#14532d!important; }
    .privacy div { color:#166534!important; }
    
    /* Metrics High Contrast */
    [data-testid="stMetric"] { background:#ffffff !important; border:1px solid #cbd5e1 !important; border-radius:16px; padding:17px 19px; box-shadow:0 6px 20px rgba(22,40,72,.06) !important; }
    [data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] span { color:#475569 !important; font-weight:700 !important; font-size: 14px !important; }
    [data-testid="stMetricValue"] div, [data-testid="stMetricValue"] span { color:#10233f !important; font-size: 32px !important; font-weight: 800 !important; }
    
    /* Tabs & Cards Styling */
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:8px; border-bottom:2px solid #e2e8f0; }
    [data-testid="stTabs"] button p { font-weight:700 !important; font-size: 15px !important; color: #475569 !important; }
    [data-testid="stTabs"] button[aria-selected="true"] p { color: #1e66f5 !important; font-weight: 800 !important; }
    
    [data-testid="stChatMessage"] { background:#fff; border:1px solid var(--line); border-radius:15px; padding:14px; }
    .result-block { background:white; border:1px solid var(--line); border-radius:14px; padding:15px 17px; margin:8px 0 12px; box-shadow:0 4px 16px rgba(22,40,72,.04); }
    @media(max-width:800px){.hero{padding:34px 27px}.hero h1{font-size:37px!important}.feature-grid{grid-template-columns:1fr}.block-container{padding-top:1rem}.upload-callout{display:block}}
    </style>
    """,
    unsafe_allow_html=True,
)


def render_items(title: str, icon: str, items: list[Evidence], empty: str) -> None:
    st.markdown(f"### {icon} {title}")
    if not items:
        st.caption(empty)
        return
    for item in items:
        with st.container(border=True):
            st.markdown(item.text)
            st.caption(f"Fuente: página {item.page}")


@st.cache_resource(show_spinner=False)
def history() -> QueryHistory:
    return QueryHistory()


with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">◆</div><div class="brand-name">Postula<span>IA</span></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="side-label">Documento de análisis</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Carga una convocatoria en PDF", type=["pdf"], label_visibility="collapsed")
    use_ollama = st.toggle("Respuestas con Ollama local", value=False)
    st.caption("Opcional, privado y gratuito · llama3.2:3b")
    st.divider()
    st.markdown('<div class="side-label">Preguntas sugeridas</div>', unsafe_allow_html=True)
    for suggestion in (
        "¿Cuáles son los requisitos obligatorios?",
        "¿Cuál es la fecha límite?",
        "¿Hay condiciones desfavorables?",
        "¿Qué documentos debo presentar?",
    ):
        st.markdown(f'<div class="prompt-chip">{suggestion}</div>', unsafe_allow_html=True)
    st.divider()
    st.caption("🔒 El documento se procesa localmente y no se conserva.")

if not uploaded:
    st.markdown(
        """
        <section class="hero">
          <div class="eyebrow">✦ Asistente inteligente de postulación</div>
          <h1>Entiende la convocatoria antes de postular.</h1>
          <p>Convierte documentos extensos en requisitos claros, fechas críticas y respuestas respaldadas por evidencia.</p>
          <div class="trust-row"><span>Procesamiento local</span><span>Citas por página</span><span>Sin costo de API</span></div>
        </section>
        <div class="section-head"><h2>Todo lo importante, en minutos</h2><p>Una lectura guiada para tomar mejores decisiones y evitar errores de postulación.</p></div>
        <div class="feature-grid">
          <div class="feature-card"><div class="feature-icon">◎</div><h3>Resumen accionable</h3><p>Identifica el objetivo del puesto y los puntos esenciales sin leer cada página.</p></div>
          <div class="feature-card"><div class="feature-icon">◇</div><h3>Alertas y requisitos</h3><p>Separa obligaciones, fechas límite, exclusiones y condiciones contractuales.</p></div>
          <div class="feature-card"><div class="feature-icon">⌕</div><h3>Preguntas con evidencia</h3><p>Responde usando únicamente el documento y muestra la página de cada hallazgo.</p></div>
        </div>
        <div class="upload-callout"><div><strong>Comienza con una convocatoria en PDF</strong><span>Usa el panel izquierdo para cargar el documento de ejemplo o uno propio.</span></div><div>PDF · texto seleccionable · máximo 200 MB</div></div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

data = uploaded.getvalue()
document_key = hashlib.sha256(data).hexdigest()
try:
    pages = read_pdf(data)
except PdfReadError as exc:
    st.error(str(exc))
    st.stop()

if st.session_state.get("document_key") != document_key:
    st.session_state.document_key = document_key
    st.session_state.messages = []

agent = ApplicationAgent(pages, use_ollama=use_ollama)
analysis = agent.analysis

st.markdown('<div class="eyebrow" style="color:#1e66f5">✓ Documento procesado</div>', unsafe_allow_html=True)
st.title(analysis.title)
st.markdown('<div class="privacy">🛡️ <div><strong>Análisis privado</strong><br>El archivo se procesó localmente y las respuestas se apoyan en fragmentos verificables.</div></div>', unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Requisitos", len(analysis.requirements))
m2.metric("Fechas", len(analysis.dates))
m3.metric("Condiciones", len(analysis.conditions))
m4.metric("Alertas", len(analysis.alerts) + len(analysis.exclusions))

overview, chat, evidence_tab = st.tabs(["Resumen y hallazgos", "Pregúntale al agente", "Documento fuente"])
with overview:
    st.markdown("### Resumen ejecutivo")
    st.info(analysis.summary)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        render_items("Requisitos", "✓", analysis.requirements, "No se detectaron requisitos explícitos.")
        render_items("Fechas y plazos", "◷", analysis.dates, "No se detectaron fechas claras.")
    with c2:
        render_items("Condiciones", "▣", analysis.conditions, "No se detectaron condiciones contractuales.")
        render_items("Alertas y exclusiones", "⚠", analysis.alerts + analysis.exclusions, "No se detectaron alertas automáticas.")

with chat:
    st.caption("Pregunta en lenguaje natural. El agente no reemplaza una revisión legal o de recursos humanos.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if question := st.chat_input("Ejemplo: ¿Qué puede causar mi descalificación?"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Buscando evidencia en el PDF..."):
                result = agent.ask(question)
            st.markdown(result.answer)
        st.session_state.messages.append({"role": "assistant", "content": result.answer})
        history().add(uploaded.name, question, result.answer)

with evidence_tab:
    st.markdown("### Texto extraído por página")
    st.caption("Úsalo para comprobar exactamente qué información leyó el agente.")
    for page in pages:
        with st.expander(f"Página {page.page}"):
            st.text(page.text)
