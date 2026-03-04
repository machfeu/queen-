"""
evaluator.py — Évalue et score les résultats des runs.
Inspiré du evaluator_hybride.py original de Graine IA.
"""

import logging
from typing import Dict, Any, List

from queen_core.llm_client import generate_json

logger = logging.getLogger("queen.evaluator")

EVAL_SYSTEM = """Tu es l'Evaluator de Queen V1. Tu évalues la qualité des résultats produits par un run.

Tu reçois:
- L'objectif original
- Les résultats de chaque job du run (logs, artefacts, statuts)

Tu dois produire un scoring structuré en JSON:
{
  "score": <float entre 0.0 et 1.0>,
  "justification": "explication détaillée du score",
  "criteria": {
    "pertinence": <0.0-1.0>,
    "qualite_code": <0.0-1.0>,
    "tests_passent": <0.0-1.0>,
    "securite": <0.0-1.0>,
    "completude": <0.0-1.0>
  },
  "recommendations": ["suggestion 1", "suggestion 2"],
  "verdict": "approve|retry|reject"
}

Règles:
- Score < 0.3 → reject (trop mauvais pour être utilisable)
- Score 0.3-0.7 → retry (améliorable)
- Score > 0.7 → approve (peut passer aux gates)
- Sois honnête et critique. Ne sois pas complaisant."""


def evaluate_run(goal: Dict[str, Any], jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate a completed run's results."""
    # Build context from job results
    job_summaries = []
    for job in jobs:
        summary = (
            f"Job [{job.get('job_type')}] '{job.get('id')}': "
            f"status={job.get('status')}, "
            f"result_preview={str(job.get('result', {}))[:500]}"
        )
        job_summaries.append(summary)

    prompt = f"""Objectif: {goal.get('title', '')}
Description: {goal.get('description', '')}
Critères de succès: {goal.get('constraints', {}).get('success_criteria', 'non spécifié')}

Résultats des jobs:
{chr(10).join(job_summaries)}

Évalue ces résultats et produis un scoring."""

    try:
        result = generate_json(prompt, system=EVAL_SYSTEM, temperature=0.3)
    except Exception as e:
        logger.error(f"Evaluation LLM call failed: {e}")
        result = _fallback_eval(jobs)

    # Ensure score is valid
    score = result.get("score", 0.0)
    if not isinstance(score, (int, float)):
        score = 0.0
    result["score"] = max(0.0, min(1.0, float(score)))

    return result


def compare_runs(goal: Dict[str, Any], runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare multiple runs for the same goal."""
    if len(runs) <= 1:
        return {"best_run_id": runs[0]["id"] if runs else "", "comparison": "single run"}

    run_summaries = []
    for run in runs:
        run_summaries.append(
            f"Run {run['id']}: score={run.get('score', 0)}, "
            f"status={run.get('status')}, "
            f"justification={run.get('score_justification', '')[:200]}"
        )

    prompt = f"""Compare ces runs pour l'objectif "{goal.get('title', '')}":

{chr(10).join(run_summaries)}

Quel est le meilleur run et pourquoi? Réponds en JSON:
{{"best_run_id": "...", "comparison": "explication", "ranking": ["run_id_1", "run_id_2"]}}"""

    try:
        return generate_json(prompt, temperature=0.2)
    except Exception:
        # Simple fallback: highest score wins
        best = max(runs, key=lambda r: r.get("score", 0))
        return {"best_run_id": best["id"], "comparison": "highest score selected"}


def _fallback_eval(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback evaluation when LLM is unavailable."""
    success_count = sum(1 for j in jobs if j.get("status") == "success")
    total = len(jobs) if jobs else 1
    score = success_count / total

    return {
        "score": round(score, 2),
        "justification": f"{success_count}/{total} jobs succeeded (LLM unavailable for detailed eval)",
        "criteria": {
            "pertinence": 0.5,
            "qualite_code": score,
            "tests_passent": score,
            "securite": 0.5,
            "completude": score,
        },
        "recommendations": ["Re-run with LLM available for detailed evaluation"],
        "verdict": "approve" if score > 0.7 else ("retry" if score > 0.3 else "reject"),
    }
