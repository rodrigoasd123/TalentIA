"""Ejecuta TalentIA sobre convocatorias y CV ficticios del laboratorio.

Uso:

    python scripts/run_demo.py                       # todas las combinaciones
    python scripts/run_demo.py --job VAC-001         # solo una vacante
    python scripts/run_demo.py --cv CV-007           # solo un CV
    python scripts/run_demo.py --provider gemini     # con el modelo real

Sin argumentos usa el adaptador simulado, así que funciona sin API key.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# La consola de Windows usa cp1252 por defecto y revienta con acentos y símbolos.
# Forzar UTF-8 aquí evita que la demostración falle por un carácter tipográfico.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.ai.agent import AGENT_NAME, EvaluationRequest, VeraAgent  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.infrastructure.fixtures_loader import load_all_jobs, load_all_resumes  # noqa: E402
from app.infrastructure.llm.factory import build_llm, describe_provider  # noqa: E402

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def recommendation_color(value: str) -> str:
    return {"shortlist": GREEN, "review": YELLOW, "reject": RED}.get(value, "")


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Demostración de {AGENT_NAME}")
    parser.add_argument("--job", help="Código de vacante (por ejemplo VAC-001)")
    parser.add_argument("--cv", help="Código de CV (por ejemplo CV-007)")
    parser.add_argument("--provider", default="mock", choices=["mock", "gemini"])
    parser.add_argument("--api-key", default="", help="API key si el proveedor es gemini")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--verbose", action="store_true", help="Muestra los logs del grafo")
    parser.add_argument("--evidence", action="store_true", help="Muestra la evidencia citada")
    args = parser.parse_args()

    configure_logging("INFO" if args.verbose else "WARNING", as_json=False)

    llm = build_llm(args.provider, api_key=args.api_key, model=args.model)
    info = describe_provider(llm)

    print(f"\n{BOLD}TalentIA — evaluación con evidencia verificable{RESET}")
    print(f"Proveedor: {info['provider']} · Modelo: {info['model']}")
    if info["warning"]:
        print(colorize(f"⚠  {info['warning']}", YELLOW))

    jobs = load_all_jobs()
    resumes = load_all_resumes()
    if args.job:
        jobs = [j for j in jobs if j.code.upper() == args.job.upper()]
    if args.cv:
        resumes = [r for r in resumes if r.code.upper().startswith(args.cv.upper())]

    if not jobs or not resumes:
        print(colorize("No hay convocatorias o CVs que coincidan con el filtro.", RED))
        return 1

    print(f"Vacantes: {len(jobs)} · CVs: {len(resumes)} · "
          f"Evaluaciones: {len(jobs) * len(resumes)}\n")

    agent = VeraAgent(llm, prefer_langgraph=True)
    total_cost = 0.0

    for job in jobs:
        print(f"\n{BOLD}{'═' * 78}{RESET}")
        print(f"{BOLD}{job.code} — {job.title}{RESET}")
        print(f"{DIM}Mínimo {job.requirements.minimum_score:.0f} pts · "
              f"{len(job.requirements.hard_filters)} filtros · "
              f"{job.requirements.min_years_experience:.0f} años mínimos{RESET}")
        print(f"{BOLD}{'═' * 78}{RESET}")

        results = []
        for resume in resumes:
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
                )
            )
            results.append((resume, result))
            total_cost += result.workflow_run.cost_usd

        for resume, result in sorted(results, key=lambda r: -r[1].total_score):
            evaluation = result.evaluation
            rec = evaluation.recommendation.value
            flags = []
            if result.state_summary.get("injection_detected"):
                flags.append(colorize("INYECCIÓN", RED))
            if evaluation.bias_audit and evaluation.bias_audit.bias_detected:
                flags.append(colorize("SESGO", RED))
            if result.requires_human_review:
                flags.append(colorize("REVISIÓN", YELLOW))

            print(
                f"\n  {BOLD}{resume.full_name}{RESET} {DIM}({resume.code}){RESET}"
                f"  →  {colorize(f'{result.total_score:6.2f}', recommendation_color(rec))}"
                f"  {colorize(rec.upper(), recommendation_color(rec))}"
                + ("  " + " ".join(flags) if flags else "")
            )
            for filter_result in evaluation.hard_filter_results:
                mark = colorize("✓", GREEN) if filter_result.passed else colorize("✗", RED)
                obligation = "" if filter_result.mandatory else f" {DIM}(valorable){RESET}"
                print(f"      {mark} {filter_result.filter_label}{obligation}: "
                      f"{DIM}{filter_result.explanation}{RESET}")
            if evaluation.dimension_scores:
                dims = "  ".join(
                    f"{d.dimension.value}={d.score:.0f}" for d in evaluation.dimension_scores
                )
                print(f"      {DIM}{dims}{RESET}")
            print(f"      {DIM}Evidencia verificada: "
                  f"{evaluation.evidence_verification_rate:.0%} · "
                  f"PII retirada: {result.state_summary['pii_redactions']} elementos · "
                  f"coste ${result.workflow_run.cost_usd:.5f}{RESET}")
            if evaluation.review_reasons:
                reasons = ", ".join(r.value for r in evaluation.review_reasons)
                print(f"      {YELLOW}Motivos de revisión: {reasons}{RESET}")
            if args.evidence:
                for span in evaluation.all_evidence[:6]:
                    mark = colorize("✓", GREEN) if span.verified else colorize("✗", RED)
                    print(f"      {mark} {DIM}«{span.quote[:110]}»{RESET}")

    print(f"\n{BOLD}{'─' * 78}{RESET}")
    print(f"Coste total estimado: ${total_cost:.5f}")
    print(f"{DIM}Recuerda: ninguna de estas decisiones se ha aplicado. "
          f"TalentIA asiste; las personas autorizadas deciden.{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
