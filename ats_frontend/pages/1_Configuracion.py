"""Panel de configuración.

Aquí se introducen la API key del proveedor de IA y las credenciales de Google
OAuth. Tres garantías que la interfaz refleja de forma explícita:

* Los secretos se guardan **cifrados** y nunca se muestran completos.
* Dejar un campo de secreto en blanco **conserva** el valor guardado, no lo borra.
* Las opciones irreversibles (rechazo automático, envío de correo) están
  desactivadas por defecto y avisan de lo que implican al activarse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_client import ApiError, DEFAULT_BASE_URL, VeraApiClient  # noqa: E402

st.set_page_config(page_title="Configuración · VERA ATS", page_icon="⚙️", layout="wide")


def get_client() -> VeraApiClient:
    return VeraApiClient(st.session_state.get("api_base_url", DEFAULT_BASE_URL))


client = get_client()

st.title("⚙️ Configuración")
st.caption(
    "Configuración editable en caliente. Los valores sensibles se cifran antes de "
    "guardarse y no aparecen en los registros del sistema."
)

try:
    current = client.get_settings()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

by_key = {item["key"]: item for item in current["settings"]}


def value_of(key: str, default: str = "") -> str:
    item = by_key.get(key)
    return item["value"] if item and not item["is_secret"] else default


def is_set(key: str) -> bool:
    item = by_key.get(key)
    return bool(item and item["is_set"])


def masked(key: str) -> str:
    item = by_key.get(key)
    return item["value"] if item else ""


def flag_of(key: str) -> bool:
    return value_of(key, "false").strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


# ── Estado actual ────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)
col1.metric("Proveedor", current["provider"])
col2.metric("Modelo", current["model"])
col3.metric("Estado", "Listo" if current["llm_ready"] else "Sin configurar")

if current["is_simulated"]:
    st.warning(
        "El sistema está usando el **adaptador simulado**. Funciona de extremo a "
        "extremo, pero las evaluaciones no proceden de un modelo real y no deben "
        "interpretarse como tales.",
        icon="🧪",
    )

st.divider()

tab_ia, tab_google, tab_flags = st.tabs(
    ["🤖 Proveedor de IA", "📧 Google / Gmail", "🚩 Comportamiento del sistema"]
)


# ── Proveedor de IA ──────────────────────────────────────────────────────────

with tab_ia:
    st.subheader("Proveedor de modelo de lenguaje")

    provider = st.selectbox(
        "Proveedor",
        options=["gemini", "mock"],
        index=0 if value_of("llm.provider", "mock") == "gemini" else 1,
        format_func=lambda p: {
            "gemini": "Google Gemini (API real)",
            "mock": "Simulador local (sin credenciales)",
        }[p],
        help="El simulador permite recorrer todo el sistema sin gastar cuota.",
    )

    st.markdown("#### API key")
    if is_set("llm.api_key"):
        st.success(f"Hay una clave guardada: `{masked('llm.api_key')}`", icon="🔐")
        st.caption(
            "Deja el campo en blanco para conservarla. Escribe una nueva solo si "
            "quieres reemplazarla."
        )
    else:
        st.info("No hay ninguna API key configurada todavía.", icon="🔑")

    api_key = st.text_input(
        "API key de Gemini",
        type="password",
        value="",
        placeholder="AIza..." if provider == "gemini" else "no necesaria en modo simulado",
        help=(
            "Se obtiene en Google AI Studio. Se guarda cifrada con una clave derivada "
            "de VERA_SECRET_KEY y nunca se muestra completa ni se escribe en los logs."
        ),
        disabled=provider == "mock",
    )

    st.markdown("#### Modelo")
    known_models = [
        "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite",
        "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro",
    ]
    if st.button("🔄 Consultar modelos disponibles para mi clave", disabled=provider == "mock"):
        try:
            fetched = client.list_models()
            if fetched:
                st.session_state["available_models"] = fetched
                st.success(f"Se encontraron {len(fetched)} modelos disponibles.")
        except ApiError as exc:
            st.error(str(exc))

    options = st.session_state.get("available_models", known_models)
    saved_model = value_of("llm.model", "gemini-2.5-flash")
    if saved_model not in options:
        options = [saved_model, *options]

    model = st.selectbox(
        "Modelo a utilizar",
        options=options,
        index=options.index(saved_model) if saved_model in options else 0,
        help=(
            "Fija una versión concreta. Evita los alias móviles del proveedor: si el "
            "modelo cambia bajo el mismo nombre, las evaluaciones dejan de ser "
            "comparables entre sí."
        ),
        disabled=provider == "mock",
    )

    c1, c2 = st.columns(2)
    with c1:
        temperature = st.slider(
            "Temperatura",
            min_value=0.0, max_value=1.0, step=0.05,
            value=float(value_of("llm.temperature", "0.1") or 0.1),
            help=(
                "Valores bajos producen resultados más reproducibles. Por encima de "
                "0.3 la misma candidatura puede recibir puntuaciones distintas en "
                "ejecuciones sucesivas, lo que complica defender una decisión."
            ),
        )
        if temperature > 0.3:
            st.warning(
                "Una temperatura alta reduce la reproducibilidad de las evaluaciones.",
                icon="⚠️",
            )
    with c2:
        budget = st.number_input(
            "Presupuesto por vacante (USD)",
            min_value=0.0, max_value=1000.0, step=0.5,
            value=float(value_of("llm.budget_usd_per_job", "5.0") or 5.0),
            help=(
                "Al agotarse, las evaluaciones pendientes pasan a revisión humana en "
                "lugar de completarse con calidad degradada."
            ),
        )

    bias_audit = st.toggle(
        "Auditoría de sesgo con un segundo modelo",
        value=flag_of("llm.enable_bias_audit") or value_of("llm.enable_bias_audit", "true") == "true",
        help=(
            "Añade una llamada adicional por evaluación. La capa léxica "
            "determinística se aplica siempre, esté activada o no esta opción."
        ),
    )

    st.divider()
    b1, b2 = st.columns([1, 1])

    with b1:
        if st.button("🔍 Probar credenciales", use_container_width=True):
            with st.spinner("Verificando con el proveedor…"):
                try:
                    result = client.test_credentials(
                        provider=provider, api_key=api_key, model=model
                    )
                    if result["ok"]:
                        st.success(result["message"], icon="✅")
                        if result["available_models"]:
                            st.session_state["available_models"] = result["available_models"]
                    else:
                        st.error(result["message"], icon="❌")
                except ApiError as exc:
                    st.error(str(exc))

    with b2:
        if st.button("💾 Guardar configuración de IA", type="primary", use_container_width=True):
            values = {
                "llm.provider": provider,
                "llm.model": model,
                "llm.temperature": str(temperature),
                "llm.budget_usd_per_job": str(budget),
                "llm.enable_bias_audit": "true" if bias_audit else "false",
            }
            # Solo se envía la clave si el usuario escribió una nueva: enviar una
            # cadena vacía borraría la guardada.
            if api_key.strip():
                values["llm.api_key"] = api_key.strip()
            try:
                client.update_settings(values)
                st.success("Configuración guardada.", icon="✅")
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))


# ── Google / Gmail ───────────────────────────────────────────────────────────

with tab_google:
    st.subheader("Credenciales de Google OAuth 2.0")
    st.caption(
        "VERA envía correo mediante la **API oficial de Gmail**, nunca por SMTP. "
        "Las credenciales se guardan cifradas y no se envían al modelo."
    )

    with st.expander("Cómo obtener estas credenciales", expanded=not is_set("google.client_id")):
        st.markdown(
            """
            1. Entra en la consola de Google Cloud y crea o selecciona un proyecto.
            2. Habilita la **Gmail API** en la biblioteca de APIs.
            3. Configura la pantalla de consentimiento OAuth.
            4. En **Credenciales**, crea un **ID de cliente de OAuth 2.0** de tipo
               *Aplicación web*.
            5. Añade la URI de redirección exactamente como la indiques abajo.
            6. Copia aquí el *Client ID* y el *Client Secret*.

            **Sobre el ámbito de permisos:** solicita únicamente
            `gmail.send`. Es el mínimo necesario para enviar y no concede acceso de
            lectura al buzón. Pedir más permisos de los necesarios amplía el daño
            posible si la credencial se ve comprometida.

            **Nota sobre cuentas personales:** una cuenta `@gmail.com` funciona con
            OAuth igual que una de Workspace, pero los límites de envío y el proceso
            de verificación de la aplicación son distintos. Para un laboratorio es
            suficiente; antes de producción conviene revisar ambos puntos.
            """
        )

    g1, g2 = st.columns(2)

    with g1:
        client_id = st.text_input(
            "Client ID",
            value=value_of("google.client_id"),
            placeholder="123456789-abc.apps.googleusercontent.com",
        )
        redirect_uri = st.text_input(
            "URI de redirección",
            value=value_of(
                "google.redirect_uri",
                "http://localhost:8000/api/v1/auth/google/callback",
            ),
            help="Debe coincidir carácter a carácter con la registrada en Google Cloud.",
        )

    with g2:
        if is_set("google.client_secret"):
            st.success(f"Secreto guardado: `{masked('google.client_secret')}`", icon="🔐")
        client_secret = st.text_input(
            "Client Secret",
            type="password",
            value="",
            placeholder="Déjalo en blanco para conservar el actual",
        )
        sender_email = st.text_input(
            "Correo remitente",
            value=value_of("google.sender_email"),
            placeholder="tu-cuenta@gmail.com",
            help=(
                "Cuenta desde la que se enviarán las comunicaciones. Es fija por "
                "configuración: ninguna petición puede alterar el remitente."
            ),
        )

    st.info(
        "**El agente no puede enviar correo.** Aunque estas credenciales estén "
        "configuradas, VERA solo puede *preparar* un borrador a partir de una "
        "plantilla aprobada. El envío lo realiza el backend, tras validar el "
        "destinatario contra el correo registrado del candidato, comprobar la "
        "idempotencia y, en las categorías sensibles, exigir aprobación humana.",
        icon="🛡️",
    )

    if st.button("💾 Guardar credenciales de Google", type="primary"):
        values = {
            "google.client_id": client_id.strip(),
            "google.redirect_uri": redirect_uri.strip(),
            "google.sender_email": sender_email.strip(),
        }
        if client_secret.strip():
            values["google.client_secret"] = client_secret.strip()
        try:
            client.update_settings(values)
            st.success("Credenciales guardadas y cifradas.", icon="✅")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))


# ── Feature flags ────────────────────────────────────────────────────────────

with tab_flags:
    st.subheader("Comportamiento del sistema")
    st.caption(
        "Todo lo irreversible arranca desactivado. Activarlo es una decisión "
        "consciente, no un valor por defecto."
    )

    dry_run = st.toggle(
        "Modo simulación (dry run)",
        value=flag_of("ff.dry_run") or value_of("ff.dry_run", "true") == "true",
        help=(
            "Ejecuta el pipeline completo sin persistir decisiones ni enviar nada. "
            "Es el modo recomendado mientras se calibran los criterios de una vacante."
        ),
    )

    st.divider()

    auto_shortlist = st.toggle(
        "Preselección automática",
        value=flag_of("ff.ai_auto_shortlist"),
        help="Permite que una candidatura avance a preseleccionada sin revisión humana.",
    )
    if auto_shortlist:
        st.info(
            "La preselección es reversible: si el sistema se equivoca, el recruiter "
            "puede corregirlo sin consecuencias para la persona.",
            icon="ℹ️",
        )

    auto_rejection = st.toggle(
        "Rechazo automático",
        value=flag_of("ff.ai_auto_rejection"),
        help="Permite descartar candidaturas sin intervención humana.",
    )
    if auto_rejection:
        st.error(
            "**Un rechazo es irreversible y afecta a una persona.** Con esta opción "
            "activa, candidaturas que no superen los filtros podrán descartarse sin "
            "que nadie las revise. Antes de activarla en un proceso real conviene "
            "validar con el equipo jurídico que existe una vía de revisión y que la "
            "decisión queda debidamente motivada.",
            icon="⚠️",
        )

    auto_email = st.toggle(
        "Envío automático de correos",
        value=flag_of("ff.auto_email"),
        help="Permite que el sistema envíe comunicaciones sin aprobación previa.",
    )
    if auto_email:
        st.warning(
            "Las categorías sensibles (rechazo, invitación a entrevista, cierre de "
            "proceso) **seguirán exigiendo aprobación humana** con independencia de "
            "esta opción. Es una regla del motor de políticas, no una preferencia.",
            icon="⚠️",
        )

    if st.button("💾 Guardar comportamiento", type="primary"):
        try:
            client.update_settings(
                {
                    "ff.dry_run": "true" if dry_run else "false",
                    "ff.ai_auto_shortlist": "true" if auto_shortlist else "false",
                    "ff.ai_auto_rejection": "true" if auto_rejection else "false",
                    "ff.auto_email": "true" if auto_email else "false",
                }
            )
            st.success("Configuración guardada.", icon="✅")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))


# ── Detalle técnico ──────────────────────────────────────────────────────────

st.divider()
with st.expander("Ver todas las claves de configuración"):
    st.caption(
        "Vista completa tal como la devuelve la API. Los secretos aparecen "
        "enmascarados: no existe ningún endpoint que los devuelva en claro."
    )
    st.dataframe(
        [
            {
                "Clave": item["key"],
                "Grupo": item["group"],
                "Valor": item["value"],
                "Secreto": "Sí" if item["is_secret"] else "No",
                "Establecido": "Sí" if item["is_set"] else "No",
                "Modificado": (item["updated_at"] or "")[:19],
            }
            for item in current["settings"]
        ],
        use_container_width=True,
        hide_index=True,
    )
