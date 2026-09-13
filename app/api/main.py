"""API unificada de TalentIA.

Expone el panel de configuración y la ejecución del agente sobre las
convocatorias y los CVs del laboratorio.

Dos decisiones que se ven en el código y conviene señalar:

* **Los secretos nunca salen por la API.** El endpoint de configuración devuelve
  valores enmascarados y un indicador de si la clave está establecida. No existe
  ningún endpoint que devuelva una API key en claro.
* **La respuesta de evaluación incluye `actions_executed: false`.** El agente
  propone; nada de lo que devuelve se ha aplicado. Dejarlo explícito en el
  contrato evita que un cliente futuro asume lo contrario.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.ai.agent import AGENT_NAME, AGENT_VERSION, EvaluationRequest, VeraAgent
from app.ai.graphs.evaluation_graph import GRAPH_NAME, GRAPH_VERSION
from app.ai.graphs.model_benchmark_graph import run_model_benchmark
from app.ai.graphs.runner import langgraph_available
from app.ai.prompts.registry import get_prompt_registry
from app.api.dependencies import requires, requires_settings_write
from app.api.schemas import (
    AgentHealthResponse,
    CredentialTestRequest,
    CredentialTestResponse,
    DimensionOut,
    ErrorDetail,
    ErrorResponse,
    EvaluationResponse,
    EvaluationRunRequest,
    EvidenceOut,
    FilterResultOut,
    HealthResponse,
    JobSummary,
    ModelBenchmarkRequest,
    ResumeSummary,
    SettingsResponse,
    SettingsUpdateRequest,
)
from app.application.unit_of_work import UnitOfWork
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError, VeraError
from app.core.logging import configure_logging, get_logger, get_trace_id, set_trace_id
from app.core.observability import METRICS
from app.domain.enums import Permission
from app.domain.value_objects import EmailAddress
from app.infrastructure.database.session import get_session, init_database
from app.infrastructure.fixtures_loader import (
    job_brief_markdown,
    load_all_jobs,
    load_all_resumes,
)
from app.infrastructure.llm.factory import build_llm_from_settings, describe_provider
from app.infrastructure.llm.gemini_adapter import GeminiAdapter
from app.infrastructure.llm.model_catalog import (
    SELECTABLE_LLM_MODELS,
    provider_for_model,
)
from app.infrastructure.llm.openai_adapter import OpenAIAdapter
from app.infrastructure.llm.openai_compatible_adapter import (
    DEFAULT_GENAI_LAB_BASE_URL,
    OpenAICompatibleAdapter,
)
from app.infrastructure.observability.mlflow_tracker import MLFLOW_TRACKER
from app.infrastructure.settings_store import SettingsStore

logger = get_logger(__name__)
API_PREFIX = "/api/v1"


def _validate_json_object(text: str) -> None:
    """Acepta JSON puro o envuelto en texto/bloques Markdown."""
    cleaned = text.strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("La respuesta no es un objeto JSON")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, as_json=settings.log_json)
    # Asegura el esquema también cuando la API se inicia sin el script auxiliar.
    init_database()

    if settings.mlflow_enabled:
        try:
            import mlflow

            mlflow.set_tracking_uri(settings.resolved_mlflow_tracking_uri)
            mlflow.set_experiment(settings.mlflow_experiment_name)
        except ImportError:
            pass

    logger.info(
        "TalentIA iniciado",
        agent=AGENT_NAME,
        version=AGENT_VERSION,
        environment=settings.environment.value,
        langgraph=langgraph_available(),
    )
    yield
    logger.info("TalentIA detenido")


app = FastAPI(
    title="TalentIA",
    description=(
        "Applicant Tracking System con agente de IA gobernado. "
        "TalentIA asiste; las personas autorizadas deciden."
    ),
    version=AGENT_VERSION,
    lifespan=lifespan,
)

from app.api.v1.routes.operations import router as operations_router  # noqa: E402

app.include_router(operations_router)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    # Allowlist explícita. Nunca comodín, ni siquiera en desarrollo: un comodín
    # que se cuela en un despliegue es difícil de detectar después.
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def trace_and_headers(request: Request, call_next):
    """Asigna un identificador de traza y aplica cabeceras de seguridad."""
    trace_id = set_trace_id(request.headers.get("X-Trace-Id"))
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(VeraError)
async def vera_error_handler(_: Request, exc: VeraError) -> JSONResponse:
    """Traduce las excepciones de dominio al envelope uniforme de error.

    Nunca se filtra la traza de pila ni detalles internos hacia el cliente.
    """
    payload = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=get_trace_id(),
            timestamp=datetime.now(UTC).isoformat(),
        )
    )
    if exc.http_status >= 500:
        logger.error("Error interno", code=exc.code, message=exc.message)
    return JSONResponse(status_code=exc.http_status, content=payload.model_dump())


SessionDep = Annotated[Session, Depends(get_session)]


def get_store(session: SessionDep) -> Iterator[SettingsStore]:
    yield SettingsStore(session)


StoreDep = Annotated[SettingsStore, Depends(get_store)]


# ── Salud ────────────────────────────────────────────────────────────────────


@app.get("/health/live", tags=["salud"])
def health_live() -> dict[str, str]:
    """Liveness: sin dependencias. Solo dice que el proceso responde."""
    return {"status": "alive"}


@app.get("/health/ready", response_model=HealthResponse, tags=["salud"])
def health_ready(store: StoreDep) -> HealthResponse:
    """Readiness: comprueba las dependencias necesarias para atender tráfico."""
    settings = get_settings()
    return HealthResponse(
        status="ready",
        environment=settings.environment.value,
        database=settings.database_url.split("://", 1)[0],
        llm_ready=store.is_llm_ready(),
        version=AGENT_VERSION,
    )


@app.get("/metrics", tags=["salud"], dependencies=[Depends(requires(Permission.SETTINGS_READ))])
def metrics() -> dict[str, object]:
    return METRICS.snapshot()


@app.get(
    f"{API_PREFIX}/observability/llm",
    tags=["observabilidad"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def llm_observability() -> dict[str, object]:
    """Estado de MLflow y consumo agregado por proveedor/modelo."""
    return MLFLOW_TRACKER.status()


@app.post(
    f"{API_PREFIX}/benchmarks/models",
    tags=["observabilidad"],
    dependencies=[Depends(requires_settings_write)],
)
def benchmark_models(payload: ModelBenchmarkRequest, store: StoreDep) -> dict[str, object]:
    """Compara modelos con la misma suite sintética y conserva las llamadas en MLflow."""
    if not payload.confirmed:
        raise ValidationError("Confirma explícitamente el consumo antes de ejecutar.")
    models = payload.models
    invalid = sorted(set(models) - set(SELECTABLE_LLM_MODELS))
    if invalid:
        raise ValidationError(f"Modelos fuera del catálogo: {', '.join(invalid)}")
    if payload.baseline_model and payload.baseline_model not in models:
        raise ValidationError("El modelo base debe formar parte de los modelos seleccionados.")
    return run_model_benchmark(store, models, baseline_model=payload.baseline_model or models[0])


# ── Configuración ────────────────────────────────────────────────────────────


@app.get(
    f"{API_PREFIX}/config/settings",
    response_model=SettingsResponse,
    tags=["configuración"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def read_settings(store: StoreDep) -> SettingsResponse:
    """Configuración actual. Los secretos van enmascarados, nunca en claro."""
    config = store.llm_config()
    llm = build_llm_from_settings(store)
    info = describe_provider(llm)
    return SettingsResponse(
        settings=store.get_public_view(),  # type: ignore[arg-type]
        llm_ready=store.is_llm_ready(),
        provider=str(config["provider"]),
        model=str(config["model"]),
        is_simulated=bool(info["is_simulated"]),
    )


@app.patch(
    f"{API_PREFIX}/config/settings",
    response_model=SettingsResponse,
    tags=["configuración"],
    dependencies=[Depends(requires_settings_write)],
)
def update_settings(
    payload: SettingsUpdateRequest, store: StoreDep, session: SessionDep
) -> SettingsResponse:
    """Actualiza claves de configuración.

    Las claves ausentes no se tocan. Un secreto se conserva omitiéndolo, lo que
    permite reenviar el formulario del panel sin borrar la API key guardada.
    """
    model = payload.values.get("llm.model")
    values = dict(payload.values)
    if model:
        if model not in SELECTABLE_LLM_MODELS:
            raise ValidationError(
                f"El modelo «{model}» no pertenece al catálogo de generación vigente."
            )
        values["llm.provider"] = provider_for_model(model)
    applied = store.set_many(values, updated_by=payload.updated_by)
    session.commit()
    logger.info("Configuración modificada", keys=applied, updated_by=payload.updated_by)
    return read_settings(store)


@app.post(
    f"{API_PREFIX}/config/test-credentials",
    response_model=CredentialTestResponse,
    tags=["configuración"],
    dependencies=[Depends(requires_settings_write)],
)
def test_credentials(payload: CredentialTestRequest, store: StoreDep) -> CredentialTestResponse:
    """Verifica una API key sin llegar a gastar una generación completa.

    Si no se envía clave, se usa la ya guardada: así el panel puede comprobar la
    credencial existente sin obligar a reescribirla.
    """
    try:
        provider = provider_for_model(payload.model)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if provider == "mock":
        return CredentialTestResponse(
            ok=True,
            message="Adaptador simulado activo. No requiere credenciales.",
            available_models=["mock"],
        )

    stored_key_name = {
        "genai_lab": "llm.genai_lab_api_key",
        "gemini": "llm.gemini_api_key",
        "openai": "llm.openai_api_key",
    }[provider]
    api_key = payload.api_key or store.get(stored_key_name, "")
    if not api_key and provider == "genai_lab":
        api_key = store.get("llm.api_key", "")
    if provider == "genai_lab":
        base_url = payload.base_url or store.get("llm.base_url", DEFAULT_GENAI_LAB_BASE_URL)
        adapter = OpenAICompatibleAdapter(api_key=api_key, model=payload.model, base_url=base_url)
    elif provider == "gemini":
        adapter = GeminiAdapter(api_key=api_key, model=payload.model)
    else:
        adapter = OpenAIAdapter(api_key=api_key, model=payload.model)
    ok, message = adapter.verify_credentials()
    if ok and provider in {"genai_lab", "gemini"}:
        try:
            probe = adapter.generate_json(
                system_instruction="Responde con un objeto json válido.",
                user_content="Devuelve un objeto json con la clave ok y valor true.",
                temperature=0.0,
                max_output_tokens=256,
                timeout_seconds=60,
            )
            _validate_json_object(probe.text)
            message = f"Clave y generación verificadas con el modelo {payload.model}."
        except (VeraError, ValueError, json.JSONDecodeError) as exc:
            ok = False
            message = (
                f"La clave es válida, pero el modelo seleccionado no pudo generar: {str(exc)[:300]}"
            )
    return CredentialTestResponse(
        ok=ok, message=message, available_models=adapter.list_models() if ok else []
    )


@app.get(
    f"{API_PREFIX}/config/models",
    tags=["configuración"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def list_models(store: StoreDep) -> dict[str, list[str]]:
    """Catálogo único; el proveedor y la credencial se resuelven internamente."""
    return {"models": list(SELECTABLE_LLM_MODELS)}


# ── Agente ───────────────────────────────────────────────────────────────────


@app.get(
    f"{API_PREFIX}/agent/health",
    response_model=AgentHealthResponse,
    tags=["agente"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def agent_health(store: StoreDep) -> AgentHealthResponse:
    llm = build_llm_from_settings(store)
    info = describe_provider(llm)
    registry = get_prompt_registry()
    return AgentHealthResponse(
        agent=AGENT_NAME,
        full_name="Verified Evidence & Ranking Agent",
        version=AGENT_VERSION,
        graph=f"{GRAPH_NAME}@{GRAPH_VERSION}",
        llm_configured=llm.is_configured,
        model=llm.model_name,
        provider=str(info["provider"]),
        is_simulated=bool(info["is_simulated"]),
        llm_bias_audit=bool(store.llm_config()["enable_bias_audit"]),
        budget_usd=float(store.llm_config()["budget_usd"]),
        prompts=[
            {"id": p.full_id, "schema": p.output_schema, "checksum": p.checksum}
            for p in registry.list_all()
        ],
        langgraph_available=langgraph_available(),
    )


@app.get(
    f"{API_PREFIX}/agent/graph",
    tags=["agente"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def agent_graph() -> dict[str, str]:
    """Diagrama del grafo, derivado de su definición real."""
    from app.ai.graphs.evaluation_graph import graph_diagram
    from app.domain.rules.state_machine import ApplicationStateMachine

    return {
        "evaluation_graph": graph_diagram(),
        "application_lifecycle": ApplicationStateMachine.to_mermaid(),
    }


# ── Catálogo del laboratorio ─────────────────────────────────────────────────


@app.get(
    f"{API_PREFIX}/jobs",
    response_model=list[JobSummary],
    tags=["vacantes"],
    dependencies=[Depends(requires(Permission.JOB_READ))],
)
def list_jobs(session: SessionDep) -> list[JobSummary]:
    jobs = UnitOfWork(session).jobs.list(limit=100)
    if not jobs:
        jobs = load_all_jobs()
    return [
        JobSummary(
            id=job.id,
            code=job.code,
            title=job.title,
            department=job.department,
            location=job.location,
            status=job.status.value,
            minimum_score=job.requirements.minimum_score,
            review_threshold=job.requirements.review_threshold,
            min_years_experience=job.requirements.min_years_experience,
            mandatory_skills=job.requirements.mandatory_skills,
            hard_filter_count=len(job.requirements.hard_filters),
            weights={d.value: w for d, w in job.requirements.weights.weights.items()},
            requirements_version=job.requirements.version,
            language_required=any(
                f.operator.value == "min_level" for f in job.requirements.hard_filters
            ),
            language_level=next(
                (
                    str(f.value.get("level", "b2"))
                    for f in job.requirements.hard_filters
                    if f.operator.value == "min_level"
                ),
                "b2",
            ),
            language_mode=next(
                (
                    f.effective_mode.value
                    for f in job.requirements.hard_filters
                    if f.operator.value == "min_level"
                ),
                "weighted",
            ),
            language_penalty_percent=next(
                (
                    f.effective_penalty_percent
                    for f in job.requirements.hard_filters
                    if f.operator.value == "min_level"
                ),
                15.0,
            ),
        )
        for job in jobs
    ]


@app.get(
    f"{API_PREFIX}/jobs/{{code}}/brief",
    tags=["vacantes"],
    dependencies=[Depends(requires(Permission.JOB_READ))],
)
def job_brief(code: str, session: SessionDep) -> dict[str, str]:
    """Bases de convocatoria en su versión legible."""
    content = job_brief_markdown(code)
    if not content:
        job = UnitOfWork(session).jobs.get_by_code(code)
        if job is None:
            raise NotFoundError(f"No hay bases de convocatoria para «{code}»")
        content = f"# {job.title}\n\n{job.description}"
    return {"code": code, "markdown": content}


@app.get(
    f"{API_PREFIX}/resumes",
    response_model=list[ResumeSummary],
    tags=["candidatos"],
    dependencies=[Depends(requires(Permission.CANDIDATE_READ))],
)
def list_resumes() -> list[ResumeSummary]:
    """CVs ficticios disponibles. El correo se devuelve enmascarado."""
    return [
        ResumeSummary(
            code=resume.code,
            full_name=resume.full_name,
            email_masked=EmailAddress(value=resume.email).masked(),
            char_count=len(resume.text),
            purpose=resume.purpose,
            is_security_fixture=resume.is_security_fixture,
        )
        for resume in load_all_resumes()
    ]


# ── Evaluación ───────────────────────────────────────────────────────────────


@app.post(
    f"{API_PREFIX}/evaluations/run",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    tags=["evaluación"],
    dependencies=[Depends(requires(Permission.EVALUATION_RUN))],
)
def run_evaluation(payload: EvaluationRunRequest, store: StoreDep) -> EvaluationResponse:
    """Ejecuta TalentIA sobre una combinación de vacante y CV.

    Lo que devuelve es una **propuesta**: ninguna de las acciones sugeridas se ha
    aplicado, y así lo indica el campo ``actions_executed``.
    """
    job = next((j for j in load_all_jobs() if j.code.upper() == payload.job_code.upper()), None)
    if job is None:
        raise NotFoundError(f"No existe la vacante «{payload.job_code}»")

    resume = next(
        (r for r in load_all_resumes() if r.code.upper() == payload.resume_code.upper()), None
    )
    if resume is None:
        raise NotFoundError(f"No existe el CV «{payload.resume_code}»")

    config = store.llm_config()
    llm = build_llm_from_settings(store)
    info = describe_provider(llm)

    agent = VeraAgent(
        llm,
        enable_llm_bias_audit=bool(config["enable_bias_audit"]),
        budget_usd=float(config["budget_usd"]),
    )
    result = agent.evaluate(
        EvaluationRequest(
            application_id=f"{job.code}:{resume.code}",
            candidate_id=resume.code,
            job_id=job.id,
            resume_id=resume.code,
            resume_text=resume.text,
            candidate_name=resume.full_name,
            candidate_email=resume.email,
            requirements=job.requirements,
            job_title=job.title,
            job_department=job.department,
            job_description=job.description,
            dry_run=payload.dry_run,
        )
    )

    evaluation = result.evaluation
    summary = result.state_summary

    return EvaluationResponse(
        application_id=evaluation.application_id,
        trace_id=evaluation.trace_id,
        workflow_run_id=evaluation.workflow_run_id,
        agent=AGENT_NAME,
        agent_version=evaluation.agent_version,
        model=evaluation.model_name,
        is_simulated=bool(info["is_simulated"]),
        total_score=result.total_score,
        score_calculated=bool(evaluation.dimension_scores),
        recommendation=evaluation.recommendation.value,
        passed_hard_filters=evaluation.passed_hard_filters,
        requires_human_review=evaluation.requires_human_review,
        review_reasons=[r.value for r in evaluation.review_reasons],
        hard_filters=[
            FilterResultOut(
                label=f.filter_label,
                passed=f.passed,
                mandatory=f.mandatory,
                explanation=f.explanation,
                status=f.status.value,
                mode=f.mode.value,
                penalty_percent=f.penalty_percent,
            )
            for f in evaluation.hard_filter_results
        ],
        dimensions=[
            DimensionOut(
                dimension=d.dimension.value,
                score=d.score,
                weight=d.weight,
                reasoning=d.reasoning,
                evidence=[
                    EvidenceOut(
                        quote=e.quote,
                        dimension=e.dimension.value,
                        verified=e.verified,
                        match_ratio=e.match_ratio,
                    )
                    for e in d.evidence
                ],
            )
            for d in evaluation.dimension_scores
        ],
        strengths=evaluation.strengths,
        gaps=evaluation.gaps,
        missing_requirements=evaluation.missing_requirements,
        summary=evaluation.summary,
        explanation=result.explain(),
        evidence_verification_rate=evaluation.evidence_verification_rate,
        injection_detected=bool(summary.get("injection_detected")),
        injection_severity=str(summary.get("injection_severity", "info")),
        bias_detected=bool(summary.get("bias_detected")),
        pii_redactions=int(summary.get("pii_redactions", 0)),
        pii_categories=list(result.state_summary.get("pii_categories", []) or []),
        proposed_actions=[str(a) for a in result.proposed_actions],
        policy_decisions=list(summary.get("policy_decisions", []) or []),
        nodes_executed=list(summary.get("nodes_executed", [])),
        node_timings=result.workflow_run.node_timings,
        token_usage=result.workflow_run.token_usage,
        cost_usd=result.workflow_run.cost_usd,
        prompt_versions=evaluation.prompt_versions,
        actions_executed=False,
    )


# ── Diagnóstico y Benchmarking (OpenAI) ──────────────────────────────────────


@app.post(
    f"{API_PREFIX}/ai/test",
    tags=["diagnóstico"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def test_openai_endpoint():
    """Realiza una llamada de prueba pequeña al modelo configurado."""
    from app.services.openai_service import OpenAIService, OpenAIServiceError

    try:
        service = OpenAIService()
        messages = [{"role": "user", "content": "Responde únicamente: conexión correcta"}]
        result = service.call_model(messages=messages, feature="test_connection")

        if result.get("success"):
            return {
                "success": True,
                "model": result.get("model"),
                "response": result.get("response"),
                "input_tokens": result.get("input_tokens"),
                "output_tokens": result.get("output_tokens"),
                "total_tokens": result.get("total_tokens"),
                "estimated_cost_usd": result.get("estimated_cost_usd"),
                "latency_ms": result.get("latency_ms"),
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error_message": result.get("error_message")},
            )
    except OpenAIServiceError as e:
        return JSONResponse(status_code=500, content={"success": False, "error_message": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"success": False, "error_message": f"Error interno: {e!s}"}
        )


@app.post(
    f"{API_PREFIX}/ai/compare-models",
    tags=["diagnóstico"],
    dependencies=[Depends(requires(Permission.SETTINGS_READ))],
)
def compare_openai_models():
    """Ejecuta el mismo prompt utilizando gpt-5.6-luna y gpt-5.6-terra para desarrollo."""
    from app.core.config import get_settings
    from app.services.openai_service import OpenAIService

    if get_settings().environment.value not in ["development", "testing"]:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error_message": "Endpoint solo disponible en desarrollo"},
        )

    service = OpenAIService()
    messages = [{"role": "user", "content": "Responde con un chiste corto de programadores"}]

    results = {}

    for model in ["gpt-5.6-luna", "gpt-5.6-terra"]:
        try:
            res = service.call_model(messages=messages, model=model, feature="model_comparison")
            if res.get("success"):
                results[model] = {
                    "response": res.get("response"),
                    "input_tokens": res.get("input_tokens"),
                    "output_tokens": res.get("output_tokens"),
                    "total_tokens": res.get("total_tokens"),
                    "latency_ms": res.get("latency_ms"),
                    "estimated_cost_usd": res.get("estimated_cost_usd"),
                }
            else:
                results[model] = {"error": res.get("error_message")}
        except Exception as e:
            results[model] = {"error": str(e)}

    return results


def create_app() -> FastAPI:
    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
