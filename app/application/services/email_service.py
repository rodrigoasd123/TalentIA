"""Servicio de comunicaciones con los candidatos.

El flujo completo, y el orden importa en cada paso:

    plantilla aprobada → variables del modelo → validación → política
    → idempotencia → límite de envío → adaptador autorizado → auditoría

Cuatro garantías que el código hace cumplir:

1. **El modelo no redacta el correo.** Rellena un conjunto cerrado de variables
   dentro de una plantilla que aprobó una persona. Cualquier clave que devuelva
   fuera de esa lista se descarta.
2. **El destinatario es siempre el correo registrado del candidato.** Nunca un
   valor que provenga del CV, del modelo o de la petición.
3. **La idempotencia la garantiza la base de datos**, con una restricción de
   unicidad. Una comprobación en la aplicación puede perder una carrera entre
   dos procesos; la restricción no.
4. **Las categorías sensibles exigen aprobación humana** con independencia de la
   configuración. Es una regla del motor de políticas, no una preferencia.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.ai.prompts.registry import get_prompt_registry
from app.ai.policies.policy_engine import PolicyContext, PolicyEngine
from app.ai.schemas import EmailDraftOutput, schema_hint
from app.application.services.audit_service import Actor, AuditService
from app.application.unit_of_work import UnitOfWork
from app.core.exceptions import (
    ApplicationNotFound,
    EmailAlreadySent,
    HumanApprovalRequired,
    NotFoundError,
    PolicyDenied,
    ValidationError,
)
from app.core.logging import get_logger
from app.domain.entities import EmailMessage, EmailTemplate
from app.domain.enums import (
    SENSITIVE_EMAIL_KINDS,
    ActionType,
    EmailStatus,
    EmailTemplateKind,
    Permission,
    Severity,
)
from app.infrastructure.email.gmail_adapter import (
    GmailCredentials,
    GmailEmailAdapter,
    NullEmailAdapter,
)

logger = get_logger(__name__)

#: Límite de envíos por vacante y hora. Un error de lógica que dispare correos en
#: bucle es un incidente reputacional inmediato e irreversible.
DEFAULT_RATE_LIMIT_PER_HOUR = 50

#: Marcadores de plantilla admitidos: solo letras, dígitos y guion bajo. Cualquier
#: otra cosa se ignora, lo que impide construir marcadores dinámicos.
_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]{0,40})\}")


@dataclass(slots=True)
class PreparedEmail:
    message: EmailMessage
    template: EmailTemplate
    requires_approval: bool
    policy_reason: str = ""
    generated_variables: dict[str, str] | None = None


class EmailService:
    def __init__(self, uow: UnitOfWork, *, llm=None) -> None:  # noqa: ANN001
        self.uow = uow
        self.audit = AuditService(uow.audit)
        self.policy = PolicyEngine()
        self._llm = llm

    # ── Adaptador de envío ───────────────────────────────────────────────────

    def _adapter(self):  # noqa: ANN202
        """Gmail si está configurado; en caso contrario, el simulado.

        Degradar a simulado en lugar de fallar permite recorrer el flujo entero
        en el laboratorio. La interfaz avisa de forma visible de que no se está
        enviando nada.
        """
        config = self.uow.settings.google_config()
        credentials = GmailCredentials(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            refresh_token=config["refresh_token"],
            sender_email=config["sender_email"],
            redirect_uri=config["redirect_uri"],
        )
        if credentials.is_complete:
            return GmailEmailAdapter(credentials)
        return NullEmailAdapter()

    # ── Preparación ──────────────────────────────────────────────────────────

    def prepare(
        self,
        *,
        application_id: str,
        template_code: str,
        actor: Actor,
        use_ai: bool = True,
        extra_context: dict[str, Any] | None = None,
    ) -> PreparedEmail:
        """Construye un borrador a partir de una plantilla aprobada."""
        application = self.uow.applications.get(application_id)
        if application is None:
            raise ApplicationNotFound(f"No existe la candidatura {application_id}")

        candidate = self.uow.candidates.get(application.candidate_id)
        job = self.uow.jobs.get(application.job_id)
        if candidate is None or job is None:
            raise NotFoundError("Faltan datos de candidato o vacante")

        template = self.uow.templates.get_by_code(template_code)
        if template is None:
            raise NotFoundError(f"No existe la plantilla «{template_code}»")
        if not template.approved:
            raise PolicyDenied(
                f"La plantilla «{template_code}» no está aprobada. No se preparan "
                "comunicaciones con plantillas sin aprobar."
            )

        key = self.idempotency_key(application_id, template.id, template.template_version)
        existing = self.uow.emails.get_by_idempotency_key(key)
        if existing is not None:
            raise EmailAlreadySent(
                f"Ya existe una comunicación de tipo «{template_code}» para esta "
                f"candidatura (estado: {existing.status.value})"
            )

        variables = self._generate_variables(
            template=template, job=job, application=application,
            extra_context=extra_context or {}, use_ai=use_ai,
        )
        subject, body = self.render(template, job_title=job.title, variables=variables)

        requires_approval = (
            template.requires_human_approval or template.kind in SENSITIVE_EMAIL_KINDS
        )
        message = EmailMessage(
            application_id=application_id,
            candidate_id=candidate.id,
            job_id=job.id,
            template_id=template.id,
            template_version=template.template_version,
            # El destinatario sale del registro del candidato. En ningún punto
            # del flujo se acepta una dirección proporcionada desde fuera.
            recipient=candidate.email,
            subject=subject,
            body=body,
            status=(
                EmailStatus.PENDING_APPROVAL if requires_approval else EmailStatus.APPROVED
            ),
            idempotency_key=key,
            initiated_by=actor.actor_id,
        )
        stored = self.uow.emails.add(message)

        self.audit.record(
            action="email.prepared",
            actor=actor,
            resource_type="application",
            resource_id=application_id,
            new_state={
                "email_id": stored.id,
                "template": template.code,
                "status": stored.status.value,
                "recipient": candidate.email.masked(),
            },
            requires_approval=requires_approval,
            generated_by_ai=use_ai,
        )
        logger.info(
            "Comunicación preparada",
            email_id=stored.id,
            template=template.code,
            requires_approval=requires_approval,
        )
        return PreparedEmail(
            message=stored,
            template=template,
            requires_approval=requires_approval,
            generated_variables=variables,
        )

    def _generate_variables(
        self,
        *,
        template: EmailTemplate,
        job,  # noqa: ANN001
        application,  # noqa: ANN001
        extra_context: dict[str, Any],
        use_ai: bool,
    ) -> dict[str, str]:
        """Obtiene los valores de las variables declaradas por la plantilla.

        Si el modelo no está disponible o falla, se devuelven cadenas vacías y el
        revisor las completa. Un fallo del proveedor no debe impedir comunicarse
        con un candidato.
        """
        allowed = set(template.allowed_variables)
        if not allowed:
            return {}
        if not use_ai or self._llm is None:
            return {name: str(extra_context.get(name, "")) for name in allowed}

        try:
            prompt = get_prompt_registry().get("email_generation")
            user_content = prompt.render_user(
                template_kind=template.kind.value,
                template_subject=template.subject_template,
                template_body=template.body_template,
                allowed_variables="\n".join(f"- {name}" for name in sorted(allowed)),
                context=self._render_context(job, application, extra_context),
                schema=schema_hint(EmailDraftOutput),
            )
            response = self._llm.generate_json(
                system_instruction=prompt.system_instruction,
                user_content=user_content,
                temperature=prompt.temperature,
                max_output_tokens=prompt.max_output_tokens,
            )
            import json

            payload = json.loads(response.text)
            draft = EmailDraftOutput.model_validate(payload)
            # Se descarta cualquier clave fuera de la lista declarada: es la
            # frontera que impide que el modelo introduzca contenido no previsto.
            return {
                name: draft.variables.get(name, "")[:500]
                for name in allowed
            }
        except Exception as exc:  # noqa: BLE001 — degradar es preferible a fallar
            logger.warning(
                "No se pudieron generar las variables con IA; se dejan vacías",
                error=str(exc)[:200],
            )
            return {name: "" for name in allowed}

    @staticmethod
    def _render_context(job, application, extra: dict[str, Any]) -> str:  # noqa: ANN001
        """Contexto que se entrega al modelo.

        Nótese lo que **no** incluye: ni la puntuación, ni la evidencia, ni la
        comparación con otros candidatos. Nada de eso debe acabar en una
        comunicación externa, así que ni siquiera se le ofrece.
        """
        lines = [
            f"Puesto: {job.title}",
            f"Departamento: {job.department or 'no indicado'}",
            f"Estado del proceso: {application.status.value}",
        ]
        lines.extend(f"{k}: {v}" for k, v in extra.items())
        return "\n".join(lines)

    @staticmethod
    def render(
        template: EmailTemplate, *, job_title: str, variables: dict[str, str]
    ) -> tuple[str, str]:
        """Rellena la plantilla.

        Se sustituyen únicamente los marcadores presentes en el texto aprobado, y
        cualquier marcador sin valor se elimina en lugar de quedar visible. No se
        usa un motor de plantillas con lógica: una plantilla no debe poder
        ejecutar nada.
        """
        values = {"job_title": job_title, **variables}

        def _replace(text: str) -> str:
            def _sub(match: re.Match[str]) -> str:
                return str(values.get(match.group(1), "")).strip()

            rendered = _PLACEHOLDER_RE.sub(_sub, text)
            # Limpieza de los huecos que quedaron vacíos.
            rendered = re.sub(r"\n{3,}", "\n\n", rendered)
            return rendered.strip()

        return _replace(template.subject_template), _replace(template.body_template)

    # ── Aprobación ───────────────────────────────────────────────────────────

    def approve(
        self,
        *,
        email_id: str,
        actor: Actor,
        actor_permissions: frozenset[Permission] = frozenset(),
        note: str = "",
    ) -> EmailMessage:
        message = self._get(email_id)
        if message.status is not EmailStatus.PENDING_APPROVAL:
            raise ValidationError(
                f"La comunicación está en estado «{message.status.value}» y no "
                "requiere aprobación"
            )
        if actor_permissions and Permission.EMAIL_APPROVE not in actor_permissions:
            from app.core.exceptions import PermissionDenied

            raise PermissionDenied("Falta el permiso email:approve")

        message.status = EmailStatus.APPROVED
        message.approved_by = actor.actor_id
        message.approved_at = datetime.now(UTC)
        message.touch()
        self.uow.emails.update(message)

        self.audit.record(
            action="email.approved",
            actor=actor,
            resource_type="application",
            resource_id=message.application_id,
            human_approval_by=actor.actor_id,
            email_id=message.id,
            note=note,
        )
        return message

    def reject_draft(self, *, email_id: str, actor: Actor, reason: str) -> EmailMessage:
        message = self._get(email_id)
        message.status = EmailStatus.CANCELLED
        message.error_message = reason
        message.touch()
        self.uow.emails.update(message)

        self.audit.record(
            action="email.cancelled",
            actor=actor,
            resource_type="application",
            resource_id=message.application_id,
            email_id=message.id,
            reason=reason,
        )
        return message

    # ── Envío ────────────────────────────────────────────────────────────────

    def send(
        self,
        *,
        email_id: str,
        actor: Actor,
        actor_permissions: frozenset[Permission] = frozenset(),
        force_dry_run: bool | None = None,
    ) -> EmailMessage:
        """Envía una comunicación ya aprobada, tras validar la política."""
        message = self._get(email_id)
        if message.status is EmailStatus.SENT:
            # Idempotencia observable: reenviar lo ya enviado no es un error, es
            # una operación sin efecto.
            logger.info("La comunicación ya estaba enviada", email_id=email_id)
            return message
        if message.status is EmailStatus.PENDING_APPROVAL:
            raise HumanApprovalRequired(
                "La comunicación requiere aprobación humana antes de enviarse"
            )
        if message.status is EmailStatus.CANCELLED:
            raise ValidationError("La comunicación fue cancelada")

        application = self.uow.applications.get(message.application_id)
        candidate = self.uow.candidates.get(message.candidate_id)
        template = self.uow.templates.get(message.template_id)
        if application is None or candidate is None or template is None:
            raise NotFoundError("Faltan datos para validar el envío")

        flags = self.uow.settings.feature_flags()
        dry_run = flags["DRY_RUN"] if force_dry_run is None else force_dry_run

        decision = self.policy.evaluate(
            PolicyContext(
                action=ActionType.SEND_EMAIL,
                actor_id=actor.actor_id,
                actor_permissions=actor_permissions,
                is_human_actor=actor.actor_type.value == "user",
                application_id=application.id,
                application_status=application.status,
                candidate_email=str(candidate.email),
                recipient=str(message.recipient),
                template_kind=template.kind,
                template_approved=template.approved,
                already_sent=False,
                emails_sent_last_hour=self.uow.emails.count_sent_since(message.job_id, 1),
                rate_limit_per_hour=DEFAULT_RATE_LIMIT_PER_HOUR,
                dry_run=dry_run,
                feature_flags=flags,
            )
        )
        if not decision.allowed:
            self.audit.record(
                action="email.send_denied",
                actor=actor,
                resource_type="application",
                resource_id=message.application_id,
                policy_result=str(decision),
                severity=(
                    Severity.CRITICAL if decision.severity is Severity.CRITICAL
                    else Severity.MEDIUM
                ),
                email_id=message.id,
            )
            if decision.needs_human:
                raise HumanApprovalRequired(decision.reason)
            raise PolicyDenied(decision.reason)

        adapter = self._adapter()
        try:
            result = adapter.send(
                to=str(message.recipient),
                subject=message.subject,
                body=message.body,
                idempotency_key=message.idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001 — el intento no se pierde
            message.status = EmailStatus.FAILED
            message.retry_count += 1
            message.error_message = str(exc)[:400]
            message.touch()
            self.uow.emails.update(message)
            self.audit.record(
                action="email.failed",
                actor=actor,
                resource_type="application",
                resource_id=message.application_id,
                severity=Severity.MEDIUM,
                email_id=message.id,
                error=str(exc)[:200],
                retry_count=message.retry_count,
            )
            raise

        message.status = EmailStatus.SENT
        message.gmail_message_id = result.get("message_id", "")
        message.gmail_thread_id = result.get("thread_id", "")
        message.sent_at = datetime.now(UTC)
        message.touch()
        self.uow.emails.update(message)

        self.audit.record(
            action="email.sent",
            actor=actor,
            resource_type="application",
            resource_id=message.application_id,
            new_state={
                "email_id": message.id,
                "recipient": message.recipient.masked(),
                "template": template.code,
                "gmail_message_id": message.gmail_message_id,
                "provider": getattr(adapter, "provider", "unknown"),
            },
            policy_result=str(decision),
            human_approval_by=message.approved_by,
        )
        return message

    # ── Utilidades ───────────────────────────────────────────────────────────

    @staticmethod
    def idempotency_key(application_id: str, template_id: str, version: int) -> str:
        """Clave determinista por candidatura, plantilla y versión.

        Incluir la versión permite reenviar legítimamente si la plantilla cambia,
        sin abrir la puerta a duplicar la misma comunicación.
        """
        raw = f"{application_id}:{template_id}:v{version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:40]

    def _get(self, email_id: str) -> EmailMessage:
        message = self.uow.emails.get(email_id)
        if message is None:
            raise NotFoundError(f"No existe la comunicación {email_id}")
        return message

    def pending_approval(self) -> list[EmailMessage]:
        return self.uow.emails.list_pending_approval()

    def history(self, application_id: str) -> list[EmailMessage]:
        return self.uow.emails.list_for_application(application_id)

    def provider_status(self) -> dict[str, Any]:
        adapter = self._adapter()
        ok, detail = adapter.verify_credentials()
        return {
            "provider": getattr(adapter, "provider", "unknown"),
            "configured": ok,
            "detail": detail,
            "is_simulated": getattr(adapter, "provider", "") == "null",
        }


__all__ = ["DEFAULT_RATE_LIMIT_PER_HOUR", "EmailService", "PreparedEmail"]
