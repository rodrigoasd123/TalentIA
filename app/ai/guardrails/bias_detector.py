"""Guardrail G6 — detección de sesgo en el razonamiento del evaluador.

Dos mecanismos complementarios, porque ninguno basta por separado:

1. **Determinístico** (este módulo, clase ``LexicalBiasDetector``): busca
   menciones de atributos protegidos y de indicadores indirectos en la
   justificación producida por el evaluador. Es rápido, gratuito y no puede ser
   manipulado por el contenido del CV.
2. **Con modelo** (nodo ``bias_check``): un segundo modelo audita el
   razonamiento del primero. Capta formulaciones sutiles que ninguna expresión
   regular detectaría.

Un punto importante: se audita el **razonamiento**, no el CV. Que un CV mencione
la edad del candidato no es un problema del candidato; que la justificación de
su puntuación mencione su edad sí lo es.

El tercer mecanismo, la auditoría estadística de la distribución de
puntuaciones, no vive aquí: opera sobre lotes de evaluaciones, no sobre una.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.enums import Severity

#: Términos que, apareciendo en una justificación, indican que un atributo
#: protegido influyó en el razonamiento. Se agrupan por categoría para poder
#: explicar el hallazgo, no solo señalarlo.
_BIAS_LEXICON: dict[str, tuple[Severity, tuple[str, ...]]] = {
    "age": (Severity.HIGH, (
        r"\bjoven(es)?\b", r"\bmayor(es)?\s+de\s+\d{2}\b", r"\bveterano\b",
        r"\bedad\s+(avanzada|temprana)\b", r"\bgeneraci[óo]n\s+(x|y|z|millennial)\b",
        r"\bdemasiado\s+(joven|mayor)\b", r"\btoo\s+(young|old)\b",
        r"\bpr[óo]ximo\s+a\s+(jubilarse|la\s+jubilaci[óo]n)\b",
        r"\bnativo\s+digital\b", r"\bde\s+la\s+vieja\s+escuela\b",
    )),
    "gender": (Severity.CRITICAL, (
        r"\b(hombre|mujer|var[óo]n|femenin[oa]|masculin[oa])\b",
        r"\b(ella|[ée]l)\s+(podr[íi]a|ser[íi]a|encajar[íi]a)\b",
        r"\bmaternidad\b", r"\bpaternidad\b", r"\bembaraz",
        r"\bcargas?\s+familiares\b",
    )),
    "nationality": (Severity.CRITICAL, (
        r"\bextranjer[oa]\b", r"\bnacionalidad\b", r"\binmigrante\b",
        r"\bpermiso\s+de\s+(trabajo|residencia)\b", r"\bvisa(do)?\b",
        r"\bacento\b", r"\bno\s+es\s+local\b",
    )),
    "ethnicity": (Severity.CRITICAL, (
        r"\betnia\b", r"\braza\b", r"\bind[íi]gena\b", r"\bafro",
        r"\borigen\s+[ée]tnico\b",
    )),
    "religion": (Severity.CRITICAL, (
        r"\breligi[óo]n\b", r"\bcat[óo]lic", r"\bmusulm[áa]n", r"\bjud[íi]o\b",
        r"\bcreencias\s+religiosas\b", r"\bpr[áa]ctica\s+religiosa\b",
    )),
    "disability": (Severity.CRITICAL, (
        r"\bdiscapacidad\b", r"\bminusval", r"\blimitaci[óo]n\s+f[íi]sica\b",
        r"\bcondici[óo]n\s+m[ée]dica\b", r"\benfermedad\b", r"\bsalud\s+mental\b",
    )),
    "marital_status": (Severity.HIGH, (
        r"\bestado\s+civil\b", r"\bsolter[oa]\b", r"\bcasad[oa]\b",
        r"\bdivorciad[oa]\b", r"\bcon\s+hijos\b", r"\bsin\s+hijos\b",
    )),
    "appearance": (Severity.HIGH, (
        r"\bfoto(graf[íi]a)?\b", r"\bapariencia\b", r"\bpresencia\s+f[íi]sica\b",
        r"\baspecto\s+(personal|f[íi]sico)\b", r"\bbuena\s+imagen\b",
    )),
    "socioeconomic_proxy": (Severity.MEDIUM, (
        r"\bbarrio\b", r"\bc[óo]digo\s+postal\b", r"\bzona\s+(humilde|acomodada)\b",
        r"\bnivel\s+socioecon[óo]mico\b", r"\bcolegio\s+privado\b",
        r"\bfamilia\s+de\s+recursos\b",
    )),
    "institution_prestige": (Severity.MEDIUM, (
        r"\buniversidad\s+de\s+(prestigio|[ée]lite|primer\s+nivel)\b",
        r"\bno\s+es\s+una\s+universidad\s+reconocida\b",
        r"\buniversidad\s+de\s+segunda\b", r"\btitulaci[óo]n\s+de\s+poco\s+prestigio\b",
    )),
    "employment_gap": (Severity.MEDIUM, (
        r"\b(hueco|laguna|vac[íi]o|interrupci[óo]n|par[óo]n)\s+"
        r"(laboral|en\s+su\s+(carrera|trayectoria))\b",
        r"\bperiodo\s+sin\s+(trabajar|empleo)\b", r"\bemployment\s+gap\b",
        r"\bdesempleo\s+prolongado\b",
    )),
}

_COMPILED: dict[str, tuple[Severity, tuple[re.Pattern[str], ...]]] = {
    category: (severity, tuple(re.compile(p, re.IGNORECASE) for p in patterns))
    for category, (severity, patterns) in _BIAS_LEXICON.items()
}

_SEVERITY_ORDER = {
    Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2,
    Severity.HIGH: 3, Severity.CRITICAL: 4,
}


@dataclass(slots=True)
class BiasFinding:
    category: str
    severity: Severity
    excerpt: str
    matched_term: str
    explanation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "severity": self.severity.value,
            "excerpt": self.excerpt,
            "matched_term": self.matched_term,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class BiasReport:
    findings: list[BiasFinding] = field(default_factory=list)
    texts_analyzed: int = 0

    @property
    def bias_detected(self) -> bool:
        return bool(self.findings)

    @property
    def max_severity(self) -> Severity:
        if not self.findings:
            return Severity.INFO
        return max((f.severity for f in self.findings), key=lambda s: _SEVERITY_ORDER[s])

    @property
    def categories(self) -> list[str]:
        return sorted({f.category for f in self.findings})

    @property
    def is_blocking(self) -> bool:
        """¿Debe este hallazgo detener la automatización?

        A partir de severidad alta, sí. Un indicador medio (por ejemplo, una
        mención a una interrupción laboral) se registra y se revisa, pero no
        invalida por sí solo la evaluación.
        """
        return _SEVERITY_ORDER[self.max_severity] >= _SEVERITY_ORDER[Severity.HIGH]

    def summary(self) -> str:
        if not self.findings:
            return "No se detectaron indicios de sesgo en el razonamiento."
        return (
            f"Severidad {self.max_severity.value}. "
            f"Categorías: {', '.join(self.categories)}. "
            f"{len(self.findings)} indicio(s) en el razonamiento."
        )


class LexicalBiasDetector:
    """Detección determinística de atributos protegidos en el razonamiento."""

    def analyze(self, texts: dict[str, str]) -> BiasReport:
        """Analiza un conjunto de textos etiquetados por origen.

        Recibe un diccionario (por ejemplo ``{"dimension:technical": "..."}``)
        para poder decir no solo *qué* se detectó, sino *dónde*.
        """
        report = BiasReport(texts_analyzed=len(texts))
        for label, text in texts.items():
            if not text:
                continue
            for category, (severity, patterns) in _COMPILED.items():
                for pattern in patterns:
                    match = pattern.search(text)
                    if match is None:
                        continue
                    report.findings.append(
                        BiasFinding(
                            category=category,
                            severity=severity,
                            excerpt=self._excerpt(text, match.start(), match.end()),
                            matched_term=match.group(0),
                            explanation=(
                                f"El razonamiento de «{label}» menciona un elemento de la "
                                f"categoría «{category}», que no es pertinente para evaluar "
                                "la idoneidad profesional."
                            ),
                        )
                    )
                    break  # Un hallazgo por categoría y texto es suficiente.
        return report

    @staticmethod
    def _excerpt(text: str, start: int, end: int, window: int = 70) -> str:
        left = max(0, start - window)
        right = min(len(text), end + window)
        return (
            ("…" if left > 0 else "")
            + text[left:right].replace("\n", " ").strip()
            + ("…" if right < len(text) else "")
        )


def collect_reasoning_texts(evaluation: object) -> dict[str, str]:
    """Extrae de una evaluación todos los textos que deben auditarse.

    Acepta tanto la salida cruda del modelo como la entidad persistida, porque
    el detector se usa en ambos momentos del flujo.
    """
    texts: dict[str, str] = {}
    dimensions = getattr(evaluation, "dimensions", None) or getattr(
        evaluation, "dimension_scores", []
    )
    for dimension in dimensions:
        key = getattr(dimension, "dimension", "")
        name = getattr(key, "value", key)
        reasoning = getattr(dimension, "reasoning", "")
        if reasoning:
            texts[f"dimension:{name}"] = reasoning
    if summary := getattr(evaluation, "summary", ""):
        texts["summary"] = summary
    for index, item in enumerate(getattr(evaluation, "strengths", []) or []):
        texts[f"strength:{index}"] = str(item)
    for index, item in enumerate(getattr(evaluation, "gaps", []) or []):
        texts[f"gap:{index}"] = str(item)
    return texts


__all__ = [
    "BiasFinding", "BiasReport", "LexicalBiasDetector", "collect_reasoning_texts",
]
