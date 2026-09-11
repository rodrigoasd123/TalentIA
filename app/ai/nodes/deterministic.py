"""Nodos determinísticos del grafo.

Ninguno de estos nodos llama a un modelo de lenguaje. Son Python puro: rápidos,
gratuitos, reproducibles y, sobre todo, imposibles de manipular mediante el
contenido de un CV.

Son siete de los once nodos del grafo. Esa proporción es intencionada: cada
decisión que puede tomarse con una regla es una decisión que no depende de un
sistema probabilístico.
"""

from __future__ import annotations

from app.ai.guardrails.bias_detector import LexicalBiasDetector, collect_reasoning_texts
from app.ai.guardrails.evidence_verifier import EvidenceVerifier
from app.ai.guardrails.injection_detector import InjectionDetector
from app.ai.guardrails.pii_sanitizer import PIISanitizer, assert_no_pii
from app.ai.nodes.base import Node, NodeSpec
from app.ai.policies.policy_engine import PolicyContext, PolicyEngine
from app.ai.state import (
    WorkflowState,
    add_proposed_action,
    add_review_reason,
)
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.domain.entities import DimensionScore, ResumeExtraction
from app.domain.enums import (
    ActionType,
    ApplicationStatus,
    Recommendation,
    ReviewReason,
    ScoringDimension,
    Severity,
)
from app.domain.rules.hard_filters import HardFilterEngine
from app.domain.rules.scoring import ScoringPolicy
from app.domain.value_objects import ProposedAction

logger = get_logger(__name__)


# ── 1. Validación de entrada ─────────────────────────────────────────────────


class InputValidationNode(Node):
    """Comprueba que hay materia prima suficiente antes de gastar nada.

    Es el nodo más barato del grafo y evita el escenario absurdo de pagar una
    llamada a un modelo para procesar un documento vacío.
    """

    spec = NodeSpec(
        name="input_validation",
        reads=frozenset({"raw_resume_text", "requirements", "candidate_email"}),
        writes=frozenset({"terminated_early", "termination_reason"}),
        description="Valida longitud, contenido mínimo y requisitos presentes",
    )

    MIN_CHARS = 120

    def run(self, state: WorkflowState) -> WorkflowState:
        text = (state.get("raw_resume_text") or "").strip()
        settings = get_settings()

        if not text:
            raise ValidationError("El CV no contiene texto extraíble")
        if len(text) < self.MIN_CHARS:
            raise ValidationError(
                f"El CV tiene solo {len(text)} caracteres; se requieren al menos {self.MIN_CHARS}. "
                "Puede tratarse de un PDF escaneado sin capa de texto."
            )
        if len(text) > settings.max_resume_chars * 2:
            raise ValidationError(
                f"El CV supera con mucho el tamaño esperado ({len(text)} caracteres)"
            )
        if state.get("requirements") is None:
            raise ValidationError("La vacante no tiene requisitos definidos")

        return state


# ── 2. Sanitización y detección de inyección ─────────────────────────────────


