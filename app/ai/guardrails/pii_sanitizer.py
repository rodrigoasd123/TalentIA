"""Guardrail G3 — anonimización de datos personales antes del modelo.

La frontera que cruza este módulo es la más importante del sistema en términos
de cumplimiento: todo lo que sale por aquí va a un servicio externo.

El enfoque es de **lista de permitidos invertida**: no intentamos adivinar qué
es sensible, sino que retiramos categorías completas conocidas y sustituimos
cada valor por un token estable. El mapa de tokens se queda en el backend y
nunca acompaña al texto.

Un detalle deliberado: se retiran también los nombres de instituciones
educativas y los años de graduación cuando la política lo exige. No son datos
personales en sentido estricto, pero funcionan como indicadores indirectos de
clase social y de edad, y una evaluación que se apoye en ellos es exactamente
el tipo de sesgo que este sistema debe evitar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.enums import PIICategory

# ── Patrones de detección ────────────────────────────────────────────────────
# Se ordenan de más específico a más general: el correo debe capturarse antes
# que el teléfono, porque un correo puede contener dígitos.

_PATTERNS: tuple[tuple[PIICategory, re.Pattern[str]], ...] = (
    (PIICategory.EMAIL, re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    (PIICategory.URL_PROFILE, re.compile(
        r"\b(?:https?://)?(?:www\.)?"
        r"(?:linkedin\.com/in/|github\.com/|gitlab\.com/|twitter\.com/|x\.com/)"
        r"[\w\-./]+", re.IGNORECASE)),
    (PIICategory.NATIONAL_ID, re.compile(
        r"\b(?:dni|nif|nie|cedula|cédula|c\.?i\.?|rut|curp|documento|pasaporte|passport)"
        r"\s*[:.\-]?\s*[\dA-Za-z][\dA-Za-z\-.]{5,14}\b", re.IGNORECASE)),
    # El teléfono exige una señal explícita: una etiqueta, un prefijo
    # internacional o una agrupación de tres bloques. Un patrón más laxo
    # devoraría rangos de años como "2019 - 2021", que son información
    # profesional legítima y necesaria para evaluar la experiencia.
    (PIICategory.PHONE, re.compile(
        # Los separadores admiten espacios pero nunca saltos de línea: un `\s`
        # aquí se comería la línea siguiente junto con el teléfono.
        r"(?:tel[ée]fono|tel|m[óo]vil|cel(?:ular)?|phone|whatsapp)[ \t]*[:.\-]?[ \t]*"
        r"\+?[\d .\-()]{7,20}"
        r"|\+\d{1,3}[\s.\-]?(?:\(?\d{1,4}\)?[\s.\-]?){1,4}\d{2,4}"
        r"|\b\d{3}[\s.\-]\d{3}[\s.\-]\d{3,4}\b",
        re.IGNORECASE)),
    (PIICategory.BIRTH_DATE, re.compile(
        r"\b(?:fecha\s+de\s+nacimiento|nacid[oa]\s+(?:el|en)|birth\s*date|date\s+of\s+birth|dob)"
        r"\s*[:.\-]?\s*[\d]{1,4}[/\-\s][\d]{1,2}[/\-\s][\d]{2,4}", re.IGNORECASE)),
    (PIICategory.AGE, re.compile(
        r"\b(?:edad|age)\s*[:.\-]?\s*\d{1,2}\s*(?:a[ñn]os|years?)?\b|"
        r"\b\d{2}\s*a[ñn]os\s+de\s+edad\b", re.IGNORECASE)),
    (PIICategory.GENDER, re.compile(
        r"\b(?:g[ée]nero|sexo|gender|sex)\s*[:.\-]?\s*"
        r"(?:m|f|masculino|femenino|male|female|hombre|mujer|no\s+binario)\b", re.IGNORECASE)),
    (PIICategory.MARITAL_STATUS, re.compile(
        r"\b(?:estado\s+civil|marital\s+status)\s*[:.\-]?\s*"
        r"(?:solter[oa]|casad[oa]|divorciad[oa]|viud[oa]|uni[óo]n\s+libre|single|married|divorced)\b",
        re.IGNORECASE)),
    (PIICategory.NATIONALITY, re.compile(
        r"\b(?:nacionalidad|nationality|ciudadan[íi]a|citizenship)\s*[:.\-]?\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]+",
        re.IGNORECASE)),
    (PIICategory.RELIGION, re.compile(
        r"\b(?:religi[óo]n|religion|creencias?)\s*[:.\-]?\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]+",
        re.IGNORECASE)),
    (PIICategory.HEALTH, re.compile(
        r"\b(?:discapacidad|disability|condici[óo]n\s+m[ée]dica|estado\s+de\s+salud|"
        r"certificado\s+de\s+discapacidad)\s*[:.\-]?\s*[^\n]{0,60}", re.IGNORECASE)),
    (PIICategory.PHOTO, re.compile(
        r"\b(?:foto(?:graf[íi]a)?|photo(?:graph)?|imagen\s+de\s+perfil)\s*[:.\-]?\s*[^\n]{0,40}",
        re.IGNORECASE)),
    (PIICategory.ADDRESS, re.compile(
        r"\b(?:direcci[óo]n|domicilio|address)\s*[:.\-]?\s*[^\n]{5,90}", re.IGNORECASE)),
)

#: Etiquetas que suelen preceder al nombre del candidato en la cabecera del CV.
_NAME_LABEL_RE = re.compile(
    r"^\s*(?:nombre(?:\s+completo)?|name|candidat[oa])\s*[:.\-]\s*(.{3,80})$",
    re.IGNORECASE | re.MULTILINE,
)

#: Instituciones educativas: se sustituyen por su tipo genérico para conservar
#: el nivel formativo sin arrastrar el prestigio de la marca.
_INSTITUTION_RE = re.compile(
    r"\b(?:universidad|university|universidade|instituto\s+tecnol[óo]gico|"
    r"colegio\s+mayor|escuela\s+polit[ée]cnica|tecnol[óo]gico\s+de)\s+"
    r"[A-ZÁÉÍÓÚÑ][\w\sÁÉÍÓÚÑáéíóúñ.'-]{2,50}",
    re.IGNORECASE,
)


@dataclass(slots=True)
class PIIMatch:
    category: PIICategory
    original: str
    token: str
    start: int


@dataclass(slots=True)
class AnonymizationResult:
    """Texto anonimizado y el mapa para rehidratarlo, que nunca sale del backend."""

    anonymized_text: str
    pii_map: dict[str, str] = field(default_factory=dict)
    matches: list[PIIMatch] = field(default_factory=list)
    categories_found: set[PIICategory] = field(default_factory=set)

    @property
    def redaction_count(self) -> int:
        return len(self.matches)

    def rehydrate(self, text: str) -> str:
        """Devuelve los valores reales. Solo para mostrar a una persona autorizada."""
        out = text
        for token, original in self.pii_map.items():
            out = out.replace(token, original)
        return out

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for match in self.matches:
            counts[match.category.value] = counts.get(match.category.value, 0) + 1
        return counts


class PIISanitizer:
    """Retira información personal antes de que el texto cruce hacia el modelo."""

    def __init__(
        self,
        *,
        anonymize_institutions: bool = True,
        anonymize_graduation_years: bool = True,
        candidate_name: str | None = None,
    ) -> None:
        self.anonymize_institutions = anonymize_institutions
        self.anonymize_graduation_years = anonymize_graduation_years
        self.candidate_name = candidate_name

    def anonymize(self, text: str) -> AnonymizationResult:
        """Sustituye cada dato personal por un token estable y numerado."""
        result = AnonymizationResult(anonymized_text=text)
        counters: dict[PIICategory, int] = {}
        working = text

        # El orden importa. Los patrones estructurados van primero porque el
        # nombre suele estar contenido dentro de ellos: sustituir "Ana Ramírez"
        # antes que "ana.ramirez@example.com" dejaría el correo destrozado
        # ("[NAME_1].[NAME_1]@example.com") en lugar de anonimizado.
        for category, pattern in _PATTERNS:
            working = self._replace_pattern(working, pattern, category, result, counters)

        if self.candidate_name:
            working = self._replace_known_name(working, result, counters)

        working = self._replace_labelled_name(working, result, counters)

        if self.anonymize_institutions:
            working = self._replace_institutions(working, result, counters)

        if self.anonymize_graduation_years:
            working = self._replace_graduation_years(working)

        result.anonymized_text = working
        result.categories_found = {m.category for m in result.matches}
        return result

    # ── Sustituciones ────────────────────────────────────────────────────────

    def _token(self, category: PIICategory, counters: dict[PIICategory, int]) -> str:
        counters[category] = counters.get(category, 0) + 1
        return f"[{category.value.upper()}_{counters[category]}]"

    def _register(
        self,
        result: AnonymizationResult,
        category: PIICategory,
        original: str,
        token: str,
        start: int,
    ) -> None:
        result.pii_map[token] = original
        result.matches.append(
            PIIMatch(category=category, original=original, token=token, start=start)
        )

    def _replace_known_name(
        self, text: str, result: AnonymizationResult, counters: dict[PIICategory, int]
    ) -> str:
        """Retira el nombre completo y también cada uno de sus componentes.

        Un CV cita el nombre completo una vez y luego solo el nombre de pila en
        la firma o en el correo. Retirar únicamente la forma completa dejaría el
        resto visible.
        """
        assert self.candidate_name is not None
        token = self._token(PIICategory.NAME, counters)
        parts = [p for p in self.candidate_name.split() if len(p) > 2]
        candidates = sorted({self.candidate_name, *parts}, key=len, reverse=True)
        out = text
        registered = False
        for part in candidates:
            pattern = re.compile(rf"\b{re.escape(part)}\b", re.IGNORECASE)
            if pattern.search(out):
                if not registered:
                    self._register(result, PIICategory.NAME, self.candidate_name, token, 0)
                    registered = True
                out = pattern.sub(token, out)
        return out

    def _replace_labelled_name(
        self, text: str, result: AnonymizationResult, counters: dict[PIICategory, int]
    ) -> str:
        out = text
        for match in _NAME_LABEL_RE.finditer(text):
            value = match.group(1).strip()
            if not value or value.startswith("["):
                continue
            token = self._token(PIICategory.NAME, counters)
            self._register(result, PIICategory.NAME, value, token, match.start(1))
            out = out.replace(value, token)
        return out

    def _replace_pattern(
        self,
        text: str,
        pattern: re.Pattern[str],
        category: PIICategory,
        result: AnonymizationResult,
        counters: dict[PIICategory, int],
    ) -> str:
        def _sub(match: re.Match[str]) -> str:
            original = match.group(0)
            if original.startswith("["):  # ya anonimizado en una pasada previa
                return original
            token = self._token(category, counters)
            self._register(result, category, original, token, match.start())
            return token

        return pattern.sub(_sub, text)

    def _replace_institutions(
        self, text: str, result: AnonymizationResult, counters: dict[PIICategory, int]
    ) -> str:
        def _sub(match: re.Match[str]) -> str:
            original = match.group(0)
            counters[PIICategory.ADDRESS] = counters.get(PIICategory.ADDRESS, 0)
            token = "[INSTITUCION_EDUCATIVA]"
            result.pii_map.setdefault(f"{token}#{len(result.matches)}", original)
            result.matches.append(
                PIIMatch(
                    category=PIICategory.ADDRESS,
                    original=original,
                    token=token,
                    start=match.start(),
                )
            )
            return token

        return _INSTITUTION_RE.sub(_sub, text)

    @staticmethod
    def _replace_graduation_years(text: str) -> str:
        """Sustituye años de titulación por su década.

        El año exacto de graduación permite inferir la edad con bastante
        precisión. La década conserva la información útil (cuánto hace que se
        formó) sin ser un indicador directo de edad.
        """

        def _sub(match: re.Match[str]) -> str:
            year = int(match.group(1))
            return f"{match.group(0)[: match.start(1) - match.start(0)]}(década de {year // 10 * 10})"

        return re.sub(
            r"(?:graduaci[óo]n|titulaci[óo]n|egreso|graduated|graduation)\s*[:.\-]?\s*(\d{4})\b",
            _sub,
            text,
            flags=re.IGNORECASE,
        )


def assert_no_pii(payload: str, *, forbidden_values: list[str]) -> list[str]:
    """Comprueba que ningún valor prohibido aparece en el texto que va al modelo.

    Es la función que usa el test de frontera. Devuelve la lista de valores
    filtrados: si no está vacía, el build debe fallar. Existe como función del
    sistema, y no solo como test, para poder ejecutarla también en tiempo de
    ejecución antes de cada llamada real.
    """
    leaked: list[str] = []
    haystack = payload.lower()
    for value in forbidden_values:
        needle = (value or "").strip().lower()
        if len(needle) < 4:
            continue
        if needle in haystack:
            leaked.append(value)
    return leaked


__all__ = [
    "AnonymizationResult", "PIIMatch", "PIISanitizer", "assert_no_pii",
]
