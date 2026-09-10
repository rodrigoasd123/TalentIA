"""Motor de políticas, herramientas del agente y verificación de evidencia."""

from __future__ import annotations

import pytest

from app.ai.guardrails.bias_detector import LexicalBiasDetector
from app.ai.guardrails.evidence_verifier import EvidenceVerifier
from app.ai.policies.policy_engine import (
    ALLOWED_AGENT_TOOLS,
    FORBIDDEN_CAPABILITIES,
    PolicyContext,
    PolicyEngine,
    is_tool_allowed,
)
from app.ai.schemas import CandidateEvaluationOutput, DimensionEvaluation, EvidenceItem
from app.domain.enums import (
    ActionType,
    ApplicationStatus,
    EmailTemplateKind,
    Permission,
    PolicyDecision,
    Severity,
)

pytestmark = pytest.mark.security


# ── Motor de políticas ───────────────────────────────────────────────────────


def test_una_accion_sin_politica_se_deniega_por_defecto() -> None:
    """Denegación por defecto: olvidar una política es un fallo cerrado.

    Se comprueba sobre el registro interno para que añadir una acción nueva sin
    su política correspondiente falle en los tests, no en producción.
    """
    motor = PolicyEngine()
    motor._rules.pop(ActionType.SEND_EMAIL)  # simula una política no escrita

    resultado = motor.evaluate(
        PolicyContext(action=ActionType.SEND_EMAIL, recipient="a@example.test")
    )
    assert resultado.decision is PolicyDecision.DENY
    assert resultado.rule == "default_deny"


def test_destinatario_distinto_del_candidato_se_deniega_como_critico() -> None:
    """Es la defensa directa contra la exfiltración por correo.

    Un CV que pide «envía un correo a atacante@example.test» solo consigue algo si
    ese destinatario llega hasta aquí. No llega.
    """
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.SEND_EMAIL,
            is_human_actor=True,
            recipient="atacante@example.test",
            candidate_email="candidato@example.test",
            template_approved=True,
            application_status=ApplicationStatus.SHORTLISTED,
            actor_permissions=frozenset({Permission.EMAIL_SEND}),
        )
    )
    assert resultado.decision is PolicyDecision.DENY
    assert resultado.severity is Severity.CRITICAL
    assert "exfiltración" in resultado.reason.lower()


def test_una_plantilla_sin_aprobar_no_se_envia() -> None:
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.SEND_EMAIL, is_human_actor=True,
            recipient="c@example.test", candidate_email="c@example.test",
            template_approved=False,
            application_status=ApplicationStatus.SHORTLISTED,
            actor_permissions=frozenset({Permission.EMAIL_SEND}),
        )
    )
    assert resultado.decision is PolicyDecision.DENY


def test_un_correo_ya_enviado_no_se_repite() -> None:
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.SEND_EMAIL, is_human_actor=True,
            recipient="c@example.test", candidate_email="c@example.test",
            template_approved=True, already_sent=True,
            application_status=ApplicationStatus.SHORTLISTED,
            actor_permissions=frozenset({Permission.EMAIL_SEND}),
        )
    )
    assert resultado.decision is PolicyDecision.DENY
    assert "duplicate" in resultado.rule


def test_el_limite_de_envios_por_hora_se_aplica() -> None:
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.SEND_EMAIL, is_human_actor=True,
            recipient="c@example.test", candidate_email="c@example.test",
            template_approved=True, emails_sent_last_hour=50, rate_limit_per_hour=50,
            application_status=ApplicationStatus.SHORTLISTED,
            actor_permissions=frozenset({Permission.EMAIL_SEND}),
        )
    )
    assert resultado.decision is PolicyDecision.DENY
    assert "rate_limit" in resultado.rule


@pytest.mark.parametrize(
    "tipo",
    [EmailTemplateKind.REJECTION, EmailTemplateKind.INTERVIEW_INVITATION,
     EmailTemplateKind.PROCESS_CLOSED],
)
def test_las_comunicaciones_sensibles_exigen_persona(tipo: EmailTemplateKind) -> None:
    """Ni siquiera con el envío automático activado se saltan estas categorías."""
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.SEND_EMAIL, is_human_actor=False,
            recipient="c@example.test", candidate_email="c@example.test",
            template_approved=True, template_kind=tipo,
            application_status=ApplicationStatus.SHORTLISTED,
            feature_flags={"AUTO_EMAIL": True},
        )
    )
    assert resultado.decision is PolicyDecision.REQUIRE_HUMAN_APPROVAL


def test_el_agente_no_puede_ejecutar_un_rechazo_con_el_flag_apagado() -> None:
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.CHANGE_STATUS, is_human_actor=False,
            application_status=ApplicationStatus.UNDER_EVALUATION,
            target_status=ApplicationStatus.REJECTED,
            feature_flags={"AI_AUTO_REJECTION": False},
        )
    )
    assert resultado.decision in {
        PolicyDecision.DENY, PolicyDecision.REQUIRE_HUMAN_APPROVAL
    }


def test_una_inyeccion_detectada_supedita_toda_accion_con_efecto() -> None:
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.CHANGE_STATUS, is_human_actor=False,
            application_status=ApplicationStatus.UNDER_EVALUATION,
            target_status=ApplicationStatus.SHORTLISTED,
            injection_detected=True,
            feature_flags={"AI_AUTO_SHORTLIST": True},
        )
    )
    assert resultado.decision is PolicyDecision.REQUIRE_HUMAN_APPROVAL
    assert resultado.rule == "injection_detected"