class SanitizationNode(Node):
    """Guardrail G2. Normaliza, detecta manipulación y neutraliza delimitadores.

    Detectar una inyección no rechaza al candidato: marca el caso para revisión
    humana. La distinción importa, porque un rechazo automático por contenido
    sospechoso permitiría eliminar a un rival insertando texto en su CV.
    """

    spec = NodeSpec(
        name="sanitization",
        reads=frozenset({"raw_resume_text"}),
        writes=frozenset(
            {"sanitized_text", "sanitization", "injection_detected", "injection_severity"}
        ),
        description="Guardrail anti prompt injection",
    )

    #: Severidades ordenadas, para decidir qué consecuencia tiene cada hallazgo.
    _ORDER = {
        Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2,
        Severity.HIGH: 3, Severity.CRITICAL: 4,
    }

    def run(self, state: WorkflowState) -> WorkflowState:
        detector = InjectionDetector(max_chars=get_settings().max_resume_chars)
        result = detector.sanitize(state["raw_resume_text"])

        state["sanitized_text"] = result.sanitized_text
        state["sanitization"] = result
        state["injection_severity"] = result.max_severity.value

        # No todo hallazgo es un ataque. Graduamos la consecuencia:
        #
        #   HIGH/CRITICAL → intento real de manipular al agente. Bloquea la
        #                   automatización y activa el motor de políticas.
        #   MEDIUM        → anomalía (relleno de palabras clave, evasión por
        #                   codificación). Va a revisión humana, pero no se
        #                   trata como ataque ni endurece las políticas.
        #   LOW/INFO      → solo queda registrado.
        #
        # La graduación importa: tratar cualquier rareza como ataque llenaría la
        # cola de revisión de falsos positivos y acabaría con los revisores
        # ignorando la señal, que es la peor forma de perder un control.
        severity = self._ORDER[result.max_severity]
        is_attack = severity >= self._ORDER[Severity.HIGH]
        state["injection_detected"] = is_attack

        if result.is_suspicious:
            logger.security(
                "Contenido anómalo detectado en CV",
                application_id=state.get("application_id", ""),
                severity=result.max_severity.value,
                categories=result.categories,
                findings=len(result.findings),
                treated_as_attack=is_attack,
            )

        if severity >= self._ORDER[Severity.MEDIUM]:
            add_review_reason(state, ReviewReason.INJECTION_DETECTED)
            add_proposed_action(
                state,
                ProposedAction(
                    action_type=ActionType.REQUEST_HUMAN_REVIEW.value,
                    payload={
                        "reason": ReviewReason.INJECTION_DETECTED.value,
                        "severity": result.max_severity.value,
                        "categories": result.categories,
                        "treated_as_attack": is_attack,
                    },
                    rationale=result.summary(),
                    proposed_by_node=self.spec.name,
                ),
            )
        return state


# ── 3. Anonimización ─────────────────────────────────────────────────────────


