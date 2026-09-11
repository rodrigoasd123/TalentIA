"""Filtros determinísticos de admisión.

Este módulo no importa nada de la capa de IA y nunca lo hará. Es la parte del
sistema que decide "cumple o no cumple" y debe ser reproducible al carácter:
el mismo candidato y los mismos criterios producen siempre el mismo resultado,
hoy y dentro de dos años.

Motivo de fondo: un filtro obligatorio es una exclusión. Una exclusión que
depende de un modelo probabilístico es una exclusión que no se puede defender
ante el candidato ni ante una auditoría.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.domain.entities import ResumeExtraction
from app.domain.enums import (
    LANGUAGE_LEVEL_ORDER,
    CriterionStatus,
    FilterOperator,
    LanguageLevel,
)
from app.domain.value_objects import FilterResult, HardFilter

#: Sinónimos habituales para que "JS" y "JavaScript" no cuenten como cosas
#: distintas. Es un catálogo pequeño y explícito a propósito: normalizar con un
#: modelo reintroduciría el no determinismo que este módulo evita.
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript", "ts": "typescript", "py": "python",
    "postgres": "postgresql", "psql": "postgresql", "pg": "postgresql",
    "k8s": "kubernetes", "gcp": "google cloud", "aws cloud": "aws",
    "node": "nodejs", "node.js": "nodejs", "react.js": "react",
    "vue.js": "vue", "c#": "csharp", "c++": "cpp", ".net": "dotnet",
    "ml": "machine learning", "ai": "inteligencia artificial",
    "restful": "rest", "rest api": "rest", "ci cd": "cicd", "ci/cd": "cicd",
}


def normalize_term(term: str) -> str:
    """Normaliza una habilidad para poder compararla.

    Quita acentos, pasa a minúsculas, colapsa separadores y aplica alias. Sin
    esta normalización, "Postgres" y "PostgreSQL" producirían un falso negativo
    que excluiría a un candidato válido.
    """
    text = unicodedata.normalize("NFKD", term.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[_/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return SKILL_ALIASES.get(text, text)


def normalize_terms(terms: object) -> set[str]:
    if isinstance(terms, str):
        return {normalize_term(terms)}
    if isinstance(terms, (list, tuple, set)):
        return {normalize_term(str(t)) for t in terms if str(t).strip()}
    return set()


class CandidateFacts:
    """Vista plana del candidato sobre la que operan los filtros.

    Aísla los filtros de la forma concreta de ``ResumeExtraction``: si mañana
    cambia la estructura de extracción, solo hay que tocar esta clase.
    """

    def __init__(self, extraction: ResumeExtraction) -> None:
        self._extraction = extraction
        self._skills = {normalize_term(s) for s in extraction.normalized_skills()}
        # Las tecnologías citadas dentro de cada experiencia también cuentan:
        # es habitual que un CV no repita en "skills" lo que ya detalló arriba.
        for exp in extraction.experiences:
            self._skills.update(normalize_term(t) for t in exp.technologies)
        self._certifications = {normalize_term(c) for c in extraction.certifications}
        self._languages = {ls.language: ls.level for ls in extraction.languages}

    @property
    def years_experience(self) -> float:
        return self._extraction.total_years_experience

    @property
    def skills(self) -> set[str]:
        return self._skills

    @property
    def certifications(self) -> set[str]:
        return self._certifications

    @property
    def education_levels(self) -> set[str]:
        return {normalize_term(e.level) for e in self._extraction.education if e.level}

    @property
    def availability(self) -> str:
        return normalize_term(self._extraction.availability)

    def language_level(self, language: str) -> LanguageLevel | None:
        return self._languages.get(normalize_term(language))

    def get(self, field: str) -> Any:
        """Resuelve el nombre de campo declarado en el filtro."""
        mapping: dict[str, Any] = {
            "years_experience": self.years_experience,
            "total_years_experience": self.years_experience,
            "skills": self.skills,
            "technologies": self.skills,
            "certifications": self.certifications,
            "education_level": self.education_levels,
            "availability": self.availability,
            "seniority": normalize_term(self._extraction.seniority),
        }
        return mapping.get(field)


class HardFilterEngine:
    """Aplica los filtros de una vacante a los datos extraídos de un CV."""

    def evaluate(
        self, filters: list[HardFilter], extraction: ResumeExtraction
    ) -> list[FilterResult]:
        facts = CandidateFacts(extraction)
        return [self._apply(f, facts) for f in filters]

    def _apply(self, hard_filter: HardFilter, facts: CandidateFacts) -> FilterResult:
        handler = _HANDLERS.get(hard_filter.operator)
        if handler is None:  # pragma: no cover — protegido por el validador del VO
            return FilterResult(
                filter_label=hard_filter.label, field=hard_filter.field, passed=False,
                mandatory=hard_filter.mandatory, expected=hard_filter.value, actual=None,
                explanation=f"Operador no soportado: {hard_filter.operator.value}",
            )
        passed, actual, explanation = handler(hard_filter, facts)
        status = (
            CriterionStatus.PASSED
            if passed
            else CriterionStatus.UNVERIFIED
            if actual is None
            else CriterionStatus.FAILED
        )
        return FilterResult(
            filter_label=hard_filter.label,
            field=hard_filter.field,
            passed=passed,
            mandatory=hard_filter.mandatory,
            expected=hard_filter.value,
            actual=actual,
            explanation=explanation,
            status=status,
            mode=hard_filter.effective_mode,
            penalty_percent=hard_filter.effective_penalty_percent,
        )

    @staticmethod
    def all_mandatory_passed(results: list[FilterResult]) -> bool:
        return not any(r.mandatory and r.is_blocking for r in results)

    @staticmethod
    def failed_mandatory(results: list[FilterResult]) -> list[FilterResult]:
        return [r for r in results if r.mandatory and r.is_blocking]

    @staticmethod
    def missing_requirements(results: list[FilterResult]) -> list[str]:
        return [r.filter_label for r in results if not r.passed]


# ── Manejadores por operador ─────────────────────────────────────────────────
# Cada uno devuelve (cumple, valor_real, explicación). La explicación se muestra
# al recruiter y al candidato, así que se escribe en lenguaje llano.


def _op_gte(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    actual = facts.get(f.field)
    if actual is None:
        return False, None, f"No se encontró información sobre {f.field}"
    ok = float(actual) >= float(f.value)
    verb = "cumple" if ok else "no alcanza"
    return ok, actual, f"{actual} {verb} el mínimo requerido de {f.value}"


def _op_lte(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    actual = facts.get(f.field)
    if actual is None:
        return False, None, f"No se encontró información sobre {f.field}"
    ok = float(actual) <= float(f.value)
    return ok, actual, f"{actual} {'no supera' if ok else 'supera'} el máximo de {f.value}"


def _op_equals(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    actual = facts.get(f.field)
    expected = normalize_term(str(f.value))
    if isinstance(actual, set):
        ok = expected in actual
        return ok, sorted(actual), f"{'Coincide' if ok else 'No coincide'} con «{f.value}»"
    ok = normalize_term(str(actual)) == expected
    return ok, actual, f"{'Coincide' if ok else 'No coincide'} con «{f.value}»"


def _op_contains_all(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    required = normalize_terms(f.value)
    present = facts.get(f.field) or set()
    if not isinstance(present, set):
        present = normalize_terms(present)
    missing = sorted(required - present)
    ok = not missing
    explanation = (
        "Están presentes todas las requeridas"
        if ok
        else f"Faltan: {', '.join(missing)}"
    )
    return ok, sorted(required & present), explanation


def _op_contains_any(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    required = normalize_terms(f.value)
    present = facts.get(f.field) or set()
    if not isinstance(present, set):
        present = normalize_terms(present)
    found = sorted(required & present)
    ok = bool(found)
    explanation = (
        f"Encontradas: {', '.join(found)}"
        if ok
        else f"No se encontró ninguna de: {', '.join(sorted(required))}"
    )
    return ok, found, explanation


def _op_in(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    allowed = normalize_terms(f.value)
    actual = facts.get(f.field)
    actual_set = actual if isinstance(actual, set) else normalize_terms(actual)
    found = sorted(allowed & actual_set)
    ok = bool(found)
    return ok, found, (
        f"«{', '.join(found)}» está entre los valores admitidos"
        if ok
        else f"Ninguno de los valores admitidos ({', '.join(sorted(allowed))}) está presente"
    )


def _op_min_level(f: HardFilter, facts: CandidateFacts) -> tuple[bool, Any, str]:
    spec = dict(f.value)
    language = str(spec.get("language", ""))
    required = LanguageLevel(str(spec.get("level", "b1")).lower())
    actual = facts.language_level(language)
    if actual is None:
        return False, None, f"No se declara nivel de {language}"
    ok = LANGUAGE_LEVEL_ORDER[actual] >= LANGUAGE_LEVEL_ORDER[required]
    return ok, actual.value, (
        f"Nivel de {language}: {actual.value.upper()} "
        f"({'cumple' if ok else 'por debajo de'} {required.value.upper()})"
    )


_HANDLERS = {
    FilterOperator.GTE: _op_gte,
    FilterOperator.LTE: _op_lte,
    FilterOperator.EQUALS: _op_equals,
    FilterOperator.CONTAINS_ALL: _op_contains_all,
    FilterOperator.CONTAINS_ANY: _op_contains_any,
    FilterOperator.IN: _op_in,
    FilterOperator.MIN_LEVEL: _op_min_level,
}


__all__ = ["SKILL_ALIASES", "CandidateFacts", "HardFilterEngine", "normalize_term", "normalize_terms"]
