"""Adaptador de LLM simulado.

Cumple dos funciones que no son intercambiables:

1. **Permitir que VERA funcione sin API key.** El laboratorio arranca, el grafo
   se ejecuta de principio a fin y la interfaz se puede recorrer entera antes de
   configurar ningún proveedor.
2. **Hacer los tests deterministas.** Una suite que dependa de un modelo real es
   lenta, cara e inestable, y acaba desactivándose.

No es un generador de texto aleatorio: analiza el documento con reglas y produce
salidas coherentes con su contenido, **citando fragmentos literales**. Esto
importa porque significa que el verificador de evidencia se ejercita de verdad
durante los tests, en lugar de validarse contra citas fabricadas.

Nunca debe usarse en producción. ``is_configured`` devuelve ``True`` porque el
grafo debe poder ejecutarse, pero ``provider`` lo identifica como simulado y la
interfaz lo señala de forma visible.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.llm.base import LLMResponse

logger = get_logger(__name__)

#: Tecnologías que el simulador sabe reconocer en un CV.
_KNOWN_TECHNOLOGIES = (
    "python", "java", "javascript", "typescript", "go", "rust", "csharp", "php",
    "ruby", "kotlin", "swift", "scala", "sql", "fastapi", "django", "flask",
    "spring", "express", "nodejs", "react", "angular", "vue", "next.js",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "sqlite",
    "aws", "azure", "google cloud", "docker", "kubernetes", "terraform",
    "jenkins", "gitlab", "github actions", "cicd", "linux", "nginx", "kafka",
    "rabbitmq", "graphql", "rest", "grpc", "pandas", "numpy", "pytorch",
    "tensorflow", "scikit-learn", "spark", "airflow", "dbt", "power bi",
    "tableau", "langchain", "machine learning", "microservicios", "pytest",
    "git", "agile", "scrum", "prometheus", "grafana", "openapi", "celery",
)

_YEARS_RE = re.compile(
    r"(\d{1,2}(?:[.,]\d)?)\s*(?:\+\s*)?a[ñn]os?\s+(?:de\s+)?(?:experiencia|exp\b)",
    re.IGNORECASE,
)
_SENIORITY_HINTS = (
    ("principal", "principal"), ("staff", "principal"),
    ("lead", "lead"), ("líder", "lead"), ("jefe", "lead"),
    ("senior", "senior"), ("sr.", "senior"),
    ("semi", "semi_senior"), ("ssr", "semi_senior"), ("mid", "semi_senior"),
    ("junior", "junior"), ("jr.", "junior"), ("trainee", "junior"),
)
_LANGUAGE_HINTS = (
    ("inglés", "english"), ("ingles", "english"), ("english", "english"),
    ("español", "spanish"), ("espanol", "spanish"), ("spanish", "spanish"),
    ("portugués", "portuguese"), ("frances", "french"), ("francés", "french"),
    ("alemán", "german"), ("aleman", "german"),
)
_LEVEL_RE = re.compile(r"\b(a1|a2|b1|b2|c1|c2|nativ[oa]|native|bilingüe|bilingue)\b", re.IGNORECASE)
_EDUCATION_RE = re.compile(
    r"(ingenier[íi]a|licenciatura|grado|m[áa]ster|maestr[íi]a|doctorado|t[ée]cnico|"
    r"tecn[óo]logo|bachelor|master|phd)[^\n.]{0,80}",
    re.IGNORECASE,
)
_CERT_RE = re.compile(
    r"((?:aws|azure|google|gcp|scrum|pmp|cisco|oracle|comptia|kubernetes|cka)"
    r"[^\n,;.]{0,60}(?:certif|associate|professional|master|practitioner|foundation)[^\n,;.]{0,30}"
    r"|certificaci[óo]n[^\n,;.]{3,60})",
    re.IGNORECASE,
)


class MockLLMAdapter:
    """Simulador determinista basado en reglas sobre el texto real."""

    provider = "mock"

    def __init__(self, model: str = "mock", *, fail_on: str | None = None) -> None:
        self._model = model
        # Permite forzar un fallo en un esquema concreto para probar los caminos
        # de degradación del grafo sin tener que simular una caída de red.
        self._fail_on = fail_on

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["mock"]

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        timeout_seconds: int = 60,
    ) -> LLMResponse:
        schema_name = self._detect_schema(user_content)
        if self._fail_on and self._fail_on == schema_name:
            return LLMResponse(
                text="lo siento, no puedo procesar esta solicitud",
                model=self._model, finish_reason="STOP",
            )

        document = self._extract_document(user_content)
        builders = {
            "ResumeExtractionOutput": self._build_extraction,
            "CandidateEvaluationOutput": self._build_evaluation,
            "BiasAuditOutput": self._build_bias_audit,
            "EmailDraftOutput": self._build_email_draft,
        }
        builder = builders.get(schema_name)
        if builder is None:
            raise ValueError(f"El simulador no sabe generar el esquema «{schema_name}»")

        payload = builder(document, user_content)
        text = json.dumps(payload, ensure_ascii=False)
        return LLMResponse(
            text=text,
            prompt_tokens=len(user_content) // 4,
            completion_tokens=len(text) // 4,
            model=self._model,
            finish_reason="STOP",
        )

    # ── Detección de contexto ────────────────────────────────────────────────

    @staticmethod
    def _detect_schema(user_content: str) -> str:
        """Identifica qué esquema se espera a partir del JSON Schema incluido."""
        match = re.search(r'"title"\s*:\s*"(\w+Output)"', user_content)
        if match:
            return match.group(1)
        for name in ("ResumeExtractionOutput", "CandidateEvaluationOutput",
                     "BiasAuditOutput", "EmailDraftOutput"):
            if name in user_content:
                return name
        return "ResumeExtractionOutput"

    @staticmethod
    def _extract_document(user_content: str) -> str:
        match = re.search(
            r"<untrusted_document[^>]*>(.*?)</untrusted_document>", user_content, re.DOTALL
        )
        return match.group(1).strip() if match else user_content

    # ── Constructores por esquema ────────────────────────────────────────────

    def _build_extraction(self, document: str, _: str) -> dict[str, Any]:
        lowered = document.lower()

        technologies = sorted({t for t in _KNOWN_TECHNOLOGIES if t in lowered})

        years_matches = [float(m.replace(",", ".")) for m in _YEARS_RE.findall(document)]
        years = max(years_matches) if years_matches else self._infer_years_from_dates(document)

        seniority = "unknown"
        for hint, value in _SENIORITY_HINTS:
            if hint in lowered:
                seniority = value
                break

        education = [
            {
                "degree": m.group(0).strip()[:200],
                "field_of_study": "",
                "institution": "",
                "graduation_year": None,
                "level": self._education_level(m.group(1).lower()),
            }
            for m in list(_EDUCATION_RE.finditer(document))[:4]
        ]

        languages = []
        for hint, canonical in _LANGUAGE_HINTS:
            index = lowered.find(hint)
            if index < 0:
                continue
            window = document[index : index + 90]
            level_match = _LEVEL_RE.search(window)
            level = "native" if not level_match else level_match.group(1).lower()
            if level in {"nativo", "nativa", "bilingüe", "bilingue"}:
                level = "native"
            if not any(lang["language"] == canonical for lang in languages):
                languages.append({"language": canonical, "level": level})

        certifications = sorted({
            m.group(0).strip()[:120] for m in list(_CERT_RE.finditer(document))[:6]
        })

        experiences = self._extract_experiences(document, technologies)

        # La confianza es alta cuando encontramos señales explícitas y baja
        # cuando tuvimos que inferir. Así el grafo deriva a revisión humana los
        # documentos realmente ambiguos, igual que haría un modelo honesto.
        confidence = {
            "total_years_experience": 0.9 if years_matches else 0.55,
            "skills": 0.9 if len(technologies) >= 3 else 0.6,
            "education": 0.85 if education else 0.4,
            "languages": 0.8 if languages else 0.5,
        }

        current_role = self._first_role(document)
        suspicious = self._looks_suspicious(document)

        return {
            "total_years_experience": round(years, 1),
            "seniority": seniority,
            "current_role": current_role,
            "skills": technologies[:40],
            "technologies": technologies[:40],
            "experiences": experiences,
            "education": education,
            "languages": languages,
            "certifications": certifications,
            "availability": "inmediata" if "inmediata" in lowered else "",
            "field_confidence": confidence,
            "suspicious_content_found": suspicious,
            "suspicious_content_note": (
                "El documento contiene texto que parece dirigido al sistema automático."
                if suspicious else ""
            ),
        }

    def _build_evaluation(self, document: str, user_content: str) -> dict[str, Any]:
        """Construye una evaluación citando fragmentos literales del documento.

        Las citas son reales por diseño: solo así el verificador de evidencia se
        ejercita de verdad en los tests.
        """
        requested = self._requested_dimensions(user_content)
        mandatory = self._requested_skills(user_content, "Requisitos obligatorios:")
        lowered = document.lower()

        present = [s for s in mandatory if s.lower() in lowered]
        missing = [s for s in mandatory if s.lower() not in lowered]
        coverage = len(present) / len(mandatory) if mandatory else 0.7

        sentences = self._sentences(document)

        # Un CV que solo enumera tecnologías en una lista no acredita lo mismo
        # que uno que las describe en contexto. El simulador distingue ambos
        # casos para que la demostración muestre la diferencia entre emparejar
        # palabras clave y evaluar evidencia real.
        depth = self._evidence_depth(sentences, present)
        dimensions: list[dict[str, Any]] = []

        for dimension in requested:
            base = {
                "technical": 35 + coverage * 40 + depth * 20,
                "experience": 40 + coverage * 30 + depth * 25,
                "education": 60.0,
                "projects": 35 + coverage * 25 + depth * 35,
                "semantic": 40 + coverage * 35 + depth * 20,
                "languages": 70.0,
            }.get(dimension, 55.0)

            evidence = [
                {"quote": quote, "dimension": dimension}
                for quote in self._pick_quotes(sentences, present, dimension)
            ]
            dimensions.append(
                {
                    "dimension": dimension,
                    "score": round(min(96.0, max(12.0, base)), 1),
                    "reasoning": (
                        f"Se identificaron {len(present)} de {len(mandatory)} requisitos "
                        f"obligatorios en el documento."
                        if mandatory
                        else "Evaluación basada en el contenido profesional del documento."
                    ),
                    "evidence": evidence,
                }
            )

        recommendation = "shortlist" if coverage >= 0.8 else ("review" if coverage >= 0.5 else "reject")

        return {
            "dimensions": dimensions,
            "strengths": [f"Experiencia acreditada en {s}" for s in present[:5]],
            "gaps": [f"No se encontró evidencia de {s}" for s in missing[:5]],
            "missing_requirements": missing[:20],
            "summary": (
                f"[EVALUACIÓN SIMULADA] Cobertura de requisitos obligatorios: "
                f"{coverage:.0%}. Este resultado procede del adaptador simulado, "
                "no de un modelo real."
            ),
            "recommendation": recommendation,
        }

    @staticmethod
    def _build_bias_audit(_: str, __: str) -> dict[str, Any]:
        return {
            "bias_detected": False,
            "indicators": [],
            "overall_assessment": (
                "[AUDITORÍA SIMULADA] No se ejecutó una auditoría real de sesgo. "
                "La capa léxica determinística sí se aplicó."
            ),
        }

    @staticmethod
    def _build_email_draft(_: str, user_content: str) -> dict[str, Any]:
        allowed = re.findall(r"^\s*-\s*(\w+)\s*$", user_content, re.MULTILINE)
        return {
            "variables": {name: "" for name in allowed[:20]},
            "tone_note": "[SIMULADO] Borrador generado por el adaptador simulado.",
        }

    # ── Utilidades de análisis ───────────────────────────────────────────────

    @staticmethod
    def _infer_years_from_dates(document: str) -> float:
        years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", document)]
        if len(years) < 2:
            return 0.0
        return float(min(40, max(years) - min(years)))

    @staticmethod
    def _education_level(term: str) -> str:
        mapping = {
            "doctorado": "doctorado", "phd": "doctorado",
            "máster": "master", "master": "master", "maestría": "master",
            "maestria": "master", "ingeniería": "grado", "ingenieria": "grado",
            "licenciatura": "grado", "grado": "grado", "bachelor": "grado",
            "técnico": "tecnico", "tecnico": "tecnico", "tecnólogo": "tecnico",
        }
        return mapping.get(term, "grado")

    @staticmethod
    def _first_role(document: str) -> str:
        match = re.search(
            r"^\s*(?:puesto|cargo|rol|position)\s*[:.\-]\s*(.{3,80})$",
            document, re.IGNORECASE | re.MULTILINE,
        )
        if match:
            return match.group(1).strip()
        match = re.search(
            r"\b((?:senior|junior|semi[\s-]?senior|lead)?\s*"
            r"(?:desarrollador|developer|ingenier[oa]|analista|arquitect[oa]|"
            r"data\s+\w+|devops|qa)\s*[\w\s]{0,40})",
            document, re.IGNORECASE,
        )
        return match.group(1).strip()[:100] if match else ""

    def _extract_experiences(self, document: str, technologies: list[str]) -> list[dict[str, Any]]:
        experiences: list[dict[str, Any]] = []
        pattern = re.compile(
            r"^\s*[-•*]?\s*(.{5,90}?)\s+(?:en|at|\|)\s+(.{2,60}?)\s*"
            r"[\(\[]?\s*(\d{4})\s*[-–—]\s*(\d{4}|actualidad|presente|present)\s*[\)\]]?",
            re.IGNORECASE | re.MULTILINE,
        )
        for match in list(pattern.finditer(document))[:8]:
            role, company, start, end = match.groups()
            end_year = 2026 if end.lower() in {"actualidad", "presente", "present"} else int(end)
            block = document[match.end() : match.end() + 400].lower()
            experiences.append(
                {
                    "company": company.strip()[:200],
                    "role": role.strip()[:200],
                    "start_date": start,
                    "end_date": None if end_year == 2026 else end,
                    "is_current": end_year == 2026,
                    "description": "",
                    "technologies": [t for t in technologies if t in block][:20],
                    "years": float(max(0, end_year - int(start))),
                }
            )
        return experiences

    @staticmethod
    def _requested_dimensions(user_content: str) -> list[str]:
        found = re.findall(
            r"^-\s*(technical|experience|education|projects|semantic|languages):",
            user_content, re.MULTILINE,
        )
        return found or ["technical", "experience", "semantic"]

    @staticmethod
    def _requested_skills(user_content: str, label: str) -> list[str]:
        match = re.search(rf"{re.escape(label)}\s*(.+)", user_content)
        if not match:
            return []
        raw = match.group(1).strip()
        if raw.lower().startswith("no especificad"):
            return []
        return [s.strip() for s in raw.split(",") if s.strip()][:20]

    @staticmethod
    def _sentences(document: str) -> list[str]:
        parts = re.split(r"[\n.;]+", document)
        return [p.strip() for p in parts if 15 <= len(p.strip()) <= 350]

    @staticmethod
    def _looks_like_skill_catalogue(sentence: str) -> bool:
        """¿Es esta línea un listado de tecnologías en vez de una descripción?

        Un catálogo enumera; una descripción narra. La diferencia importa porque
        enumerar una tecnología no acredita haberla usado.
        """
        stripped = sentence.strip()
        many_commas = stripped.count(",") >= 3
        is_labelled_list = bool(re.match(r"^\**[\w\s]{3,30}\**\s*:", stripped))
        few_verbs = not re.search(
            r"\b(desarroll|implement|diseñ|construy|migr|optimiz|redu|automatiz|"
            r"lider|gestion|manten|integr|despleg)\w*", stripped, re.IGNORECASE
        )
        return many_commas and (is_labelled_list or few_verbs)

    @classmethod
    def _evidence_depth(cls, sentences: list[str], present: list[str]) -> float:
        """Proporción de requisitos que aparecen descritos, no solo enumerados.

        Devuelve un valor entre 0 y 1. Un CV que lista veinte tecnologías sin
        contar qué hizo con ninguna tiende a 0; uno que describe su uso en
        proyectos concretos tiende a 1.
        """
        if not present or not sentences:
            return 0.5
        narrative = [s for s in sentences if not cls._looks_like_skill_catalogue(s)]
        described = sum(
            1 for skill in present
            if any(skill.lower() in s.lower() for s in narrative)
        )
        return described / len(present)

    @staticmethod
    def _pick_quotes(sentences: list[str], present: list[str], dimension: str) -> list[str]:
        """Elige frases del documento que mencionen los requisitos encontrados."""
        quotes: list[str] = []
        for skill in present:
            for sentence in sentences:
                if skill.lower() in sentence.lower() and sentence not in quotes:
                    quotes.append(sentence[:380])
                    break
            if len(quotes) >= 3:
                break
        if not quotes and sentences:
            # Sin coincidencias, se cita el fragmento más informativo disponible.
            quotes = [max(sentences, key=len)[:380]]
        return quotes[:3]

    @staticmethod
    def _looks_suspicious(document: str) -> bool:
        markers = (
            "ignore previous", "ignora las instrucciones", "system:", "[system]",
            "score of 100", "puntuación de 100", "pre-aprobado", "pre-approved",
        )
        lowered = document.lower()
        return any(m in lowered for m in markers)

    def __repr__(self) -> str:
        return "MockLLMAdapter(SIMULADO — no usar en producción)"


__all__ = ["MockLLMAdapter"]