class PIIAnonymizationNode(Node):
    """Guardrail G3. Retira datos personales antes de cruzar hacia el modelo.

    A partir de este nodo, ningún componente que hable con un servicio externo
    debe usar ``raw_resume_text``. La comprobación final del nodo verifica que
    los datos conocidos del candidato no sobrevivieron a la anonimización.
    """

    spec = NodeSpec(
        name="pii_anonymization",
        reads=frozenset({"sanitized_text", "candidate_name", "candidate_email"}),
        writes=frozenset(
            {"anonymized_text", "pii_map", "pii_categories", "pii_redaction_count"}
        ),
        description="Guardrail de privacidad: anonimización previa al LLM",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        sanitizer = PIISanitizer(candidate_name=state.get("candidate_name") or None)
        result = sanitizer.anonymize(state["sanitized_text"])

        state["anonymized_text"] = result.anonymized_text
        state["pii_map"] = result.pii_map
        state["pii_categories"] = sorted(c.value for c in result.categories_found)
        state["pii_redaction_count"] = result.redaction_count

        # Comprobación de frontera. Si los datos conocidos del candidato siguen
        # presentes, algo falló y no debemos continuar hacia el proveedor externo.
        leaked = assert_no_pii(
            result.anonymized_text,
            forbidden_values=[
                state.get("candidate_name", ""),
                state.get("candidate_email", ""),
            ],
        )
        if leaked:
            logger.security(
                "Fuga de PII detectada tras la anonimización",
                application_id=state.get("application_id", ""),
                leaked_kinds=len(leaked),
            )
            raise ValidationError(
                "La anonimización no eliminó datos personales conocidos del candidato. "
                "Se detiene el envío al proveedor de IA."
            )

        logger.info(
            "Anonimización completada",
            redactions=result.redaction_count,
            categories=state["pii_categories"],
        )
        return state


# ── 4. Requisitos de la vacante ──────────────────────────────────────────────


class JobRequirementNode(Node):
    """Deja los requisitos listos para el filtrado. Nodo de preparación pura."""

    spec = NodeSpec(
        name="job_requirement",
        reads=frozenset({"requirements"}),
        writes=frozenset({"requirements"}),
        description="Carga y valida los criterios de la vacante",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        requirements = state["requirements"]
        if not requirements.hard_filters and not requirements.mandatory_skills:
            logger.warning(
                "La vacante no define filtros obligatorios",
                job_id=state.get("job_id", ""),
            )
        return state


# ── 5. Filtros determinísticos ───────────────────────────────────────────────


class HardFilterNode(Node):
    """Aplica los criterios excluyentes. Sin IA, por diseño.

    Se ejecuta **antes** de la evaluación semántica, y no solo por corrección:
    un candidato que no cumple un requisito obligatorio no llega a consumir una
    llamada al modelo, lo que reduce el coste del proceso de forma sustancial.
    """

    spec = NodeSpec(
        name="hard_filter",
        reads=frozenset({"extraction", "requirements"}),
        writes=frozenset({"filter_results", "passed_hard_filters"}),
        description="Filtros excluyentes determinísticos",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        extraction: ResumeExtraction | None = state.get("extraction")
        if extraction is None:
            raise ValidationError("No hay datos extraídos sobre los que aplicar filtros")

        engine = HardFilterEngine()
        results = engine.evaluate(state["requirements"].hard_filters, extraction)
        state["filter_results"] = results
        state["passed_hard_filters"] = engine.all_mandatory_passed(results)

        if not state["passed_hard_filters"]:
            failed = engine.failed_mandatory(results)
            logger.info(
                "Filtros obligatorios no superados",
                application_id=state.get("application_id", ""),
                failed=[f.filter_label for f in failed],
            )
            add_review_reason(state, ReviewReason.HARD_FILTER_FAILED)
        return state


# ── 6. Cálculo de puntuación y decisión ──────────────────────────────────────


class ScoreCalculationNode(Node):
    """Calcula el total y decide si hace falta una persona.

    El modelo puntúa dimensiones; **el total se calcula aquí**. Es la diferencia
    entre un número reproducible y un número que depende de cómo se sintiera el
    modelo ese día.
    """

    spec = NodeSpec(
        name="score_calculation",
        reads=frozenset(
            {
                "evaluation_output", "requirements", "filter_results", "extraction",
                "evidence_report", "bias_detected", "injection_detected",
            }
        ),
        writes=frozenset({"scoring_outcome", "requires_human_review", "review_reasons"}),
        description="Cálculo determinístico del total y decisión de revisión",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        settings = get_settings()
        requirements = state["requirements"]
        evaluation = state.get("evaluation_output")

        policy = ScoringPolicy(
            auto_shortlist_enabled=settings.ff_ai_auto_shortlist,
            auto_rejection_enabled=settings.ff_ai_auto_rejection,
            max_unverified_evidence_ratio=settings.max_unverified_evidence_ratio,
        )

        dimension_scores = self._build_dimension_scores(state)
        total = policy.compute_total(dimension_scores, requirements.weights)
        total = policy.apply_criterion_penalties(total, state.get("filter_results", []))

        evidence_report = state.get("evidence_report")
        evidence_rate = evidence_report.verification_rate if evidence_report else 0.0

        extra: list[ReviewReason] = list(state.get("review_reasons", []))
        # Que no haya evaluación semántica solo es un fallo si el candidato
        # llegó a merecerla. Cuando no supera un filtro obligatorio, el grafo la
        # omite a propósito y etiquetarlo como fallo del modelo sería engañoso
        # para quien después lea el motivo de la decisión.
        if evaluation is None and state.get("passed_hard_filters"):
            extra.append(ReviewReason.LLM_FAILURE)
        if state.get("budget_exhausted"):
            extra.append(ReviewReason.BUDGET_EXCEEDED)

        outcome = policy.decide(
            total=total,
            minimum_score=requirements.minimum_score,
            review_threshold=requirements.review_threshold,
            filter_results=state.get("filter_results", []),
            extraction=state.get("extraction"),
            evidence_verification_rate=evidence_rate,
            bias_detected=bool(state.get("bias_detected")),
            injection_detected=bool(state.get("injection_detected")),
            evaluation_performed=evaluation is not None,
            extra_reasons=extra,
        )

        state["scoring_outcome"] = outcome
        state["requires_human_review"] = outcome.requires_human_review
        state["review_reasons"] = outcome.review_reasons

        logger.info(
            "Puntuación calculada",
            application_id=state.get("application_id", ""),
            total=float(outcome.total),
            recommendation=outcome.recommendation.value,
            requires_human=outcome.requires_human_review,
            reasons=[r.value for r in outcome.review_reasons],
        )
        return state

    @staticmethod
    def _build_dimension_scores(state: WorkflowState) -> list[DimensionScore]:
        """Traduce la salida del modelo a entidades de dominio con sus pesos."""
        evaluation = state.get("evaluation_output")
        if evaluation is None:
            return []
        weights = state["requirements"].weights
        report = state.get("evidence_report")
        spans_by_index = list(report.items) if report else []

        scores: list[DimensionScore] = []
        cursor = 0
        for dimension in evaluation.dimensions:
            enum_dimension = ScoringDimension(dimension.dimension)
            span_count = len(dimension.evidence)
            spans = [s.to_span() for s in spans_by_index[cursor : cursor + span_count]]
            cursor += span_count
            scores.append(
                DimensionScore(
                    dimension=enum_dimension,
                    score=dimension.score,
                    weight=weights.weight_of(enum_dimension),
                    reasoning=dimension.reasoning,
                    evidence=spans,
                )
            )
        return scores


# ── 7. Verificación de evidencia ─────────────────────────────────────────────


class EvidenceVerificationNode(Node):
    """Guardrail G5. Comprueba que cada cita existe en el CV.

    Se verifica contra el texto **anonimizado**, que es exactamente lo que vio
    el modelo. Verificar contra el original permitiría dar por buena una cita
    que el modelo no pudo haber leído.
    """

    spec = NodeSpec(
        name="evidence_verification",
        reads=frozenset({"evaluation_output", "anonymized_text", "extraction"}),
        writes=frozenset({"evidence_report"}),
        description="Verificación de evidencia contra el documento fuente",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        evaluation = state.get("evaluation_output")
        if evaluation is None:
            return state

        verifier = EvidenceVerifier()
        report = verifier.verify_evaluation(
            evaluation,
            source_text=state.get("anonymized_text", ""),
            extraction=state.get("extraction"),
        )
        state["evidence_report"] = report

        threshold = 1 - get_settings().max_unverified_evidence_ratio
        if report.verification_rate < threshold:
            logger.warning(
                "Evidencia insuficientemente verificable",
                application_id=state.get("application_id", ""),
                rate=round(report.verification_rate, 3),
                unverified=[u.quote[:80] for u in report.unverified[:5]],
            )
            add_review_reason(state, ReviewReason.EVIDENCE_UNVERIFIABLE)
        return state


# ── 8. Detección léxica de sesgo ─────────────────────────────────────────────


class LexicalBiasNode(Node):
    """Guardrail G6, capa determinística.

    Complementa al auditor con modelo. Esta capa es gratuita, instantánea y no
    puede fallar por indisponibilidad del proveedor, así que se ejecuta siempre,
    incluso cuando la auditoría con modelo está desactivada.
    """

    spec = NodeSpec(
        name="lexical_bias_check",
        reads=frozenset({"evaluation_output"}),
        writes=frozenset({"bias_report", "bias_detected"}),
        description="Detección determinística de atributos protegidos en el razonamiento",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        evaluation = state.get("evaluation_output")
        if evaluation is None:
            return state

        detector = LexicalBiasDetector()
        report = detector.analyze(collect_reasoning_texts(evaluation))
        state["bias_report"] = report

        if report.is_blocking:
            state["bias_detected"] = True
            logger.security(
                "Posible sesgo detectado en el razonamiento",
                application_id=state.get("application_id", ""),
                severity=report.max_severity.value,
                categories=report.categories,
            )
            add_review_reason(state, ReviewReason.BIAS_DETECTED)
        elif report.bias_detected:
            logger.info(
                "Indicios leves de sesgo registrados",
                categories=report.categories,
                severity=report.max_severity.value,
            )
        return state


# ── 9. Validación de políticas y propuesta de acciones ───────────────────────


class PolicyValidationNode(Node):
    """Guardrail G7. Convierte la evaluación en acciones propuestas y las somete
    al motor de políticas.

    Aquí termina la responsabilidad del grafo. Lo que sale son propuestas
    acompañadas de un veredicto; ejecutarlas es competencia de la capa de
    aplicación, fuera del alcance del modelo.
    """

    spec = NodeSpec(
        name="policy_validation",
        reads=frozenset(
            {"scoring_outcome", "requires_human_review", "injection_detected", "dry_run"}
        ),
        writes=frozenset({"policy_decisions", "proposed_actions"}),
        description="Evaluación de políticas sobre las acciones propuestas",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        settings = get_settings()
        engine = PolicyEngine()
        outcome = state.get("scoring_outcome")

        if outcome is None:
            add_proposed_action(
                state,
                ProposedAction(
                    action_type=ActionType.REQUEST_HUMAN_REVIEW.value,
                    payload={"reason": ReviewReason.LLM_FAILURE.value},
                    rationale="No se pudo completar la evaluación automática",
                    proposed_by_node=self.spec.name,
                ),
            )
            return state

        target = self._target_status(outcome.recommendation, state)
        if target is None:
            return state

        action = ProposedAction(
            action_type=ActionType.CHANGE_STATUS.value,
            payload={"target_status": target.value, "score": float(outcome.total)},
            rationale=outcome.explanation,
            proposed_by_node=self.spec.name,
        )

        context = PolicyContext(
            action=ActionType.CHANGE_STATUS,
            is_human_actor=False,
            application_id=state.get("application_id", ""),
            application_status=ApplicationStatus.UNDER_EVALUATION,
            target_status=target,
            injection_detected=bool(state.get("injection_detected")),
            bias_detected=bool(state.get("bias_detected")),
            dry_run=bool(state.get("dry_run")),
            feature_flags=settings.static_feature_flags(),
        )
        result = engine.evaluate(context)
        state.setdefault("policy_decisions", []).append(result.to_dict())

        if result.allowed:
            add_proposed_action(state, action)
        else:
            add_proposed_action(
                state,
                ProposedAction(
                    action_type=ActionType.REQUEST_HUMAN_REVIEW.value,
                    payload={
                        "suggested_status": target.value,
                        "policy_rule": result.rule,
                        "score": float(outcome.total),
                    },
                    rationale=f"{result.reason}. {outcome.explanation}",
                    proposed_by_node=self.spec.name,
                ),
            )
            state["requires_human_review"] = True

        logger.info(
            "Política evaluada",
            application_id=state.get("application_id", ""),
            decision=result.decision.value,
            rule=result.rule,
        )
        return state

    @staticmethod
    def _target_status(
        recommendation: Recommendation, state: WorkflowState
    ) -> ApplicationStatus | None:
        if state.get("requires_human_review"):
            return ApplicationStatus.HUMAN_REVIEW
        if recommendation is Recommendation.SHORTLIST:
            return ApplicationStatus.SHORTLISTED
        if recommendation is Recommendation.REJECT:
            return ApplicationStatus.REJECTED
        return ApplicationStatus.HUMAN_REVIEW


# ── 10. Auditoría ────────────────────────────────────────────────────────────


class AuditNode(Node):
    """Cierra el workflow dejando constancia de lo ocurrido.

    No escribe en base de datos: emite el resumen que la capa de aplicación
    persistirá. Un nodo del grafo con acceso de escritura a la auditoría sería
    justo el tipo de acoplamiento que este diseño evita.
    """

    spec = NodeSpec(
        name="audit",
        reads=frozenset({"scoring_outcome", "proposed_actions", "review_reasons"}),
        writes=frozenset(),
        description="Emisión del resumen de auditoría del workflow",
    )

    def run(self, state: WorkflowState) -> WorkflowState:
        from app.ai.state import state_summary

        summary = state_summary(state)
        logger.info("Workflow finalizado", **summary)
        return state


DETERMINISTIC_NODES = (
    InputValidationNode,
    SanitizationNode,
    PIIAnonymizationNode,
    JobRequirementNode,
    HardFilterNode,
    EvidenceVerificationNode,
    LexicalBiasNode,
    ScoreCalculationNode,
    PolicyValidationNode,
    AuditNode,
)

__all__ = [
    "DETERMINISTIC_NODES", "AuditNode", "EvidenceVerificationNode", "HardFilterNode",
    "InputValidationNode", "JobRequirementNode", "LexicalBiasNode",
    "PIIAnonymizationNode", "PolicyValidationNode", "SanitizationNode",
    "ScoreCalculationNode",
]
