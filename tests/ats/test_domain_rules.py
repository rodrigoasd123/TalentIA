"""Reglas de dominio: filtros determinísticos, máquina de estados y puntuación.

Estas pruebas no tocan la red, ni la base de datos, ni el modelo. Se ejecutan en
milisegundos, y esa es precisamente la propiedad que justifica mantener el
dominio libre de dependencias externas.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidStateTransition, InvalidScoringWeights
from app.domain.entities import DimensionScore, ResumeExtraction
from app.domain.enums import (
    ApplicationStatus,
    CriterionMode,
    CriterionStatus,
    FilterOperator,
    LanguageLevel,
    Permission,
    Recommendation,
    ReviewReason,
    Role,
    ROLE_PERMISSIONS,
    ScoringDimension,
    TERMINAL_STATUSES,
)
from app.domain.rules.hard_filters import HardFilterEngine, normalize_term
from app.domain.rules.scoring import ScoringPolicy, compare_candidates
from app.domain.rules.state_machine import TRANSITIONS, ApplicationStateMachine
from app.domain.value_objects import FilterResult, HardFilter, LanguageSkill, Score, ScoringWeights


# ── Normalización de habilidades ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Python", "python"), ("JS", "javascript"), ("Postgres", "postgresql"),
        ("PostgreSQL", "postgresql"), ("K8s", "kubernetes"), ("Node.js", "nodejs"),
        ("CI/CD", "cicd"), ("  FastAPI  ", "fastapi"), ("Máchine Learning", "machine learning"),
    ],
)
def test_normalizacion_de_habilidades(entrada: str, esperado: str) -> None:
    """«Postgres» y «PostgreSQL» deben contar como lo mismo.

    Sin esta normalización, un candidato válido quedaría excluido por escribir
    el nombre de una tecnología de forma abreviada.
    """
    assert normalize_term(entrada) == esperado


# ── Filtros determinísticos ──────────────────────────────────────────────────


def test_filtro_de_experiencia_minima(extraccion: ResumeExtraction) -> None:
    filtro = HardFilter(
        field="years_experience", operator=FilterOperator.GTE, value=5,
        label="Mínimo 5 años", legal_basis="Autonomía técnica requerida",
    )
    resultado = HardFilterEngine().evaluate([filtro], extraccion)[0]
    assert resultado.passed
    assert "7.0" in resultado.explanation


def test_filtro_de_experiencia_rechaza_por_debajo(extraccion: ResumeExtraction) -> None:
    extraccion.total_years_experience = 3.0
    filtro = HardFilter(
        field="years_experience", operator=FilterOperator.GTE, value=5,
        label="Mínimo 5 años", legal_basis="Autonomía técnica requerida",
    )
    resultado = HardFilterEngine().evaluate([filtro], extraccion)[0]
    assert not resultado.passed


def test_filtro_de_habilidades_obligatorias(extraccion: ResumeExtraction) -> None:
    filtro = HardFilter(
        field="skills", operator=FilterOperator.CONTAINS_ALL,
        value=["python", "kubernetes"], label="Python y Kubernetes",
        legal_basis="Stack de la plataforma",
    )
    resultado = HardFilterEngine().evaluate([filtro], extraccion)[0]
    assert not resultado.passed
    assert "kubernetes" in resultado.explanation


def test_filtro_de_idioma_respeta_el_orden_de_niveles(extraccion: ResumeExtraction) -> None:
    """C1 satisface un requisito de B2; B1 no."""
    filtro = HardFilter(
        field="languages", operator=FilterOperator.MIN_LEVEL,
        value={"language": "english", "level": "b2"}, label="Inglés B2",
        legal_basis="Documentación técnica en inglés",
    )
    assert HardFilterEngine().evaluate([filtro], extraccion)[0].passed

    extraccion.languages = [LanguageSkill(language="english", level=LanguageLevel.B1)]
    assert not HardFilterEngine().evaluate([filtro], extraccion)[0].passed


def test_idioma_ausente_es_no_acreditado_y_no_bloquea(extraccion: ResumeExtraction) -> None:
    extraccion.languages = []
    filtro = HardFilter(
        field="languages", operator=FilterOperator.MIN_LEVEL,
        value={"language": "english", "level": "b2"}, label="Inglés B2",
        legal_basis="Documentación técnica en inglés",
    )
    resultado = HardFilterEngine().evaluate([filtro], extraccion)[0]

    assert resultado.status is CriterionStatus.UNVERIFIED
    assert resultado.mode is CriterionMode.WEIGHTED
    assert resultado.penalty_percent == 15.0
    assert HardFilterEngine.all_mandatory_passed([resultado])


def test_penalizacion_ponderada_no_anula_el_resto_del_puntaje() -> None:
    resultado = FilterResult(
        filter_label="Inglés B2", field="languages", passed=False, mandatory=True,
        expected="b2", actual=None, explanation="No acreditado",
        status=CriterionStatus.UNVERIFIED, mode=CriterionMode.WEIGHTED,
        penalty_percent=15,
    )

    total = ScoringPolicy.apply_criterion_penalties(Score(value=80), [resultado])
    assert float(total) == pytest.approx(68.0)


def test_tecnologias_dentro_de_la_experiencia_tambien_cuentan() -> None:
    """Un CV que detalla tecnologías por puesto y no las repite en «skills».

    Es un formato habitual, y no reconocerlo excluiría a candidatos válidos por
    una cuestión de maquetación.
    """
    from app.domain.entities import WorkExperience

    extraccion = ResumeExtraction(
        total_years_experience=6.0,
        skills=[],
        experiences=[
            WorkExperience(company="X", role="Dev", technologies=["python", "postgresql"])
        ],
    )
    filtro = HardFilter(
        field="skills", operator=FilterOperator.CONTAINS_ALL,
        value=["python", "postgresql"], label="Python y PostgreSQL",
        legal_basis="Stack de la plataforma",
    )
    assert HardFilterEngine().evaluate([filtro], extraccion)[0].passed


def test_un_filtro_debe_declarar_su_base_legal() -> None:
    """No se puede crear un criterio excluyente sin justificarlo por escrito."""
    with pytest.raises(ValueError):
        HardFilter(
            field="years_experience", operator=FilterOperator.GTE, value=5,
            label="Mínimo 5 años", legal_basis="",
        )


# ── Máquina de estados ───────────────────────────────────────────────────────


def test_transicion_valida() -> None:
    transicion = ApplicationStateMachine.validate(
        ApplicationStatus.NEW, ApplicationStatus.RESUME_PROCESSED
    )
    assert transicion.label == "CV procesado"


def test_transicion_invalida_se_rechaza() -> None:
    with pytest.raises(InvalidStateTransition):
        ApplicationStateMachine.validate(
            ApplicationStatus.NEW, ApplicationStatus.HIRED
        )


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATUSES, key=lambda s: s.value))
def test_los_estados_terminales_no_admiten_salida(terminal: ApplicationStatus) -> None:
    """Un proceso cerrado no se reabre: se crea una candidatura nueva.

    Sin esta garantía, el historial de un candidato dejaría de ser fiable.
    """
    assert ApplicationStateMachine.allowed_targets(terminal) == []
    with pytest.raises(InvalidStateTransition):
        ApplicationStateMachine.validate(terminal, ApplicationStatus.UNDER_EVALUATION)


def test_el_agente_no_puede_ejecutar_transiciones_que_exigen_persona() -> None:
    with pytest.raises(InvalidStateTransition):
        ApplicationStateMachine.validate(
            ApplicationStatus.UNDER_EVALUATION,
            ApplicationStatus.REJECTED,
            is_human_actor=False,
        )


def test_el_agente_no_puede_proponer_una_contratacion() -> None:
    assert not ApplicationStateMachine.agent_may_propose(
        ApplicationStatus.APPROVED, ApplicationStatus.HIRED
    )


def test_toda_transicion_declara_permiso_y_etiqueta() -> None:
    for transicion in TRANSITIONS:
        assert transicion.label, f"Transición sin etiqueta: {transicion}"
        assert isinstance(transicion.required_permission, Permission)


# ── RBAC ─────────────────────────────────────────────────────────────────────


def test_el_auditor_no_puede_modificar_nada() -> None:
    """Un auditor que puede escribir deja de ser un control independiente."""
    permisos = ROLE_PERMISSIONS[Role.AUDITOR]
    prohibidos = {
        Permission.JOB_WRITE, Permission.CANDIDATE_WRITE,
        Permission.APPLICATION_TRANSITION, Permission.EVALUATION_OVERRIDE,
        Permission.EMAIL_SEND, Permission.SETTINGS_WRITE, Permission.REVIEW_DECIDE,
    }
    assert not (permisos & prohibidos)


def test_solo_el_administrador_puede_cambiar_la_configuracion() -> None:
    for rol, permisos in ROLE_PERMISSIONS.items():
        if rol is not Role.ADMIN:
            assert Permission.SETTINGS_WRITE not in permisos, (
                f"El rol {rol.value} puede modificar la configuración del sistema"
            )


def test_el_recruiter_no_puede_aprobar_sus_propios_correos() -> None:
    """Separación de funciones: quien prepara no aprueba."""
    permisos = ROLE_PERMISSIONS[Role.RECRUITER]
    assert Permission.EMAIL_PREPARE in permisos
    assert Permission.EMAIL_APPROVE not in permisos


# ── Pesos y puntuación ───────────────────────────────────────────────────────


def test_los_pesos_deben_sumar_cien() -> None:
    with pytest.raises(ValueError):
        ScoringWeights(
            weights={ScoringDimension.TECHNICAL: 50.0, ScoringDimension.EXPERIENCE: 30.0}
        )


def test_el_total_se_calcula_con_los_pesos_configurados() -> None:
    pesos = ScoringWeights(
        weights={ScoringDimension.TECHNICAL: 60.0, ScoringDimension.EXPERIENCE: 40.0}
    )
    dimensiones = [
        DimensionScore(dimension=ScoringDimension.TECHNICAL, score=90.0, weight=60.0),
        DimensionScore(dimension=ScoringDimension.EXPERIENCE, score=50.0, weight=40.0),
    ]
    total = ScoringPolicy().compute_total(dimensiones, pesos)
    assert total.value == pytest.approx(74.0)


def test_una_dimension_ausente_se_renormaliza_en_lugar_de_puntuar_cero() -> None:
    """Un fallo del modelo no debe traducirse en una penalización al candidato."""
    pesos = ScoringWeights(
        weights={
            ScoringDimension.TECHNICAL: 50.0,
            ScoringDimension.EXPERIENCE: 30.0,
            ScoringDimension.EDUCATION: 20.0,
        }
    )
    dimensiones = [
        DimensionScore(dimension=ScoringDimension.TECHNICAL, score=80.0, weight=50.0),
        DimensionScore(dimension=ScoringDimension.EXPERIENCE, score=80.0, weight=30.0),
    ]
    total = ScoringPolicy().compute_total(dimensiones, pesos)
    assert total.value == pytest.approx(80.0), (
        "La dimensión que el modelo no puntuó no debe contar como cero"
    )


def test_incumplir_un_filtro_obligatorio_fuerza_el_rechazo() -> None:
    resultado = ScoringPolicy().decide(
        total=Score(value=95.0),
        minimum_score=70.0,
        review_threshold=5.0,
        filter_results=[
            FilterResult(
                filter_label="Inglés B2", field="languages", passed=False, mandatory=True,
                expected="b2", actual="a2", explanation="Por debajo del nivel requerido",
            )
        ],
        extraction=None,
        evidence_verification_rate=1.0,
        bias_detected=False,
        injection_detected=False,
    )
    assert resultado.recommendation is Recommendation.REJECT
    assert resultado.requires_human_review
    assert ReviewReason.HARD_FILTER_FAILED in resultado.review_reasons


def test_la_zona_gris_deriva_a_revision_humana() -> None:
    resultado = ScoringPolicy(auto_shortlist_enabled=True).decide(
        total=Score(value=72.0), minimum_score=70.0, review_threshold=5.0,
        filter_results=[], extraction=None, evidence_verification_rate=1.0,
        bias_detected=False, injection_detected=False,
    )
    assert resultado.recommendation is Recommendation.REVIEW
    assert ReviewReason.SCORE_BORDERLINE in resultado.review_reasons


def test_sin_flag_activo_nada_se_automatiza() -> None:
    """Por defecto, ninguna decisión se toma sin una persona."""
    resultado = ScoringPolicy().decide(
        total=Score(value=95.0), minimum_score=70.0, review_threshold=5.0,
        filter_results=[], extraction=None, evidence_verification_rate=1.0,
        bias_detected=False, injection_detected=False,
    )
    assert resultado.recommendation is Recommendation.SHORTLIST
    assert resultado.requires_human_review


def test_el_sesgo_detectado_bloquea_la_automatizacion() -> None:
    resultado = ScoringPolicy(auto_shortlist_enabled=True).decide(
        total=Score(value=95.0), minimum_score=70.0, review_threshold=5.0,
        filter_results=[], extraction=None, evidence_verification_rate=1.0,
        bias_detected=True, injection_detected=False,
    )
    assert resultado.requires_human_review
    assert ReviewReason.BIAS_DETECTED in resultado.review_reasons


def test_comparacion_explicable_entre_candidatos() -> None:
    """Responde a «¿por qué A y no B?» con datos, no con un número."""
    a = [DimensionScore(dimension=ScoringDimension.TECHNICAL, score=90.0, weight=60.0)]
    b = [DimensionScore(dimension=ScoringDimension.TECHNICAL, score=70.0, weight=60.0)]
    filas = compare_candidates(a, b)
    assert filas[0]["difference"] == pytest.approx(20.0)
    assert filas[0]["weighted_difference"] == pytest.approx(12.0)
