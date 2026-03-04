"""
consensus.py — Évaluation par consensus multi-agents.
Inspiré de Grok 4.20 : N évaluateurs indépendants jugent le même résultat
avec des perspectives différentes. Le score final est l'agrégation.

Avantage : élimine les cas où un seul LLM valide son propre code médiocre.

Usage:
    from queen_core.consensus import evaluate_with_consensus
    result = evaluate_with_consensus(context, num_evaluators=3)
"""

import json
import logging
import statistics
from typing import Dict, Any, List, Optional

from queen_core.llm_client import generate_json

logger = logging.getLogger("queen.consensus")

# ─── Perspectives d'évaluation ───────────────────────────────────────────────
# Chaque évaluateur a un angle différent pour éviter le groupthink.

EVALUATOR_PERSONAS = [
    {
        "name": "correctness_expert",
        "system": (
            "Tu es un expert en correctness logicielle. Tu juges si le code "
            "fait EXACTEMENT ce qui est demandé, sans bugs ni edge cases oubliés. "
            "Tu es sévère sur la logique et les erreurs silencieuses. "
            "Tu réponds UNIQUEMENT en JSON valide."
        ),
        "focus": "correctness",
    },
    {
        "name": "security_reviewer",
        "system": (
            "Tu es un reviewer sécurité senior. Tu cherches les failles : "
            "injections, path traversal, données non validées, dépendances "
            "dangereuses, secrets exposés. Tu es paranoïaque par design. "
            "Tu réponds UNIQUEMENT en JSON valide."
        ),
        "focus": "security",
    },
    {
        "name": "maintainability_judge",
        "system": (
            "Tu es un architecte logiciel qui juge la maintenabilité. "
            "Tu évalues : lisibilité, nommage, découpage en fonctions, "
            "duplication, documentation, testabilité. Tu favorises le code "
            "simple et explicite. Tu réponds UNIQUEMENT en JSON valide."
        ),
        "focus": "maintainability",
    },
    {
        "name": "performance_analyst",
        "system": (
            "Tu es un expert performance Python. Tu identifies les "
            "bottlenecks : boucles O(n²), allocations inutiles, I/O bloquant, "
            "structures de données inadaptées. Tu es pragmatique : "
            "l'optimisation prématurée est un anti-pattern. "
            "Tu réponds UNIQUEMENT en JSON valide."
        ),
        "focus": "performance",
    },
]

EVAL_PROMPT_TEMPLATE = """Évalue ce travail selon ton expertise ({focus}):

Objectif du goal: {goal_title}
Description: {goal_description}
Critères de succès: {success_criteria}

Résultat à évaluer:
{result_summary}

Donne un score de 0.0 à 1.0 et une justification.
Réponds en JSON:
{{
  "score": 0.0,
  "verdict": "approve|retry|reject",
  "strengths": ["point fort"],
  "weaknesses": ["point faible"],
  "critical_issues": [],
  "justification": "explication en 2-3 phrases"
}}"""


# ─── Consensus Engine ─────────────────────────────────────────────────────────

