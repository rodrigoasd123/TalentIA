"""Adaptador de envío mediante la API de Gmail.

Se usa la API oficial con OAuth 2.0, nunca SMTP. El motivo no es preferencia
técnica: SMTP obliga a guardar una contraseña reutilizable con permisos amplios
sobre la cuenta, mientras que OAuth permite un alcance mínimo (`gmail.send`, que
no concede lectura del buzón), es revocable sin tocar la contraseña y devuelve un
identificador de mensaje que sirve como prueba de envío en la auditoría.

Como el resto de integraciones, se habla por HTTP directamente en lugar de usar
el SDK: menos dependencias que auditar y control total sobre timeouts y sobre qué
se registra.

**El agente no puede invocar este adaptador.** Solo lo usa el servicio de correo,
después de que el motor de políticas haya autorizado el envío.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage

import httpx

from app.core.exceptions import EmailError, GmailNotConfigured
from app.core.logging import get_logger

logger = get_logger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

#: Alcance mínimo imprescindible. Pedir más amplía el daño posible si la
#: credencial se ve comprometida, sin aportar nada al caso de uso.
SCOPES = ("https://www.googleapis.com/auth/gmail.send",)


@dataclass(slots=True)
class GmailCredentials:
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    sender_email: str = ""
    redirect_uri: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(
            self.client_id and self.client_secret and self.refresh_token and self.sender_email
        )

    @property
    def can_start_oauth(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


class GmailEmailAdapter:
    """Implementación de ``EmailPort`` sobre la API de Gmail."""

    provider = "gmail"

    def __init__(self, credentials: GmailCredentials, *, timeout: int = 30) -> None:
        self.credentials = credentials
        self.timeout = timeout
        self._access_token: str | None = None

    @property
    def is_configured(self) -> bool:
        return self.credentials.is_complete

    # ── Autorización ─────────────────────────────────────────────────────────

    def authorization_url(self, state: str = "") -> str:
        """URL a la que dirigir al usuario para autorizar la aplicación.

        ``access_type=offline`` y ``prompt=consent`` son necesarios para obtener
        un refresh token: sin ellos Google devuelve solo un token de acceso, que
        caduca en una hora y deja la integración inservible al poco rato.
        """
        if not self.credentials.can_start_oauth:
            raise GmailNotConfigured(
                "Faltan el Client ID, el Client Secret o la URI de redirección"
            )
        from urllib.parse import urlencode

        params = {
            "client_id": self.credentials.client_id,
            "redirect_uri": self.credentials.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        if state:
            params["state"] = state
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> str:
        """Canjea el código de autorización por un refresh token."""
        if not self.credentials.can_start_oauth:
            raise GmailNotConfigured("Faltan las credenciales de cliente OAuth")

        payload = {
            "code": code,
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
            "redirect_uri": self.credentials.redirect_uri,
            "grant_type": "authorization_code",
        }
        data = self._post_token(payload)
        refresh = data.get("refresh_token", "")
        if not refresh:
            raise EmailError(
                "Google no devolvió un refresh token. Revoca el acceso de la "
                "aplicación en la cuenta y vuelve a autorizar: solo se entrega en "
                "la primera autorización de cada cuenta."
            )
        self._access_token = data.get("access_token")
        return refresh

    def _refresh_access_token(self) -> str:
        if not self.is_configured:
            raise GmailNotConfigured(
                "La integración con Gmail no está configurada. Completa las "
                "credenciales en el panel de configuración."
            )
        data = self._post_token(
            {
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "refresh_token": self.credentials.refresh_token,
                "grant_type": "refresh_token",
            }
        )
        token = data.get("access_token")
        if not token:
            raise EmailError("Google no devolvió un token de acceso")
        self._access_token = token
        return token

    def _post_token(self, payload: dict[str, str]) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(TOKEN_URL, data=payload)
        except httpx.HTTPError as exc:
            raise EmailError(
                f"No se pudo contactar con el servicio de autenticación de Google: "
                f"{type(exc).__name__}"
            ) from exc

        if response.status_code != 200:
            # El cuerpo puede contener fragmentos de la credencial, así que solo
            # se propaga el código de error normalizado que devuelve Google.
            try:
                detail = response.json().get("error", "")
            except ValueError:
                detail = ""
            raise EmailError(
                f"Google rechazó la petición de token (HTTP {response.status_code}"
                + (f", {detail}" if detail else "")
                + ")"
            )
        return response.json()

    # ── Envío ────────────────────────────────────────────────────────────────

    def send(
        self, *, to: str, subject: str, body: str, idempotency_key: str = ""
    ) -> dict[str, str]:
        """Envía un mensaje y devuelve los identificadores que asigna Gmail.

        La clave de idempotencia no se pasa a Google —su API no la admite—; la
        garantía está antes, en la restricción de unicidad de la base de datos.
        Aquí se acepta solo para poder registrarla junto al envío.
        """
        token = self._access_token or self._refresh_access_token()
        raw = self._build_message(to=to, subject=subject, body=body)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    SEND_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"raw": raw},
                )
                if response.status_code == 401:
                    # El token de acceso caduca en una hora; se renueva una vez y
                    # se reintenta antes de dar el envío por fallido.
                    token = self._refresh_access_token()
                    response = client.post(
                        SEND_URL,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json={"raw": raw},
                    )
        except httpx.HTTPError as exc:
            raise EmailError(f"Error de red al enviar por Gmail: {type(exc).__name__}") from exc

        if response.status_code not in (200, 202):
            raise EmailError(self._describe_error(response))

        data = response.json()
        logger.info(
            "Correo enviado por Gmail",
            gmail_message_id=data.get("id", ""),
            idempotency_key=idempotency_key,
        )
        return {
            "message_id": data.get("id", ""),
            "thread_id": data.get("threadId", ""),
        }

    def _build_message(self, *, to: str, subject: str, body: str) -> str:
        message = MimeMessage()
        message["To"] = to
        # El remitente es fijo por configuración. No se acepta como parámetro
        # para que ninguna petición pueda suplantar la identidad de la empresa.
        message["From"] = self.credentials.sender_email
        message["Subject"] = subject
        message.set_content(body)
        return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    @staticmethod
    def _describe_error(response: httpx.Response) -> str:
        hints = {
            400: "Petición mal formada o destinatario inválido.",
            401: "Credenciales rechazadas. Vuelve a autorizar la aplicación.",
            403: "Permiso insuficiente. Comprueba que el alcance gmail.send está concedido.",
            429: "Se superó la cuota de envío de la cuenta.",
            500: "Error interno de Google.",
            503: "Servicio temporalmente no disponible.",
        }
        return (
            f"Gmail devolvió HTTP {response.status_code}. "
            + hints.get(response.status_code, "Error no clasificado.")
        )

    def verify_credentials(self) -> tuple[bool, str]:
        """Comprueba que las credenciales sirven, sin enviar ningún correo."""
        if not self.is_configured:
            faltan = [
                nombre
                for nombre, valor in (
                    ("Client ID", self.credentials.client_id),
                    ("Client Secret", self.credentials.client_secret),
                    ("Refresh token", self.credentials.refresh_token),
                    ("Correo remitente", self.credentials.sender_email),
                )
                if not valor
            ]
            return False, "Falta configurar: " + ", ".join(faltan)
        try:
            self._refresh_access_token()
        except (EmailError, GmailNotConfigured) as exc:
            return False, str(exc)
        return True, f"Credenciales válidas. Remitente: {self.credentials.sender_email}"


class NullEmailAdapter:
    """Adaptador que registra el envío sin realizarlo.

    Es el que se usa mientras Gmail no está configurado. Permite recorrer el
    flujo completo —preparar, aprobar, «enviar», auditar— sin escribir a nadie,
    que es exactamente lo que hace falta en un laboratorio con datos ficticios.
    """

    provider = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    @property
    def is_configured(self) -> bool:
        return True

    def send(
        self, *, to: str, subject: str, body: str, idempotency_key: str = ""
    ) -> dict[str, str]:
        record = {
            "message_id": f"simulado-{len(self.sent) + 1}",
            "thread_id": f"hilo-simulado-{len(self.sent) + 1}",
            "to": to,
            "subject": subject,
        }
        self.sent.append(record)
        logger.warning(
            "Envío SIMULADO: no se ha enviado ningún correo real",
            to=to,
            subject=subject[:80],
        )
        return record

    def verify_credentials(self) -> tuple[bool, str]:
        return True, "Adaptador simulado: no se envía nada realmente."


__all__ = [
    "SCOPES", "GmailCredentials", "GmailEmailAdapter", "NullEmailAdapter",
]
