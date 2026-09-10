"""Grafo de evaluación de VERA.

El flujo completo, de la ingesta del CV a la propuesta de acción:

    validación → sanitización → anonimización → extracción → requisitos
    → filtros duros → ¿cumple? ─ no ─→ cálculo (rechazo o revisión)
                              └─ sí ─→ evaluación semántica → verificación de
                                       evidencia → sesgo léxico → auditoría de
                                       sesgo → cálculo → políticas → auditoría

Tres detalles del cableado merecen explicación:

**La anonimización precede a la extracción.** Ambas fases llaman al proveedor
externo, así que ambas deben trabajar sobre texto anonimizado. Colocarla después
dejaría un hueco por el que el documento íntegro —nombre, edad, documento de
identidad— saldría del sistema en la primera llamada.

**Los filtros duros cortocircuitan la evaluación semántica.** Si un candidato no
cumple un requisito obligatorio, no se le puntúa con el modelo. Ahorra coste,
pero sobre todo evita el sinsentido de producir una valoración detallada de
alguien que ya está excluido por una regla.

**El nodo de cálculo se alcanza por ambos caminos.** Tanto si hubo evaluación
semántica como si no, la decisión pasa por el mismo punto. Así no existe un
camino alternativo que produzca una decisión sin pasar por las reglas.
"""

from __future__ import annotations

from app.ai.graphs.runner import END, GraphDefinition, GraphEngine, build_engine
from app.ai.nodes.deterministic import (
    AuditNode,
    EvidenceVerificationNode,
    HardFilterNode,
    InputValidationNode,
    JobRequirementNode,
    LexicalBiasNode,
    PIIAnonymizationNode,
    PolicyValidationNode,
    SanitizationNode,
    ScoreCalculationNode,
)
from app.ai.nodes.llm_nodes import BiasCheckNode, CandidateScoringNode, ResumeParserNode
from app.ai.state import WorkflowState
from app.core.observability import BudgetGuard
from app.domain.ports import LLMPort

GRAPH_NAME = "vera_evaluation"
GRAPH_VERSION = "1.0.0"


# ── Enrutadores ──────────────────────────────────────────────────────────────
# Son funciones puras sobre el estado. El modelo no participa en el
# enrutamiento: quien decide por dónde sigue el flujo es el código.


def route_after_hard_filters(state: WorkflowState) -> str:
    """¿Merece la pena evaluar semánticamente a este candidato?"""
    if state.get("terminated_early"):
        return "terminado"
    return "cumple" if state.get("passed_hard_filters") else "no_cumple"


def route_after_evaluation(state: WorkflowState) -> str:
    """Si no hubo evaluación utilizable, se salta la verificación de evidencia."""
    return "evaluado" if state.get("evaluation_output") is not None else "sin_evaluacion"


def route_after_lexical_bias(state: WorkflowState) -> str:
    """La auditoría con modelo se omite si ya hay sesgo confirmado.

    Confirmarlo dos veces no aporta información y consume presupuesto: el caso
    ya va camino de revisión humana.
    """
    if state.get("bias_detected"):
        return "sesgo_confirmado"
    if state.get("budget_exhausted"):
        return "sin_presupuesto"
    return "auditar"


def build_evaluation_graph(
    llm: LLMPort,
    *,
    budget: BudgetGuard | None = None,
    enable_llm_bias_audit: bool = True,
    prefer_langgraph: bool = True,
) -> GraphEngine:
    """Construye y compila el grafo de evaluación.

    ``enable_llm_bias_audit`` permite prescindir del segundo modelo sin quedarse
    sin control de equidad: la capa léxica determinística siempre se ejecuta.
    """
    definition = GraphDefinition(name=GRAPH_NAME)

    # ── Nodos ────────────────────────────────────────────────────────────────
    definition.add_node(InputValidationNode())
    definition.add_node(SanitizationNode())
    definition.add_node(ResumeParserNode(llm, budget=budget))
    definition.add_node(PIIAnonymizationNode())
    definition.add_node(JobRequirementNode())
    definition.add_node(HardFilterNode())
    definition.add_node(CandidateScoringNode(llm, budget=budget))
    definition.add_node(EvidenceVerificationNode())
    definition.add_node(LexicalBiasNode())
    if enable_llm_bias_audit:
        definition.add_node(BiasCheckNode(llm, budget=budget))
    definition.add_node(ScoreCalculationNode())
    definition.add_node(PolicyValidationNode())
    definition.add_node(AuditNode())

    # ── Cableado ─────────────────────────────────────────────────────────────
    definition.set_entry_point("input_validation")
    definition.add_edge("input_validation", "sanitization")
    # La anonimización va ANTES de la extracción, no entre extracción y
    # evaluación. Es la diferencia entre "no enviamos datos personales al
    # proveedor" y "no se los enviamos casi nunca": la extracción también es una
    # llamada a un servicio externo y no necesita PII para hacer su trabajo.
    definition.add_edge("sanitization", "pii_anonymization")
    definition.add_edge("pii_anonymization", "resume_parser")
    definition.add_edge("resume_parser", "job_requirement")
    definition.add_edge("job_requirement", "hard_filter")

    definition.add_conditional_edges(
        "hard_filter",
        route_after_hard_filters,
        {
            "cumple": "candidate_scoring",
            # Quien no cumple un requisito obligatorio no se evalúa con el
            # modelo: va directo al cálculo, que aplicará la regla de rechazo o
            # de revisión según la configuración de la vacante.
            "no_cumple": "score_calculation",
            "terminado": "audit",
        },
    )

    definition.add_conditional_edges(
        "candidate_scoring",
        route_after_evaluation,
        {"evaluado": "evidence_verification", "sin_evaluacion": "score_calculation"},
    )

    definition.add_edge("evidence_verification", "lexical_bias_check")

    if enable_llm_bias_audit:
        definition.add_conditional_edges(
            "lexical_bias_check",
            route_after_lexical_bias,
            {
                "auditar": "bias_check",
                "sesgo_confirmado": "score_calculation",
                "sin_presupuesto": "score_calculation",
            },
        )
        definition.add_edge("bias_check", "score_calculation")
    else:
        definition.add_edge("lexical_bias_check", "score_calculation")

    definition.add_edge("score_calculation", "policy_validation")
    definition.add_edge("policy_validation", "audit")
    definition.add_edge("audit", END)

    return build_engine(definition, prefer_langgraph=prefer_langgraph)


def graph_diagram(*, enable_llm_bias_audit: bool = True) -> str:
    """Diagrama Mermaid del grafo, derivado de su definición real.

    Se construye con un modelo simulado porque solo interesa la topología.
    """
    from app.infrastructure.llm.mock_adapter import MockLLMAdapter

    definition = GraphDefinition(name=GRAPH_NAME)
    engine = build_evaluation_graph(
        MockLLMAdapter(),
        enable_llm_bias_audit=enable_llm_bias_audit,
        prefer_langgraph=False,
    )
    definition = engine.definition  # type: ignore[attr-defined]
    return definition.to_mermaid()


__all__ = [
    "GRAPH_NAME", "GRAPH_VERSION", "build_evaluation_graph", "graph_diagram",
    "route_after_evaluation", "route_after_hard_filters", "route_after_lexical_bias",
]
