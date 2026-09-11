"""Sistema visual compartido para TalentIA.

Las páginas usan estas ayudas para mantener una interfaz sobria, consistente y
comprensible para personas no técnicas. El CSS se inyecta una sola vez por
ejecución de página y no contiene datos de usuario.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable
from pathlib import Path

import streamlit as st

APP_NAME = "TalentIA"
APP_DESCRIPTION = "ATS para equipos de Recursos Humanos"

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

ACCENTS = {
    "Azul": "#2563EB",
    "Verde": "#15803D",
    "Ambar": "#B45309",
}

TONE_CLASS = {
    "info": "ti-info",
    "success": "ti-success",
    "warning": "ti-warning",
    "danger": "ti-danger",
    "muted": "ti-muted",
}


def configure_page(title: str = APP_NAME) -> None:
    st.set_page_config(
        page_title=f"{title} · {APP_NAME}" if title != APP_NAME else APP_NAME,
        page_icon=":material/work:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def image_uri(filename: str) -> str:
    path = ASSETS / filename
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{encoded}"


def inject_css() -> None:
    density = st.session_state.get("ui_density", "Cómoda")
    accent_name = st.session_state.get("ui_accent", "Azul")
    accent = ACCENTS.get(accent_name, ACCENTS["Azul"])
    compact = density == "Compacta"
    block_padding = "1.0rem 1.4rem 2.4rem" if compact else "1.5rem 2rem 3rem"
    control_height = "2.35rem" if compact else "2.65rem"
    metric_padding = "0.7rem 0.8rem" if compact else "0.95rem 1rem"
    row_gap = "0.45rem" if compact else "0.7rem"

    st.markdown(
        f"""
        <style>
        :root {{
            --ti-ink: #0F172A;
            --ti-muted: #475569;
            --ti-subtle: #64748B;
            --ti-line: #CBD5E1;
            --ti-soft-line: #E2E8F0;
            --ti-bg: #F8FAFC;
            --ti-surface: #FFFFFF;
            --ti-primary: {accent};
            --ti-primary-soft: #DBEAFE;
            --ti-success: #15803D;
            --ti-warning: #B45309;
            --ti-danger: #B91C1C;
            --ti-radius: 8px;
            --ti-row-gap: {row_gap};
        }}

        html, body, [class*="css"] {{
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            color: var(--ti-ink);
        }}

        .stApp {{
            background: var(--ti-bg);
        }}

        .block-container {{
            max-width: 1320px;
            padding: {block_padding};
        }}

        [data-testid="stHeader"] {{
            background: rgba(248, 250, 252, 0.92);
            backdrop-filter: blur(8px);
        }}

        h1, h2, h3, h4 {{
            color: var(--ti-ink) !important;
            letter-spacing: 0 !important;
        }}

        h1 {{
            font-size: clamp(1.65rem, 2.4vw, 2.25rem) !important;
            line-height: 1.18 !important;
        }}

        h2 {{
            font-size: 1.35rem !important;
        }}

        h3 {{
            font-size: 1.08rem !important;
        }}

        p, li, label, [data-testid="stMarkdownContainer"] {{
            color: var(--ti-muted);
        }}

        a {{
            color: var(--ti-primary);
            font-weight: 650;
        }}

        [data-testid="stSidebar"] {{
            background: #0F172A;
            border-right: 1px solid #1E293B;
        }}

        [data-testid="stSidebar"] * {{
            color: #E2E8F0 !important;
        }}

        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
            color: #94A3B8 !important;
        }}

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] [data-baseweb="select"] * {{
            color: var(--ti-ink) !important;
        }}

        .ti-brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 0.25rem 0 1.1rem;
        }}

        .ti-brand-mark {{
            width: 42px;
            height: 42px;
            border-radius: var(--ti-radius);
            background: var(--ti-primary);
            color: white !important;
            display: grid;
            place-items: center;
            font-weight: 850;
            font-size: 1.05rem;
            letter-spacing: 0;
        }}

        .ti-brand-copy strong {{
            color: var(--ti-ink) !important;
            display: block;
            font-size: 1.1rem;
            line-height: 1.1;
        }}

        .ti-brand-copy span {{
            color: var(--ti-muted) !important;
            display: block;
            font-size: 0.78rem;
            margin-top: 0.18rem;
        }}

        [data-testid="stSidebar"] .ti-brand-copy strong,
        .ti-login-side .ti-brand-copy strong {{
            color: #FFFFFF !important;
        }}

        [data-testid="stSidebar"] .ti-brand-copy span,
        .ti-login-side .ti-brand-copy span {{
            color: #CBD5E1 !important;
        }}

        .ti-shell-logo {{
            max-width: 135px;
            height: auto;
            display: block;
            margin: 0.2rem 0 1rem;
        }}

        .ti-login-grid {{
            display: grid;
            grid-template-columns: minmax(280px, 440px) minmax(300px, 1fr);
            gap: 1.4rem;
            align-items: stretch;
            min-height: calc(100vh - 7rem);
        }}

        .ti-panel {{
            background: var(--ti-surface);
            border: 1px solid var(--ti-soft-line);
            border-radius: var(--ti-radius);
            padding: 1.1rem;
        }}

        .ti-login-side {{
            background: #0F172A;
            border-radius: var(--ti-radius);
            padding: 1.35rem;
            display: flex;
            min-height: 100%;
            flex-direction: column;
            justify-content: space-between;
        }}

        .ti-login-side * {{
            color: #E2E8F0 !important;
        }}

        .ti-login-side h1 {{
            color: #FFFFFF !important;
            margin-bottom: 0.45rem !important;
        }}

        .ti-login-side p {{
            color: #CBD5E1 !important;
            max-width: 760px;
        }}

        .ti-eyebrow {{
            color: var(--ti-primary);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }}

        .ti-page-head {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
            margin: 0 0 1rem;
        }}

        .ti-page-head p {{
            margin: 0.15rem 0 0;
            max-width: 850px;
        }}

        .ti-section-label {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 800;
            color: var(--ti-subtle);
            margin: 1.1rem 0 0.45rem;
        }}

        .ti-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: var(--ti-row-gap);
            margin: 0.6rem 0 1rem;
        }}

        .ti-kpi {{
            background: var(--ti-surface);
            border: 1px solid var(--ti-soft-line);
            border-radius: var(--ti-radius);
            padding: {metric_padding};
            min-height: 86px;
        }}

        .ti-kpi span {{
            display: block;
            color: var(--ti-subtle);
            font-size: 0.76rem;
            font-weight: 750;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .ti-kpi strong {{
            display: block;
            margin-top: 0.25rem;
            color: var(--ti-ink);
            font-size: 1.65rem;
            line-height: 1.05;
        }}

        .ti-kpi small {{
            display: block;
            margin-top: 0.35rem;
            color: var(--ti-muted);
            line-height: 1.35;
        }}

        .ti-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            border: 1px solid var(--ti-line);
            background: white;
            color: var(--ti-muted);
            padding: 0.2rem 0.55rem;
            font-size: 0.78rem;
            font-weight: 750;
            white-space: nowrap;
            margin: 0.08rem 0.2rem 0.08rem 0;
        }}

        .ti-success {{
            color: #166534 !important;
            background: #F0FDF4 !important;
            border-color: #BBF7D0 !important;
        }}

        .ti-warning {{
            color: #92400E !important;
            background: #FFFBEB !important;
            border-color: #FDE68A !important;
        }}

        .ti-danger {{
            color: #991B1B !important;
            background: #FEF2F2 !important;
            border-color: #FECACA !important;
        }}

        .ti-info {{
            color: #1D4ED8 !important;
            background: #EFF6FF !important;
            border-color: #BFDBFE !important;
        }}

        .ti-muted {{
            color: #475569 !important;
            background: #F8FAFC !important;
            border-color: #E2E8F0 !important;
        }}

        .ti-stepper {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 0.45rem;
            margin: 0.5rem 0 1rem;
        }}

        .ti-step {{
            background: #FFFFFF;
            border: 1px solid var(--ti-soft-line);
            border-radius: var(--ti-radius);
            padding: 0.55rem 0.7rem;
            min-height: 52px;
        }}

        .ti-step strong {{
            color: var(--ti-ink);
            font-size: 0.82rem;
        }}

        .ti-step span {{
            color: var(--ti-muted);
            display: block;
            font-size: 0.76rem;
            margin-top: 0.12rem;
        }}

        .ti-step-active {{
            border-color: var(--ti-primary);
            background: #EFF6FF;
        }}

        .ti-empty {{
            border: 1px dashed var(--ti-line);
            background: #FFFFFF;
            border-radius: var(--ti-radius);
            padding: 1rem;
        }}

        div.stButton > button,
        div.stDownloadButton > button,
        button[kind="primary"],
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] {{
            min-height: {control_height};
            border-radius: var(--ti-radius) !important;
            font-weight: 750 !important;
            opacity: 1 !important;
        }}

        div.stButton > button[kind="primary"],
        [data-testid="baseButton-primary"] {{
            background: var(--ti-primary) !important;
            color: white !important;
            border: 1px solid var(--ti-primary) !important;
        }}

        div.stButton > button,
        div.stDownloadButton > button,
        [data-testid="baseButton-secondary"] {{
            background: #FFFFFF !important;
            color: var(--ti-ink) !important;
            border: 1px solid var(--ti-line) !important;
        }}

        div.stButton > button:disabled,
        div.stDownloadButton > button:disabled {{
            background: #E2E8F0 !important;
            color: #64748B !important;
            border-color: #CBD5E1 !important;
        }}

        div.stButton > button:focus,
        div.stDownloadButton > button:focus,
        input:focus,
        textarea:focus,
        [data-baseweb="select"] div:focus {{
            outline: 3px solid #93C5FD !important;
            outline-offset: 2px !important;
            box-shadow: none !important;
        }}

        [data-testid="stMetric"] {{
            background: #FFFFFF;
            border: 1px solid var(--ti-soft-line);
            border-radius: var(--ti-radius);
            padding: 0.65rem 0.75rem;
        }}

        [data-testid="stMetricLabel"] p {{
            color: var(--ti-subtle) !important;
            font-weight: 750 !important;
        }}

        [data-testid="stMetricValue"] div {{
            color: var(--ti-ink) !important;
            font-size: 1.55rem !important;
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--ti-soft-line);
            border-radius: var(--ti-radius);
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.35rem;
            border-bottom: 1px solid var(--ti-soft-line);
        }}

        .stTabs [data-baseweb="tab"] p {{
            font-weight: 750 !important;
            color: var(--ti-muted) !important;
        }}

        .stTabs [aria-selected="true"] p {{
            color: var(--ti-primary) !important;
        }}

        @media (prefers-reduced-motion: reduce) {{
            * {{
                transition: none !important;
                animation: none !important;
            }}
        }}

        @media (max-width: 860px) {{
            .block-container {{
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }}

            .ti-login-grid {{
                grid-template-columns: 1fr;
                min-height: auto;
            }}

            .ti-page-head {{
                display: block;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand_html(subtitle: str = APP_DESCRIPTION) -> str:
    return (
        '<div class="ti-brand">'
        '<div class="ti-brand-mark">TIA</div>'
        '<div class="ti-brand-copy">'
        f"<strong>{APP_NAME}</strong><span>{subtitle}</span>"
        "</div></div>"
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown(brand_html(), unsafe_allow_html=True)
    logo = image_uri("tcs-logo-light.jpeg")
    if logo:
        st.sidebar.markdown(
            f'<img class="ti-shell-logo" src="{logo}" alt="Tata Consultancy Services">',
            unsafe_allow_html=True,
        )


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    st.markdown(
        '<div class="ti-page-head"><div>'
        + (f'<div class="ti-eyebrow">{eyebrow}</div>' if eyebrow else "")
        + f"<h1>{title}</h1>"
        + (f"<p>{subtitle}</p>" if subtitle else "")
        + "</div></div>",
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(f'<div class="ti-section-label">{text}</div>', unsafe_allow_html=True)


def badge(label: str, tone: str = "muted") -> str:
    css = TONE_CLASS.get(tone, "ti-muted")
    return f'<span class="ti-badge {css}">{label}</span>'


def badge_row(items: Iterable[tuple[str, str]]) -> None:
    st.markdown(" ".join(badge(label, tone) for label, tone in items), unsafe_allow_html=True)


def metric_grid(items: Iterable[tuple[str, str, str]]) -> None:
    html = ['<div class="ti-kpi-grid">']
    for label, value, help_text in items:
        html.append(
            '<div class="ti-kpi">'
            f"<span>{label}</span><strong>{value}</strong>"
            + (f"<small>{help_text}</small>" if help_text else "")
            + "</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f'<div class="ti-empty"><strong>{title}</strong><br><span>{body}</span></div>',
        unsafe_allow_html=True,
    )


def progress_steps(steps: list[str], current: int) -> None:
    html = ['<div class="ti-stepper">']
    for index, label in enumerate(steps, start=1):
        active = " ti-step-active" if index == current else ""
        html.append(
            f'<div class="ti-step{active}"><strong>Paso {index}</strong><span>{label}</span></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def api_error(exc: Exception, context: str = "") -> None:
    message = str(exc)
    status_code = getattr(exc, "status_code", 0)
    if status_code == 401:
        message = "Tu sesión no está activa o expiró. Vuelve a iniciar sesión."
    elif status_code == 403:
        message = "Tu rol no tiene permiso para esta acción."
    elif status_code == 422:
        message = "Revisa los datos ingresados. Hay un campo inválido o incompleto."
    elif not message:
        message = "No se pudo completar la operación."
    st.error(f"{context + ': ' if context else ''}{message}")
