"""Transformaciones puras para la base general de candidatos."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import date
from typing import Any

BASE_COLUMNS = (
    "Candidato",
    "Cliente",
    "Estados por postulación",
    "Fecha",
    "Reclutador",
    "Fuente",
    "Q",
    "Solicitado",
    "Disponibilidad",
    "Ubicación",
    "Conocimientos técnicos",
)

PII_COLUMNS = (
    "Correo",
    "Teléfono",
    "Fecha de nacimiento",
    "Edad",
    "DNI",
    "BGC",
    "Deuda Equifax",
    "Expectativa salarial",
    "CTC para el rol",
    "Variación CTC (%)",
    "Observaciones",
)


def application_states(applications: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    """Agrupa estados ya formateados por persona sin inferir un estado global."""
    grouped: dict[str, list[str]] = {}
    for application in applications:
        candidate_id = str(application.get("candidate_id", ""))
        if not candidate_id:
            continue
        job = str(application.get("job_code") or "Vacante")
        status = str(application.get("status_label") or application.get("status") or "Sin estado")
        grouped.setdefault(candidate_id, []).append(f"{job}: {status}")
    return grouped


def filter_candidates(
    candidates: Iterable[dict[str, Any]],
    states_by_candidate: dict[str, list[str]],
    *,
    query: str = "",
    recruiter: str = "Todos",
    source: str = "Todas",
) -> list[dict[str, Any]]:
    """Filtra localmente la respuesta autorizada de la API."""
    needle = query.casefold().strip()
    visible: list[dict[str, Any]] = []
    for candidate in candidates:
        if recruiter != "Todos" and candidate.get("recruiter", "") != recruiter:
            continue
        if source != "Todas" and candidate.get("source", "") != source:
            continue
        if needle:
            searchable = [
                candidate.get(key, "")
                for key in (
                    "full_name",
                    "client",
                    "recruiter",
                    "source",
                    "requested",
                    "location",
                    "technical_knowledge",
                    "email",
                    "phone",
                    "national_id",
                )
            ]
            searchable.extend(states_by_candidate.get(str(candidate.get("id", "")), []))
            if needle not in " ".join(str(value or "") for value in searchable).casefold():
                continue
        visible.append(candidate)
    return visible


def candidate_rows(
    candidates: Iterable[dict[str, Any]],
    states_by_candidate: dict[str, list[str]],
    *,
    reveal_pii: bool,
) -> list[dict[str, Any]]:
    """Construye únicamente las columnas que pueden enviarse al navegador."""
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id", ""))
        row: dict[str, Any] = {
            "Candidato": candidate.get("full_name", ""),
            "Cliente": candidate.get("client", ""),
            "Estados por postulación": ", ".join(states_by_candidate.get(candidate_id, []))
            or "Sin postulación",
            "Fecha": _date_value(candidate.get("record_date")),
            "Reclutador": candidate.get("recruiter", ""),
            "Fuente": candidate.get("source", ""),
            "Q": candidate.get("q", ""),
            "Solicitado": candidate.get("requested", ""),
            "Disponibilidad": candidate.get("availability", ""),
            "Ubicación": candidate.get("location", ""),
            "Conocimientos técnicos": candidate.get("technical_knowledge", ""),
        }
        if reveal_pii:
            row.update(
                {
                    "Correo": candidate.get("email", ""),
                    "Teléfono": candidate.get("phone", ""),
                    "Fecha de nacimiento": _date_value(candidate.get("birth_date")),
                    "Edad": candidate.get("age"),
                    "DNI": candidate.get("national_id", ""),
                    "BGC": candidate.get("bgc", ""),
                    "Deuda Equifax": candidate.get("equifax_debt"),
                    "Expectativa salarial": candidate.get("salary_expectation"),
                    "CTC para el rol": candidate.get("role_ctc"),
                    "Variación CTC (%)": candidate.get("ctc_variation_pct"),
                    "Observaciones": candidate.get("notes", ""),
                }
            )
        rows.append(row)
    return rows


def candidate_csv(rows: Iterable[dict[str, Any]]) -> bytes:
    """Genera un CSV compatible con Excel y neutraliza fórmulas en celdas."""
    materialized = list(rows)
    if not materialized:
        return b""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(materialized[0]))
    writer.writeheader()
    for row in materialized:
        writer.writerow({key: _safe_cell(value) for key, value in row.items()})
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _date_value(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _safe_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


__all__ = [
    "BASE_COLUMNS",
    "PII_COLUMNS",
    "application_states",
    "candidate_csv",
    "candidate_rows",
    "filter_candidates",
]
