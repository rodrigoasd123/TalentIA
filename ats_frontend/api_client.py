"""Cliente HTTP del backend.

Streamlit no toca la base de datos ni importa el dominio: habla con la API como
lo haría cualquier otro cliente. Esa restricción es lo que permite sustituir la
interfaz más adelante sin reescribir nada del sistema.

Si alguna vez aparece aquí un `from app.domain...`, la separación se ha roto.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = os.getenv("VERA_API_BASE_URL", "http://127.0.0.1:8000")
API_PREFIX = "/api/v1"


class ApiError(Exception):
    """Error devuelto por el backend, ya traducido a algo mostrable."""

    def __init__(self, message: str, *, code: str = "", trace_id: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.trace_id = trace_id


class VeraApiClient:
    def __init__(
        self, base_url: str = DEFAULT_BASE_URL, *, timeout: float = 180.0,
        access_token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.access_token = access_token

    # ── Transporte ───────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        headers = dict(kwargs.pop("headers", {}))
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, headers=headers, **kwargs)
        except httpx.ConnectError as exc:
            raise ApiError(
                f"No se pudo conectar con el backend en {self.base_url}. "
                "¿Está arrancado? Ejecuta: uvicorn app.api.main:app --reload"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApiError(
                "El backend no respondió a tiempo. Una evaluación con modelo real "
                "puede tardar; prueba a aumentar el timeout."
            ) from exc

        if response.status_code >= 400:
            raise ApiError(*self._describe_error(response))
        return response.json() if response.content else None

    @staticmethod
    def _describe_error(response: httpx.Response) -> tuple[str, ...]:
        try:
            error = response.json().get("error", {})
            return (
                error.get("message", f"HTTP {response.status_code}"),
            )
        except (ValueError, AttributeError):
            return (f"HTTP {response.status_code}: {response.text[:200]}",)

    # ── Salud ────────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health/ready")

    def is_available(self) -> bool:
        try:
            self._request("GET", "/health/live")
        except ApiError:
            return False
        return True

    def metrics(self) -> dict[str, Any]:
        return self._request("GET", "/metrics")

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/auth/login",
            json={"email": email, "password": password},
        )

    # ── Configuración ────────────────────────────────────────────────────────

    def get_settings(self) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/config/settings")

    def update_settings(self, values: dict[str, str], *, updated_by: str = "panel") -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"{API_PREFIX}/config/settings",
            json={"values": values, "updated_by": updated_by},
        )

    def test_credentials(
        self, *, provider: str, api_key: str = "", model: str = "gemini-2.5-flash"
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{API_PREFIX}/config/test-credentials",
            json={"provider": provider, "api_key": api_key, "model": model},
        )

    def list_models(self) -> list[str]:
        return self._request("GET", f"{API_PREFIX}/config/models").get("models", [])

    # ── Agente ───────────────────────────────────────────────────────────────

    def agent_health(self) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/agent/health")

    def agent_graph(self) -> dict[str, str]:
        return self._request("GET", f"{API_PREFIX}/agent/graph")

    # ── Catálogo ─────────────────────────────────────────────────────────────

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._request("GET", f"{API_PREFIX}/jobs")

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{API_PREFIX}/jobs", json=payload)

    def update_job(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"{API_PREFIX}/jobs/{job_id}", json=payload)

    def sourcing_query(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/jobs/{job_id}/sourcing-query")

    def job_brief(self, code: str) -> str:
        return self._request("GET", f"{API_PREFIX}/jobs/{code}/brief").get("markdown", "")

    def list_resumes(self) -> list[dict[str, Any]]:
        return self._request("GET", f"{API_PREFIX}/resumes")

    # ── Evaluación ───────────────────────────────────────────────────────────

    def run_evaluation(
        self, *, job_code: str, resume_code: str, dry_run: bool = True
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{API_PREFIX}/evaluations/run",
            json={"job_code": job_code, "resume_code": resume_code, "dry_run": dry_run},
        )

    # ── Pipeline y candidaturas ──────────────────────────────────────────────

    def pipeline(self, job_id: str | None = None) -> dict[str, Any]:
        params = {"job_id": job_id} if job_id else None
        return self._request("GET", f"{API_PREFIX}/pipeline", params=params)["columns"]

    def list_applications(self, job_id: str | None = None) -> list[dict[str, Any]]:
        params = {"job_id": job_id} if job_id else None
        return self._request("GET", f"{API_PREFIX}/applications", params=params)

    def intake_application(
        self, *, full_name: str, email: str, job_id: str,
        consent_granted: bool, filename: str, content: bytes,
        phone: str = "", source: str = "manual",
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/intake",
            data={
                "full_name": full_name, "email": email, "job_id": job_id,
                "consent_granted": str(consent_granted).lower(),
                "phone": phone, "source": source,
            },
            files={"resume": (filename, content, content_type)},
        )

    def candidate_360(self, application_id: str) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/applications/{application_id}/360")

    def evaluate_application(
        self, application_id: str, *, dry_run: bool | None = None
    ) -> dict[str, Any]:
        params = {} if dry_run is None else {"dry_run": dry_run}
        return self._request(
            "POST", f"{API_PREFIX}/applications/{application_id}/evaluate", params=params
        )

    def transition(self, application_id: str, *, target_status: str, reason: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            f"{API_PREFIX}/applications/{application_id}/transition",
            json={"target_status": target_status, "reason": reason},
        )

    def ranking(self, job_id: str, *, include_rejected: bool = False) -> list[dict[str, Any]]:
        return self._request(
            "GET", f"{API_PREFIX}/jobs/{job_id}/ranking",
            params={"include_rejected": include_rejected},
        )

    def compare(self, a: str, b: str) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/applications/compare", params={"a": a, "b": b})

    # ── Revisión humana ──────────────────────────────────────────────────────

    def review_queue(self, status: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status} if status else None
        return self._request("GET", f"{API_PREFIX}/reviews/queue", params=params)

    def review_statistics(self) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/reviews/statistics")

    def claim_review(self, item_id: str) -> dict[str, Any]:
        return self._request("POST", f"{API_PREFIX}/reviews/{item_id}/claim")

    def decide_review(
        self, item_id: str, *, decision: str, justification: str,
        score_override: float | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{API_PREFIX}/reviews/{item_id}/decide",
            json={
                "decision": decision,
                "justification": justification,
                "score_override": score_override,
            },
        )

    # ── Comunicaciones ───────────────────────────────────────────────────────

    def email_templates(self) -> list[dict[str, Any]]:
        return self._request("GET", f"{API_PREFIX}/email-templates")

    def email_provider(self) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/emails/provider")

    def prepare_email(
        self, *, application_id: str, template_code: str, use_ai: bool = True
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{API_PREFIX}/emails/prepare",
            json={
                "application_id": application_id,
                "template_code": template_code,
                "use_ai": use_ai,
            },
        )

    def pending_emails(self) -> list[dict[str, Any]]:
        return self._request("GET", f"{API_PREFIX}/emails/pending")

    def approve_email(self, email_id: str, *, note: str = "") -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/emails/{email_id}/approve", json={"note": note}
        )

    def send_email(self, email_id: str, *, force_dry_run: bool | None = None) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/emails/{email_id}/send",
            json={"force_dry_run": force_dry_run},
        )

    # ── Analítica ────────────────────────────────────────────────────────────

    def dashboard_summary(self) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/dashboard/summary")

    def funnel(self, job_id: str | None = None) -> list[dict[str, Any]]:
        params = {"job_id": job_id} if job_id else None
        return self._request("GET", f"{API_PREFIX}/dashboard/funnel", params=params)

    def sla_alerts(self, hours: int = 72) -> list[dict[str, Any]]:
        return self._request("GET", f"{API_PREFIX}/dashboard/sla-alerts", params={"hours": hours})

    def source_analytics(self) -> list[dict[str, Any]]:
        return self._request("GET", f"{API_PREFIX}/dashboard/sources")

    def stage_durations(self, job_id: str | None = None) -> dict[str, float]:
        params = {"job_id": job_id} if job_id else None
        return self._request("GET", f"{API_PREFIX}/dashboard/stage-durations", params=params)

    def equity_report(self, job_id: str | None = None) -> dict[str, Any]:
        params = {"job_id": job_id} if job_id else None
        return self._request("GET", f"{API_PREFIX}/equity/report", params=params)

    # ── Auditoría ────────────────────────────────────────────────────────────

    def audit_events(self, **filters: Any) -> list[dict[str, Any]]:
        params = {k: v for k, v in filters.items() if v}
        return self._request("GET", f"{API_PREFIX}/audit/events", params=params)

    def verify_audit(self) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/audit/verify")

    def decision_trail(self, application_id: str, *, fmt: str = "json") -> Any:
        path = f"{API_PREFIX}/audit/applications/{application_id}/decision-trail"
        if fmt == "json":
            return self._request("GET", path, params={"format": "json"})
        # Los formatos exportables devuelven texto plano, no JSON.
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}{path}", params={"format": fmt})
        if response.status_code >= 400:
            raise ApiError(*self._describe_error(response))
        return response.text

    # ── Importación histórica ───────────────────────────────────────────────

    def upload_historical_import(
        self, *, filename: str, content: bytes, source: str = "historical",
        sheet_name: str = "", content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/imports/historical",
            data={"source": source, "sheet_name": sheet_name},
            files={"file": (filename, content, content_type)},
        )

    def get_import(self, batch_id: str) -> dict[str, Any]:
        return self._request("GET", f"{API_PREFIX}/imports/{batch_id}")

    def select_import_sheet(
        self, batch_id: str, *, sheet_name: str, expected_version: int
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{API_PREFIX}/imports/{batch_id}/select-sheet",
            json={"sheet_name": sheet_name, "expected_version": expected_version},
        )

    def validate_import(
        self, batch_id: str, *, mapping: dict[str, str], expected_version: int,
        template_name: str = "",
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/imports/{batch_id}/validate",
            json={
                "mapping": mapping,
                "expected_version": expected_version,
                "template_name": template_name,
            },
        )

    def import_rows(self, batch_id: str, *, offset: int = 0, limit: int = 100) -> dict[str, Any]:
        return self._request(
            "GET", f"{API_PREFIX}/imports/{batch_id}/rows",
            params={"offset": offset, "limit": limit},
        )

    def confirm_import(
        self, batch_id: str, *, idempotency_key: str, expected_version: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/imports/{batch_id}/confirm",
            json={"idempotency_key": idempotency_key, "expected_version": expected_version},
        )

    def cancel_import(self, batch_id: str, *, reason: str) -> dict[str, Any]:
        return self._request(
            "POST", f"{API_PREFIX}/imports/{batch_id}/cancel", json={"reason": reason}
        )

    def import_templates(self, source: str = "") -> list[dict[str, Any]]:
        params = {"source": source} if source else None
        return self._request("GET", f"{API_PREFIX}/imports/templates", params=params)


__all__ = ["DEFAULT_BASE_URL", "ApiError", "VeraApiClient"]
