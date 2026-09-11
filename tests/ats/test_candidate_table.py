from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ats_frontend.talentia.candidate_table import (
    PII_COLUMNS,
    application_states,
    candidate_csv,
    candidate_rows,
    filter_candidates,
)


def _candidate(**overrides):
    candidate = {
        "id": "candidate-1",
        "full_name": "Ana Ejemplo",
        "client": "Cliente Uno",
        "record_date": "2026-09-10",
        "recruiter": "Recruiter A",
        "source": "Adecco",
        "q": "Q3",
        "requested": "Backend Senior",
        "availability": "15 días",
        "location": "Lima",
        "technical_knowledge": "Python y FastAPI",
        "email": "ana@example.test",
        "phone": "999111222",
        "birth_date": "1990-09-11",
        "age": 36,
        "national_id": "12345678",
        "bgc": "Conforme",
        "equifax_debt": 125.5,
        "salary_expectation": 5000,
        "role_ctc": 5500,
        "ctc_variation_pct": -10,
        "notes": "Seguimiento semanal",
    }
    candidate.update(overrides)
    return candidate


def test_application_states_preserve_each_job() -> None:
    grouped = application_states(
        [
            {
                "candidate_id": "candidate-1",
                "job_code": "DEV-001",
                "status_label": "Entrevista",
            },
            {
                "candidate_id": "candidate-1",
                "job_code": "QA-002",
                "status_label": "Revisión humana",
            },
        ]
    )

    assert grouped == {
        "candidate-1": ["DEV-001: Entrevista", "QA-002: Revisión humana"]
    }


def test_filter_candidates_searches_profile_and_application() -> None:
    candidates = [
        _candidate(),
        _candidate(
            id="candidate-2",
            full_name="Luis Ejemplo",
            recruiter="Recruiter B",
            source="Referido",
            requested="QA",
        ),
    ]
    states = {"candidate-1": ["DEV-001: Entrevista"]}

    assert filter_candidates(candidates, states, query="dev-001") == [candidates[0]]
    assert filter_candidates(
        candidates,
        states,
        recruiter="Recruiter B",
        source="Referido",
    ) == [candidates[1]]


def test_candidate_rows_exclude_pii_columns_without_permission() -> None:
    restricted = candidate_rows([_candidate()], {}, reveal_pii=False)[0]
    revealed = candidate_rows([_candidate()], {}, reveal_pii=True)[0]

    assert not set(PII_COLUMNS).intersection(restricted)
    assert revealed["Correo"] == "ana@example.test"
    assert revealed["Fecha"] == date(2026, 9, 10)
    assert revealed["Fecha de nacimiento"] == date(1990, 9, 11)


def test_candidate_csv_exports_visible_rows_and_neutralizes_formulas() -> None:
    rows = candidate_rows(
        [_candidate(full_name="=CMD()", ctc_variation_pct=-10)],
        {},
        reveal_pii=True,
    )

    content = candidate_csv(rows).decode("utf-8-sig")
    exported = next(csv.DictReader(io.StringIO(content)))

    assert exported["Candidato"] == "'=CMD()"
    assert exported["Variación CTC (%)"] == "-10"
    assert "candidate-1" not in content


def test_candidate_page_shows_registry_and_create_form(monkeypatch) -> None:
    frontend = Path(__file__).parents[2] / "ats_frontend"
    monkeypatch.syspath_prepend(str(frontend))
    from talentia import session as ui_session

    class FakeClient:
        def health(self):
            return {"environment": "test", "database": "sqlite", "version": "1.0.0"}

        def dashboard_summary(self):
            return {"total_candidates": 1}

        def list_jobs(self):
            return []

        def list_candidates(self):
            return [_candidate()]

        def list_applications(self, job_id=None):
            del job_id
            return [
                {
                    "candidate_id": "candidate-1",
                    "candidate_name": "Ana Ejemplo",
                    "job_code": "DEV-001",
                    "status": "interviewed",
                }
            ]

        def funnel(self, job_id=None):
            del job_id
            return []

        def sla_alerts(self, hours):
            del hours
            return []

    monkeypatch.setattr(ui_session, "client", lambda: FakeClient())

    app = AppTest.from_file(frontend / "streamlit_app.py", default_timeout=10)
    app.session_state["auth_mode"] = "lab"
    app.session_state["auth_user"] = {
        "role": "recruiter",
        "permissions": [
            "candidate:read",
            "candidate:write",
            "candidate:pii:read",
            "application:read",
        ],
    }
    app.run()
    app.switch_page("views/candidates.py").run()

    assert not app.exception
    assert len(app.dataframe) == 1
    assert app.dataframe[0].value.iloc[0]["Candidato"] == "Ana Ejemplo"
    assert app.dataframe[0].value.iloc[0]["Estados por postulación"] == (
        "DEV-001: Entrevistado"
    )

    next(button for button in app.button if button.label == "Nuevo candidato").click().run()

    assert not app.exception
    assert any(title.value == "Nuevo candidato" for title in app.subheader)
