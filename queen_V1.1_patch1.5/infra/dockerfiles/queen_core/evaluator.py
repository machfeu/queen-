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

# Patch 1.4: inject few-shot skill examples for better calibration (if present)
try:
    from queen_core.skill_registry import get_skill_registry
    _skill = get_skill_registry().read_skill("code-evaluation")
    if _skill:
        EVAL_SYSTEM = EVAL_SYSTEM + "\n\n=== Calibration (code-evaluation) ===\n" + _skill
except Exception:
    pass


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

    # Prefer consensus multi-eval (patch 1.4) when available
    run_id = ""
    try:
        if jobs and isinstance(jobs[0], dict):
            run_id = jobs[0].get("run_id", "") or ""
    except Exception:
        run_id = ""

    try:
        from queen_core.consensus import evaluate_with_consensus

        context = {
            "goal_title": goal.get("title", ""),
            "goal_description": goal.get("description", ""),
            "success_criteria": goal.get("constraints", {}).get("success_criteria", "non spécifié"),
            "result_summary": "\n".join(job_summaries),
        }

        cons = evaluate_with_consensus(context=context, num_evaluators=3, run_id=run_id)

        # Map to legacy evaluator output
        focus_scores = {}
        for r in cons.get("individual_results", []) or []:
            try:
                focus_scores[r.get("focus", "unknown")] = float(r.get("score", 0.0) or 0.0)
            except Exception:
                focus_scores[r.get("focus", "unknown")] = 0.0

        # Estimate tests score from test jobs
        tests = [j for j in jobs if j.get("job_type") == "test"]
        if tests:
            passed = 0
            for tj in tests:
                if tj.get("status") == "success":
                    passed += 1
                else:
                    try:
                        if isinstance(tj.get("result"), dict) and tj["result"].get("all_passed") is True:
                            passed += 1
                    except Exception:
                        pass
            tests_score = passed / max(1, len(tests))
        else:
            tests_score = 0.5

        result = {
            "score": float(cons.get("consensus_score", 0.0) or 0.0),
            "justification": (
                f"Consensus: {cons.get('consensus_verdict')} — strengths: {cons.get('strengths', [])} — weaknesses: {cons.get('weaknesses', [])}"
            ),
            "criteria": {
                "pertinence": focus_scores.get("correctness", 0.5),
                "qualite_code": focus_scores.get("maintainability", 0.5),
                "tests_passent": round(tests_score, 3),
                "securite": focus_scores.get("security", 0.5),
                "completude": float(cons.get("consensus_score", 0.0) or 0.0),
            },
            "recommendations": (cons.get("weaknesses", []) or [])[:5],
            "verdict": cons.get("consensus_verdict", "retry"),
            "consensus": {
                "approvals": cons.get("approvals"),
                "rejections": cons.get("rejections"),
                "score_spread": cons.get("score_spread"),
                "scores": cons.get("scores"),
            },
        }

    except Exception as e:
        logger.warning(f"Consensus evaluation unavailable or failed: {e}")
        try:
            result = generate_json(prompt, system=EVAL_SYSTEM, temperature=0.3, run_id=run_id)
        except Exception as e2:
            logger.error(f"Evaluation LLM call failed: {e2}")
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
