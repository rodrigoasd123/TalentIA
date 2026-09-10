"""Guardrail G5 — verificación de evidencia contra el texto fuente.

Este es el guardrail que más distingue a VERA de un sistema que simplemente
"puntúa CVs con IA". Un modelo puede producir una justificación convincente de
una experiencia que el candidato nunca tuvo, y esa justificación es
indistinguible de una real si nadie la comprueba.

La regla: **toda cita debe existir en el documento**. Si el modelo afirma que
el candidato usó Kubernetes en un proyecto, esa afirmación tiene que poder
localizarse en el CV. Cuando la proporción de citas no localizables supera el
umbral, la evaluación se descarta y el caso pasa a una persona.

La comparación es difusa por necesidad: el modelo parafrasea, reordena y
normaliza mayúsculas. Exigir coincidencia exacta produciría un falso positivo
constante. Se usa una cascada de estrategias, de la más estricta a la más
permisiva, y se registra con cuál se validó cada cita.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.ai.schemas import CandidateEvaluationOutput, EvidenceItem
from app.domain.entities import ResumeExtraction
from app.domain.enums import ScoringDimension
from app.domain.value_objects import EvidenceSpan

#: Umbral de similitud a partir del cual una cita se considera localizada.
#: 0.85 tolera parafraseo leve sin admitir invención.
DEFAULT_MATCH_THRESHOLD = 0.85

#: Umbral más laxo para citas cortas, donde una diferencia de una palabra
#: hunde la similitud sin que haya invención real.
SHORT_QUOTE_THRESHOLD = 0.78
SHORT_QUOTE_MAX_WORDS = 6

_WORD_RE = re.compile(r"[\wáéíóúñü+#.]+", re.IGNORECASE)


def normalize_for_match(text: str) -> str:
    """Normaliza para comparar: sin acentos, sin puntuación, espacios colapsados."""
    lowered = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in lowered if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s+#.]", " ", stripped)).strip()


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(normalize_for_match(text))


@dataclass(slots=True)
class VerifiedEvidence:
    """Una cita y el resultado de buscarla en el documento."""

    quote: str
    dimension: ScoringDimension
    verified: bool
    match_ratio: float
    strategy: str
    source_offset: int | None = None

    def to_span(self) -> EvidenceSpan:
        return EvidenceSpan(
            quote=self.quote,
            dimension=self.dimension,
            verified=self.verified,
            match_ratio=round(self.match_ratio, 3),
            source_offset=self.source_offset,
        )


@dataclass(slots=True)
class VerificationReport:
    """Informe agregado sobre toda la evidencia de una evaluación."""

    items: list[VerifiedEvidence] = field(default_factory=list)
    threshold: float = DEFAULT_MATCH_THRESHOLD

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def verified_count(self) -> int:
        return sum(1 for i in self.items if i.verified)

    @property
    def verification_rate(self) -> float:
        """Proporción de citas localizadas.

        Una evaluación sin ninguna evidencia devuelve 0.0, no 1.0: la ausencia
        de evidencia no puede computar como evidencia perfecta.
        """
        if not self.items:
            return 0.0
        return self.verified_count / self.total

    @property
    def unverified(self) -> list[VerifiedEvidence]:
        return [i for i in self.items if not i.verified]

    def passes(self, max_unverified_ratio: float) -> bool:
        if not self.items:
            return False
        return (1 - self.verification_rate) <= max_unverified_ratio

    def summary(self) -> str:
        if not self.items:
            return "El modelo no aportó ninguna evidencia."
        return (
            f"{self.verified_count} de {self.total} citas verificadas "
            f"({self.verification_rate:.0%})."
            + (f" No localizadas: {len(self.unverified)}." if self.unverified else "")
        )


class EvidenceVerifier:
    """Comprueba que cada cita del modelo existe realmente en el CV."""

    def __init__(self, *, threshold: float = DEFAULT_MATCH_THRESHOLD) -> None:
        self.threshold = threshold

    def verify_evaluation(
        self,
        evaluation: CandidateEvaluationOutput,
        *,
        source_text: str,
        extraction: ResumeExtraction | None = None,
    ) -> VerificationReport:
        report = VerificationReport(threshold=self.threshold)
        haystack = normalize_for_match(source_text)
        haystack_tokens = set(tokenize(source_text))
        structured = self._structured_corpus(extraction)

        for item in evaluation.all_evidence:
            report.items.append(
                self._verify_item(item, haystack, haystack_tokens, structured)
            )
        return report

    def verify_quote(self, quote: str, source_text: str) -> VerifiedEvidence:
        """Verifica una cita suelta. Útil para tests y para la interfaz."""
        return self._verify_item(
            EvidenceItem(quote=quote, dimension="technical"),
            normalize_for_match(source_text),
            set(tokenize(source_text)),
            "",
        )

    # ── Cascada de estrategias ───────────────────────────────────────────────

    def _verify_item(
        self,
        item: EvidenceItem,
        haystack: str,
        haystack_tokens: set[str],
        structured: str,
    ) -> VerifiedEvidence:
        dimension = ScoringDimension(item.dimension)
        needle = normalize_for_match(item.quote)
        if not needle:
            return VerifiedEvidence(item.quote, dimension, False, 0.0, "cita vacía")

        tokens = tokenize(item.quote)
        threshold = (
            SHORT_QUOTE_THRESHOLD if len(tokens) <= SHORT_QUOTE_MAX_WORDS else self.threshold
        )

        # 1. Coincidencia literal tras normalizar. Lo más habitual y lo más fuerte.
        offset = haystack.find(needle)
        if offset >= 0:
            return VerifiedEvidence(item.quote, dimension, True, 1.0, "literal", offset)

        # 2. Coincidencia contra los datos ya extraídos y estructurados.
        if structured and needle in structured:
            return VerifiedEvidence(item.quote, dimension, True, 0.98, "datos extraídos")

        # 3. Cobertura de términos: todos los términos significativos presentes.
        coverage = self._token_coverage(tokens, haystack_tokens)
        if coverage >= 0.95:
            return VerifiedEvidence(item.quote, dimension, True, coverage, "cobertura de términos")

        # 4. Similitud difusa contra la ventana más parecida del documento.
        ratio, window_offset = self._best_window_ratio(needle, haystack)
        if ratio >= threshold:
            return VerifiedEvidence(item.quote, dimension, True, ratio, "difusa", window_offset)

        best = max(ratio, coverage)
        return VerifiedEvidence(item.quote, dimension, False, best, "no localizada")

    @staticmethod
    def _token_coverage(tokens: list[str], haystack_tokens: set[str]) -> float:
        """Proporción de términos significativos de la cita presentes en el CV.

        Se descartan las palabras muy cortas: su presencia no aporta evidencia y
        distorsionaría la proporción al alza.
        """
        meaningful = [t for t in tokens if len(t) > 2]
        if not meaningful:
            return 0.0
        found = sum(1 for t in meaningful if t in haystack_tokens)
        return found / len(meaningful)

    @staticmethod
    def _best_window_ratio(needle: str, haystack: str) -> tuple[float, int | None]:
        """Compara la cita contra ventanas deslizantes del documento.

        Comparar contra el documento entero daría una similitud ínfima siempre.
        La ventana se dimensiona en función de la cita y avanza a saltos de un
        tercio para no multiplicar el coste sin necesidad.
        """
        if not needle or not haystack:
            return 0.0, None
        window = max(len(needle), 40)
        step = max(1, window // 3)
        best_ratio = 0.0
        best_offset: int | None = None
        matcher = SequenceMatcher(None, needle, "", autojunk=False)
        for start in range(0, max(1, len(haystack) - window + 1), step):
            fragment = haystack[start : start + window]
            matcher.set_seq2(fragment)
            # quick_ratio acota por arriba: si ya es peor que lo mejor hallado,
            # no merece la pena calcular la similitud completa.
            if matcher.quick_ratio() <= best_ratio:
                continue
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_offset = start
        return best_ratio, best_offset

    @staticmethod
    def _structured_corpus(extraction: ResumeExtraction | None) -> str:
        """Texto plano con lo ya extraído, como fuente secundaria de verificación.

        Cubre el caso en que el modelo cita un dato que sí está en el CV pero
        expresado de forma muy distinta, y que la extracción ya normalizó.
        """
        if extraction is None:
            return ""
        parts: list[str] = [
            *extraction.skills,
            *extraction.technologies,
            *extraction.certifications,
            extraction.current_role,
            extraction.seniority,
        ]
        for exp in extraction.experiences:
            parts.extend([exp.company, exp.role, exp.description, *exp.technologies])
        for edu in extraction.education:
            parts.extend([edu.degree, edu.field_of_study, edu.institution, edu.level])
        for lang in extraction.languages:
            parts.append(f"{lang.language} {lang.level.value}")
        return normalize_for_match(" ".join(p for p in parts if p))


def build_evidence_spans(
    evaluation: CandidateEvaluationOutput, report: VerificationReport
) -> dict[str, list[EvidenceSpan]]:
    """Agrupa la evidencia verificada por dimensión, lista para persistir."""
    by_dimension: dict[str, list[EvidenceSpan]] = {}
    index = 0
    for dimension in evaluation.dimensions:
        spans: list[EvidenceSpan] = []
        for _ in dimension.evidence:
            if index < len(report.items):
                spans.append(report.items[index].to_span())
                index += 1
        by_dimension[dimension.dimension] = spans
    return by_dimension


__all__ = [
    "DEFAULT_MATCH_THRESHOLD", "EvidenceVerifier", "VerificationReport",
    "VerifiedEvidence", "build_evidence_spans", "normalize_for_match", "tokenize",
]
