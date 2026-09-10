"""Nodos que invocan un modelo de lenguaje.

Solo cuatro de los catorce nodos del grafo llegan aquí, y cada uno tiene una
responsabilidad estrecha. Todos comparten el mismo patrón:

    prompt versionado → llamada con timeout → JSON → validación Pydantic
    → reintento acotado con instrucción reforzada → si falla, revisión humana

Ningún nodo de este módulo decide nada. Producen objetos validados que los
nodos determinísticos usan después para calcular y decidir. Si el proveedor cae,
el grafo continúa y el caso acaba en la cola de revisión: la indisponibilidad de
un servicio externo nunca debe traducirse en una decisión sobre una persona.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

from app.ai.guardrails.injection_detector import wrap_untrusted
from app.ai.nodes.base import Node, NodeSpec
from app.ai.prompts.registry import PromptVersion, get_prompt_registry
from app.ai.schemas import (
    BiasAuditOutput,
    CandidateEvaluationOutput,
    ResumeExtractionOutput,
    schema_hint,
)
from app.ai.state import WorkflowState, add_review_reason
from app.core.config import get_settings
from app.core.exceptions import LLMNotConfigured, LLMValidationError
from app.core.logging import get_logger
from app.core.observability import BudgetGuard, TokenUsage, approximate_tokens
from app.domain.entities import Education, ResumeExtraction, WorkExperience
from app.domain.enums import LanguageLevel, ReviewReason, Severity
from app.domain.ports import LLMPort
from app.domain.value_objects import LanguageSkill

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

#: Instrucción que se añade en el reintento. Ser explícito sobre el fallo
#: anterior resuelve en la práctica la mayoría de salidas malformadas.
_RETRY_SUFFIX = (
    "\n\n[CORRECCIÓN] Tu respuesta anterior no cumplió el esquema. "
    "Responde ÚNICAMENTE con un objeto JSON válido, sin texto antes ni después, "
    "sin comentarios y sin bloques de código. Error detectado: {error}"
)


class LLMNode(Node):
    """Base de los nodos que invocan al modelo."""

    prompt_name: str
    output_model: type[BaseModel]

    def __init__(self, llm: LLMPort, *, budget: BudgetGuard | None = None) -> None:
        self.llm = llm
        self.budget = budget

    # ── Invocación con validación ────────────────────────────────────────────

    def _prompt(self) -> PromptVersion:
        return get_prompt_registry().get(self.prompt_name)

    def _invoke(
        self, prompt: PromptVersion, user_content: str, state: WorkflowState, model_cls: type[T]
    ) -> T:
        """Llama al modelo y valida la salida, con un reintento acotado."""
        if not self.llm.is_configured:
            raise LLMNotConfigured()
        if self.budget is not None and self.budget.exhausted:
            state["budget_exhausted"] = True
            raise LLMValidationError("Presupuesto de IA agotado antes de la llamada")

        settings = get_settings()
        last_error = ""
        content = user_content

        for attempt in range(1, settings.llm_max_retries + 1):
            response = self.llm.generate_json(
                system_instruction=prompt.system_instruction,
                user_content=content,
                temperature=prompt.temperature,
                max_output_tokens=prompt.max_output_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
            )
            self._account(response, state, prompt)

            try:
                payload = _extract_json(response.text)
                return model_cls.model_validate(payload)
            except (PydanticValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)[:400]
                logger.warning(
                    "Salida del modelo no conforme al esquema",
                    node=self.spec.name,
                    prompt=prompt.full_id,
                    attempt=attempt,
                    error=last_error,
                )
                content = user_content + _RETRY_SUFFIX.format(error=last_error)

        raise LLMValidationError(
            f"El modelo no produjo una salida válida tras {settings.llm_max_retries} intentos: "
            f"{last_error}"
        )

    def _account(self, response: Any, state: WorkflowState, prompt: PromptVersion) -> None:
        """Registra tokens y coste, y actualiza el presupuesto."""
        usage: TokenUsage = state.setdefault("token_usage", TokenUsage())
        prompt_tokens = response.prompt_tokens or approximate_tokens(
            prompt.system_instruction
        )
        completion_tokens = response.completion_tokens or approximate_tokens(response.text)
        before = usage.estimated_cost_usd
        usage.add(prompt_tokens, completion_tokens, response.model)
        if self.budget is not None:
            self.budget.charge(usage.estimated_cost_usd - before)
            if self.budget.exhausted:
                state["budget_exhausted"] = True
                logger.warning(
                    "Presupuesto de IA agotado",
                    spent_usd=round(self.budget.spent_usd, 4),
                    limit_usd=self.budget.limit_usd,
                )


# ── Extracción de CV ─────────────────────────────────────────────────────────


class ResumeParserNode(LLMNode):
    """Convierte el texto del CV en datos estructurados.

    Trabaja sobre el texto **ya anonimizado**. Es tentador dejar que la
    extracción vea el documento completo —al fin y al cabo, "solo" extrae datos—
    pero eso enviaría nombre, edad, teléfono y documento de identidad a un
    servicio externo, que es exactamente lo que el sistema promete no hacer.

    Y no hace falta: la extracción necesita años de experiencia, tecnologías,
    formación e idiomas, y nada de eso es información personal. El nombre y el
    correo del candidato ya los tiene el sistema desde su registro; no hay
    ninguna razón para volver a obtenerlos del documento.
    """

    spec = NodeSpec(
        name="resume_parser",
        timeout_seconds=60.0,
        max_retries=1,
        is_deterministic=False,
        reads=frozenset({"anonymized_text"}),
        writes=frozenset({"extraction_output", "extraction", "extraction_attempts"}),
        description="Extracción estructurada del CV anonimizado mediante LLM",
    )
    prompt_name = "resume_extraction"
    output_model = ResumeExtractionOutput

    def run(self, state: WorkflowState) -> WorkflowState:
        prompt = self._prompt()
        state["extraction_attempts"] = state.get("extraction_attempts", 0) + 1

        user_content = prompt.render_user(
            schema=schema_hint(ResumeExtractionOutput),
            document=wrap_untrusted(
                state["anonymized_text"], document_id=state.get("resume_id", "")
            ),
        )
        output = self._invoke(prompt, user_content, state, ResumeExtractionOutput)

        state["extraction_output"] = output
        state["extraction"] = _to_domain_extraction(output)

        if output.suspicious_content_found:
            # El modelo también señaló contenido manipulador. Es una señal
            # secundaria: la primaria es el detector determinístico.
            logger.security(
                "El modelo señaló contenido sospechoso en el CV",
                application_id=state.get("application_id", ""),
                note=output.suspicious_content_note[:200],
            )
            state["injection_detected"] = True
            add_review_reason(state, ReviewReason.INJECTION_DETECTED)

        if state["extraction"].average_confidence < 0.65:
            add_review_reason(state, ReviewReason.LOW_PARSE_CONFIDENCE)

        logger.info(
            "CV extraído",
            years=output.total_years_experience,
            skills=len(output.skills) + len(output.technologies),
            confidence=round(state["extraction"].average_confidence, 2),
        )
        return state

    def on_failure(self, state: WorkflowState, error: Exception) -> WorkflowState:
        """Sin extracción no hay filtros ni evaluación posibles.

        Se marca el fin anticipado del grafo y el caso pasa a una persona con el
        CV original a la vista.
        """
        state["terminated_early"] = True
        state["termination_reason"] = f"No se pudo extraer el CV: {error}"
        add_review_reason(state, ReviewReason.LLM_FAILURE)
        return state


# ── Evaluación semántica ─────────────────────────────────────────────────────


class CandidateScoringNode(LLMNode):
    """Puntúa dimensión a dimensión con evidencia citable.

    Recibe el texto **anonimizado**. No calcula el total, no propone acciones y
    no ve el nombre ni el correo del candidato.
    """

    spec = NodeSpec(
        name="candidate_scoring",
        timeout_seconds=90.0,
        max_retries=1,
        is_deterministic=False,
        reads=frozenset(
            {"anonymized_text", "extraction", "requirements", "filter_results", "job_title"}
        ),
        writes=frozenset({"evaluation_output", "scoring_attempts"}),
        description="Evaluación semántica con evidencia",
    )
    prompt_name = "candidate_evaluation"
    output_model = CandidateEvaluationOutput

    def run(self, state: WorkflowState) -> WorkflowState:
        prompt = self._prompt()
        state["scoring_attempts"] = state.get("scoring_attempts", 0) + 1
        requirements = state["requirements"]

        user_content = prompt.render_user(
            job_title=state.get("job_title", ""),
            job_department=state.get("job_department", ""),
            job_description=(state.get("job_description", "") or "")[:3000],
            mandatory_skills=", ".join(requirements.mandatory_skills) or "no especificados",
            optional_skills=", ".join(requirements.optional_skills) or "no especificados",
            min_years=requirements.min_years_experience,
            education_level=requirements.education_level or "no especificada",
            languages=_render_languages(requirements),
            certifications=", ".join(requirements.certifications) or "ninguna",
            dimensions=_render_dimensions(requirements),
            filter_summary=_render_filters(state),
            extraction_summary=_render_extraction(state),
            schema=schema_hint(CandidateEvaluationOutput),
            document=wrap_untrusted(
                state["anonymized_text"], document_id=state.get("resume_id", "")
            ),
        )
        output = self._invoke(prompt, user_content, state, CandidateEvaluationOutput)
        state["evaluation_output"] = output

        logger.info(
            "Evaluación semántica completada",
            dimensions=len(output.dimensions),
            evidence_items=output.evidence_count,
            model_recommendation=output.recommendation,
        )
        return state

    def on_failure(self, state: WorkflowState, error: Exception) -> WorkflowState:
        add_review_reason(state, ReviewReason.LLM_FAILURE)
        return state


# ── Auditoría de sesgo con modelo ────────────────────────────────────────────


class BiasCheckNode(LLMNode):
    """Segundo modelo que audita el razonamiento del primero.

    Es opcional: si falla o está desactivado, la capa léxica determinística ya
    se ejecutó y el sistema no se queda sin control de equidad.
    """

    spec = NodeSpec(
        name="bias_check",
        timeout_seconds=45.0,
        max_retries=1,
        is_deterministic=False,
        reads=frozenset({"evaluation_output", "job_title"}),
        writes=frozenset({"bias_audit_output", "bias_detected"}),
        description="Auditoría de sesgo del razonamiento mediante LLM",
    )
    prompt_name = "bias_audit"
    output_model = BiasAuditOutput

    def run(self, state: WorkflowState) -> WorkflowState:
        evaluation = state.get("evaluation_output")
        if evaluation is None:
            return state

        prompt = self._prompt()
        user_content = prompt.render_user(
            job_title=state.get("job_title", ""),
            reasoning_block=_render_reasoning(evaluation),
            schema=schema_hint(BiasAuditOutput),
        )
        output = self._invoke(prompt, user_content, state, BiasAuditOutput)
        state["bias_audit_output"] = output

        if output.bias_detected and output.max_severity in {"high", "critical"}:
            state["bias_detected"] = True
            logger.security(
                "El auditor de sesgo detectó indicios relevantes",
                application_id=state.get("application_id", ""),
                severity=output.max_severity,
                categories=sorted({i.category for i in output.indicators}),
            )
            add_review_reason(state, ReviewReason.BIAS_DETECTED)
        return state

    def on_failure(self, state: WorkflowState, error: Exception) -> WorkflowState:
        """Si el auditor falla, el caso pasa a revisión.

        No se da por buena una evaluación cuya equidad no se ha podido comprobar.
        """
        logger.warning("La auditoría de sesgo no pudo completarse", error=str(error)[:200])
        add_review_reason(state, ReviewReason.BIAS_DETECTED)
        return state


# ── Ayudas de renderizado ────────────────────────────────────────────────────


def _extract_json(text: str) -> dict[str, Any]:
    """Extrae el objeto JSON de la respuesta del modelo.

    Aunque se pida JSON puro, los modelos a veces envuelven la salida en un
    bloque de código o añaden una frase introductoria. Se limpia de forma
    conservadora antes de rendirse.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Respuesta vacía del modelo")

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"No se encontró un objeto JSON en la respuesta: {cleaned[:200]}")
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON")
    return parsed


