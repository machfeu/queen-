"""
planner.py — Décompose un objectif en liste de jobs exécutables.
Inspiré du planner_hybride.py original de Graine IA.
"""

import logging
from typing import Dict, Any, List

from queen_core.llm_client import generate_json
from queen_core.policy import validate_job, get_job_budget

logger = logging.getLogger("queen.planner")

PLANNING_SYSTEM = """Tu es le Planner de Queen V1, un système d'auto-amélioration contrôlée.
Tu reçois un objectif et tu dois le décomposer en une séquence de jobs exécutables.

Types de jobs disponibles:
- research: recherche d'information, analyse de contexte, lecture de code existant
- codegen: génération de code, modification de fichiers, création de scripts
- test: exécution de tests, lint, analyse statique, vérification de sécurité
- eval: évaluation de la qualité des résultats, scoring, comparaison
- patch: génération d'un diff/patch à partir des résultats

Règles:
1. Toujours commencer par un job "research" pour analyser le contexte
2. Toujours finir par un job "eval" puis "patch"
3. Chaque job "codegen" doit être suivi d'un job "test"
4. Être précis dans les descriptions de chaque job
5. Ne pas dépasser {max_jobs} jobs au total

Réponds UNIQUEMENT en JSON avec cette structure:
{{
  "plan_summary": "résumé du plan en une phrase",
  "jobs": [
    {{
      "step": 1,
      "job_type": "research|codegen|test|eval|patch",
      "title": "titre court",
      "description": "description détaillée de ce que le job doit accomplir",
      "depends_on": [],
      "estimated_duration_seconds": 60
    }}
  ]
}}"""


def create_plan(goal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a goal into a list of jobs.
    Returns: {"plan_summary": str, "jobs": [...]}
    """
    constraints = goal.get("constraints", {})
    risk_level = constraints.get("risk_level", "medium")
    budget = get_job_budget(risk_level)

    prompt = f"""Objectif: {goal['title']}
Description: {goal.get('description', '')}
Critères de succès: {constraints.get('success_criteria', 'non spécifié')}
Repo cible: {constraints.get('repo_target', 'default')}
Niveau de risque: {risk_level}
Budget max jobs: {budget['max_jobs']}

Décompose cet objectif en jobs exécutables."""

    system = PLANNING_SYSTEM.format(max_jobs=budget['max_jobs'])

    try:
        result = generate_json(prompt, system=system, temperature=0.4)
    except Exception as e:
        logger.error(f"Planning LLM call failed: {e}")
        # Fallback: plan minimal
        result = _fallback_plan(goal)

    # Validate each job
    validated_jobs = []
    for job in result.get("jobs", []):
        ok, reason = validate_job(job.get("job_type", ""), job)
        if ok:
            validated_jobs.append(job)
        else:
            logger.warning(f"Job rejected by policy: {reason}")

    result["jobs"] = validated_jobs
    return result


def _fallback_plan(goal: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal plan when LLM is unavailable."""
    return {
        "plan_summary": f"Plan par défaut pour: {goal.get('title', 'objectif')}",
        "jobs": [
            {
                "step": 1,
                "job_type": "research",
                "title": "Analyse du contexte",
                "description": f"Analyser le contexte pour l'objectif: {goal.get('description', '')}",
                "depends_on": [],
                "estimated_duration_seconds": 60,
            },
            {
                "step": 2,
                "job_type": "codegen",
                "title": "Génération de code",
                "description": "Générer le code ou les modifications nécessaires.",
                "depends_on": [1],
                "estimated_duration_seconds": 120,
            },
            {
                "step": 3,
                "job_type": "test",
                "title": "Tests et validation",
                "description": "Exécuter les tests, lint et vérifications de sécurité.",
                "depends_on": [2],
                "estimated_duration_seconds": 60,
            },
            {
                "step": 4,
                "job_type": "eval",
                "title": "Évaluation des résultats",
                "description": "Évaluer la qualité et la pertinence des résultats produits.",
                "depends_on": [3],
                "estimated_duration_seconds": 60,
            },
            {
                "step": 5,
                "job_type": "patch",
                "title": "Génération du patch",
                "description": "Générer un diff/patch à partir des résultats validés.",
                "depends_on": [4],
                "estimated_duration_seconds": 30,
            },
        ],
    }