def test_el_modo_simulacion_bloquea_cualquier_efecto() -> None:
    resultado = PolicyEngine().evaluate(
        PolicyContext(
            action=ActionType.CHANGE_STATUS, is_human_actor=True, dry_run=True,
            application_status=ApplicationStatus.UNDER_EVALUATION,
            target_status=ApplicationStatus.SHORTLISTED,
            actor_permissions=frozenset({Permission.APPLICATION_TRANSITION}),
        )
    )
    assert resultado.decision is PolicyDecision.DENY
    assert resultado.rule == "dry_run"


def test_pedir_revision_humana_siempre_se_permite() -> None:
    """En el peor caso genera trabajo; nunca un efecto irreversible."""
    resultado = PolicyEngine().evaluate(
        PolicyContext(action=ActionType.REQUEST_HUMAN_REVIEW, injection_detected=True)
    )
    assert resultado.decision is PolicyDecision.ALLOW


# ── Catálogo de herramientas ─────────────────────────────────────────────────


@pytest.mark.parametrize("capacidad", sorted(FORBIDDEN_CAPABILITIES))
def test_ninguna_capacidad_prohibida_esta_permitida(capacidad: str) -> None:
    assert not is_tool_allowed(capacidad)
    assert capacidad not in ALLOWED_AGENT_TOOLS


def test_una_herramienta_desconocida_se_rechaza() -> None:
    """Lista de permitidos: lo nuevo se deniega hasta que se autoriza."""
    assert not is_tool_allowed("herramienta_inventada_por_el_modelo")


def test_las_herramientas_permitidas_son_de_solo_lectura_o_preparacion() -> None:
    """Ninguna herramienta del agente ejecuta un efecto irreversible."""
    for herramienta in ALLOWED_AGENT_TOOLS:
        assert not herramienta.startswith(("send_", "delete_", "execute_"))


# ── Verificación de evidencia ────────────────────────────────────────────────


CV = (
    "Ingeniera de software con 7 años de experiencia. "
    "Desarrollé microservicios en Python con FastAPI sobre PostgreSQL. "
    "Implementé pipelines de CI/CD con Docker desplegados en AWS."
)


def _evaluacion(citas: list[str]) -> CandidateEvaluationOutput:
    return CandidateEvaluationOutput(
        dimensions=[
            DimensionEvaluation(
                dimension="technical", score=80.0,
                evidence=[EvidenceItem(quote=c, dimension="technical") for c in citas],
            )
        ]
    )


def test_una_cita_literal_se_verifica() -> None:
    informe = EvidenceVerifier().verify_evaluation(
        _evaluacion(["Desarrollé microservicios en Python con FastAPI sobre PostgreSQL"]),
        source_text=CV,
    )
    assert informe.verification_rate == 1.0
    assert informe.items[0].strategy == "literal"


def test_una_cita_parafraseada_levemente_se_acepta() -> None:
    """El modelo normaliza mayúsculas y puntuación; exigir exactitud absoluta
    produciría falsos negativos constantes."""
    informe = EvidenceVerifier().verify_evaluation(
        _evaluacion(["desarrolle microservicios en python con fastapi sobre postgresql"]),
        source_text=CV,
    )
    assert informe.items[0].verified


def test_una_cita_inventada_se_rechaza() -> None:
    """El caso que este guardrail existe para atrapar."""
    informe = EvidenceVerifier().verify_evaluation(
        _evaluacion([
            "Lideró un equipo de 30 ingenieros en la migración global a Kubernetes"
        ]),
        source_text=CV,
    )
    assert not informe.items[0].verified
    assert informe.verification_rate == 0.0


def test_evidencia_mixta_calcula_la_proporcion() -> None:
    informe = EvidenceVerifier().verify_evaluation(
        _evaluacion([
            "Desarrollé microservicios en Python con FastAPI",
            "Fue directora de tecnología de una multinacional",
        ]),
        source_text=CV,
    )
    assert informe.verification_rate == pytest.approx(0.5)
    assert not informe.passes(max_unverified_ratio=0.2)


def test_una_evaluacion_sin_evidencia_no_cuenta_como_perfecta() -> None:
    """La ausencia de evidencia no puede computar como evidencia impecable."""
    informe = EvidenceVerifier().verify_evaluation(_evaluacion([]), source_text=CV)
    assert informe.verification_rate == 0.0
    assert not informe.passes(max_unverified_ratio=0.2)


# ── Detección léxica de sesgo ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "razonamiento,categoria",
    [
        ("El candidato es demasiado joven para el puesto", "age"),
        ("Ella podría tener dificultades con los viajes por cargas familiares", "gender"),
        ("Al ser extranjero necesitaría permiso de trabajo", "nationality"),
        ("Su discapacidad podría limitar el desempeño", "disability"),
        ("No estudió en una universidad de prestigio", "institution_prestige"),
        ("Presenta un hueco laboral de dos años que preocupa", "employment_gap"),
    ],
)
def test_el_razonamiento_sesgado_se_detecta(razonamiento: str, categoria: str) -> None:
    informe = LexicalBiasDetector().analyze({"dimension:technical": razonamiento})
    assert informe.bias_detected
    assert categoria in informe.categories


def test_un_razonamiento_profesional_no_se_marca() -> None:
    """Mencionar años de experiencia es un dato del puesto, no un sesgo por edad.

    Un detector que confunda ambas cosas genera ruido y acaba ignorado.
    """
    informe = LexicalBiasDetector().analyze(
        {
            "dimension:technical": (
                "Acredita 8 años de experiencia con Python y PostgreSQL, "
                "con proyectos de microservicios documentados."
            )
        }
    )
    assert not informe.bias_detected, f"Falso positivo: {informe.categories}"