def _to_domain_extraction(output: ResumeExtractionOutput) -> ResumeExtraction:
    """Traduce la salida del modelo a la entidad de dominio.

    La frontera es deliberada: el dominio no debe conocer la forma concreta de
    lo que devuelve un proveedor.
    """
    return ResumeExtraction(
        total_years_experience=output.total_years_experience,
        seniority=output.seniority,
        current_role=output.current_role,
        skills=output.skills,
        technologies=output.technologies,
        experiences=[
            WorkExperience(
                company=e.company, role=e.role, start_date=e.start_date,
                end_date=e.end_date, is_current=e.is_current, description=e.description,
                technologies=e.technologies, years=e.years,
            )
            for e in output.experiences
        ],
        education=[
            Education(
                degree=e.degree, field_of_study=e.field_of_study,
                institution=e.institution, graduation_year=e.graduation_year, level=e.level,
            )
            for e in output.education
        ],
        languages=[
            LanguageSkill(language=lang.language, level=LanguageLevel(lang.level))
            for lang in output.languages
        ],
        certifications=output.certifications,
        availability=output.availability,
        field_confidence=output.field_confidence,
        suspicious_content_found=output.suspicious_content_found,
        suspicious_content_note=output.suspicious_content_note,
    )


def _render_languages(requirements: Any) -> str:
    if not requirements.languages:
        return "no especificados"
    return ", ".join(f"{ls.language} nivel {ls.level.value}" for ls in requirements.languages)