def evaluate_with_consensus(
    context: Dict[str, Any],
    num_evaluators: int = 3,
    approval_threshold: float = 0.6,
    min_approvals: int = 2,
    run_id: str = "",
) -> Dict[str, Any]:
    """
    Évalue un résultat avec N évaluateurs indépendants.

    Args:
        context: Dict avec goal_title, goal_description, success_criteria, result_summary
        num_evaluators: Nombre d'évaluateurs (2-4)
        approval_threshold: Score minimum pour un approve individuel
        min_approvals: Nombre minimum d'approves pour le consensus
        run_id: Pour le budget tracking

    Returns:
        Dict avec score agrégé, verdicts individuels, et consensus final.
    """
    num_evaluators = max(2, min(num_evaluators, len(EVALUATOR_PERSONAS)))
    evaluators = EVALUATOR_PERSONAS[:num_evaluators]

    individual_results: List[Dict[str, Any]] = []

    for evaluator in evaluators:
        try:
            prompt = EVAL_PROMPT_TEMPLATE.format(
                focus=evaluator["focus"],
                goal_title=context.get("goal_title", ""),
                goal_description=context.get("goal_description", ""),
                success_criteria=context.get("success_criteria", ""),
                result_summary=_truncate(context.get("result_summary", ""), 3000),
            )

            result = generate_json(
                prompt,
                system=evaluator["system"],
                temperature=0.3,
                max_tokens=1024,
            )

            # Normaliser le score
            score = float(result.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            result["score"] = score
            result["evaluator"] = evaluator["name"]
            result["focus"] = evaluator["focus"]
            individual_results.append(result)

            logger.info(
                f"Evaluator [{evaluator['name']}] score={score:.2f} "
                f"verdict={result.get('verdict', '?')}"
            )

        except Exception as e:
            logger.warning(f"Evaluator [{evaluator['name']}] failed: {e}")
            individual_results.append({
                "evaluator": evaluator["name"],
                "focus": evaluator["focus"],
                "score": 0.0,
                "verdict": "error",
                "justification": f"Evaluation failed: {str(e)}",
                "strengths": [],
                "weaknesses": [],
                "critical_issues": [],
            })

    # ── Agrégation ────────────────────────────────────────────────────────
    return _aggregate_results(
        individual_results,
        approval_threshold=approval_threshold,
        min_approvals=min_approvals,
    )


def _aggregate_results(
    results: List[Dict[str, Any]],
    approval_threshold: float = 0.6,
    min_approvals: int = 2,
) -> Dict[str, Any]:
    """Agrège les résultats de N évaluateurs en un verdict consensus."""

    scores = [r["score"] for r in results if isinstance(r.get("score"), (int, float))]

    if not scores:
        return {
            "consensus_score": 0.0,
            "consensus_verdict": "error",
            "num_evaluators": len(results),
            "individual_results": results,
            "reason": "No valid scores",
        }

    # Score agrégé : médiane (plus robuste que la moyenne face aux outliers)
    consensus_score = statistics.median(scores)

    # Compter les approvals
    approvals = sum(
        1 for r in results
        if r.get("verdict") == "approve" or r.get("score", 0) >= approval_threshold
    )
    rejections = sum(
        1 for r in results
        if r.get("verdict") == "reject"
    )

    # Collecter les issues critiques
    all_critical = []
    for r in results:
        critical = r.get("critical_issues", [])
        if isinstance(critical, list):
            all_critical.extend(critical)

    # Verdict final
    if rejections > 0 and all_critical:
        consensus_verdict = "reject"
    elif approvals >= min_approvals:
        consensus_verdict = "approve"
    elif consensus_score >= approval_threshold:
        consensus_verdict = "approve"
    else:
        consensus_verdict = "retry"

    # Collecter forces et faiblesses
    all_strengths = []
    all_weaknesses = []
    for r in results:
        all_strengths.extend(r.get("strengths", []))
        all_weaknesses.extend(r.get("weaknesses", []))

    # Dédupliquer
    all_strengths = list(dict.fromkeys(all_strengths))[:5]
    all_weaknesses = list(dict.fromkeys(all_weaknesses))[:5]

    return {
        "consensus_score": round(consensus_score, 3),
        "consensus_verdict": consensus_verdict,
        "num_evaluators": len(results),
        "approvals": approvals,
        "rejections": rejections,
        "scores": scores,
        "score_spread": round(max(scores) - min(scores), 3) if len(scores) > 1 else 0.0,
        "strengths": all_strengths,
        "weaknesses": all_weaknesses,
        "critical_issues": all_critical,
        "individual_results": results,
    }


def _truncate(text: str, max_chars: int = 3000) -> str:
    """Tronque un texte en gardant début et fin."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n... [tronqué] ...\n\n" + text[-half:]