def _render_dimensions(requirements: Any) -> str:
    return "\n".join(
        f"- {dimension.value}: peso {requirements.weights.weight_of(dimension):.0f}%"
        for dimension in requirements.weights.dimensions
    )


def _render_filters(state: WorkflowState) -> str:
    results = state.get("filter_results", [])
    if not results:
        return "No se definieron filtros obligatorios para esta vacante."
    return "\n".join(f"- {r}" for r in results)


def _render_extraction(state: WorkflowState) -> str:
    extraction = state.get("extraction")
    if extraction is None:
        return "No hay datos estructurados disponibles."
    lines = [
        f"- Experiencia total declarada: {extraction.total_years_experience} años",
        f"- Nivel: {extraction.seniority}",
        f"- Rol actual: {extraction.current_role or 'no indicado'}",
        f"- Tecnologías: {', '.join(sorted(extraction.normalized_skills())) or 'ninguna detectada'}",
        f"- Certificaciones: {', '.join(extraction.certifications) or 'ninguna'}",
        f"- Idiomas: {', '.join(f'{lang.language} {lang.level.value}' for lang in extraction.languages) or 'no indicados'}",
    ]
    for exp in extraction.experiences[:6]:
        lines.append(
            f"- Experiencia: {exp.role} en {exp.company} ({exp.years} años)"
            + (f" — {', '.join(exp.technologies[:8])}" if exp.technologies else "")
        )
    return "\n".join(lines)


def _render_reasoning(evaluation: CandidateEvaluationOutput) -> str:
    parts = [f"Resumen general: {evaluation.summary}"]
    for dimension in evaluation.dimensions:
        parts.append(
            f"\nDimensión «{dimension.dimension}» — puntuación {dimension.score:.0f}\n"
            f"Justificación: {dimension.reasoning}"
        )
    if evaluation.strengths:
        parts.append("\nFortalezas señaladas: " + "; ".join(evaluation.strengths))
    if evaluation.gaps:
        parts.append("\nCarencias señaladas: " + "; ".join(evaluation.gaps))
    return "\n".join(parts)


LLM_NODES = (ResumeParserNode, CandidateScoringNode, BiasCheckNode)

__all__ = [
    "LLM_NODES", "BiasCheckNode", "CandidateScoringNode", "LLMNode", "ResumeParserNode",
]
