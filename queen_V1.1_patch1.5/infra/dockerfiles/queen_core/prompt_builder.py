"""
prompt_builder.py — Construction de prompts spécialisés par type de job.
Inspiré d'Emergent AI : chaque worker a un prompt adapté à sa spécialité,
enrichi du contexte des étapes précédentes (chaînage OpenManus).

Usage:
    from queen_core.prompt_builder import build_prompt
    system, user = build_prompt(job, role_name="optimizer")
"""

import json
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("queen.prompt_builder")

# ─── System prompts par type de job ──────────────────────────────────────────

SYSTEM_PROMPTS = {
    "research": (
        "Tu es un analyste de code senior. Tu examines du code source, "
        "identifies les patterns, les dépendances, les points faibles, "
        "et produis des analyses structurées. Tu es méthodique et exhaustif. "
        "Tu réponds UNIQUEMENT en JSON valide."
    ),
    "codegen": (
        "Tu es un développeur Python senior. Tu écris du code propre, "
        "documenté, typé, testé. Tu ne casses jamais le code existant. "
        "Tu suis les conventions du projet. Tu ne génères JAMAIS de code "
        "dangereux (eval, exec, subprocess, os.system). "
        "Tu réponds UNIQUEMENT en JSON valide."
    ),
    "test": (
        "Tu es un ingénieur qualité Python. Tu vérifies la syntaxe, "
        "la sécurité, la conformité du code. Tu identifies les risques "
        "et les régressions potentielles. Tu es rigoureux et exhaustif."
    ),
    "eval": (
        "Tu es un évaluateur de code expert. Tu juges la qualité globale "
        "d'un ensemble de modifications : lisibilité, maintenabilité, "
        "performance, sécurité, couverture de tests. Tu attribues un score "
        "entre 0 et 1 avec des justifications précises par critère. "
        "Tu réponds UNIQUEMENT en JSON valide."
    ),
    "patch": (
        "Tu es un intégrateur de code. Tu collectes les fichiers générés, "
        "produis un diff unifié propre, et vérifies que tout est cohérent "
        "avant l'intégration. Tu réponds UNIQUEMENT en JSON valide."
    ),
}

# ─── User prompt templates par type ──────────────────────────────────────────

USER_TEMPLATES = {
    "research": """Analyse ce contexte pour un objectif d'amélioration de code:

Objectif: {goal_title}
Description: {goal_description}
Tâche spécifique: {description}

Fichiers existants dans le workspace:
{existing_files}

{previous_context}

Fournis une analyse structurée en JSON:
{{
  "analysis": "ton analyse détaillée",
  "findings": ["point 1", "point 2"],
  "recommendations": ["recommandation 1", "recommandation 2"],
  "files_to_modify": ["file1.py", "file2.py"],
  "risks": ["risque potentiel"],
  "summary": "résumé en 2 phrases"
}}""",

    "codegen": """Génère du code Python pour:

Objectif: {goal_title}
Tâche: {description}

{previous_context}

Règles:
- Code propre, commenté, typé
- Pas de subprocess, eval, exec, os.system
- Pas d'import de packages dangereux
- Fichiers dans le workspace uniquement
- Si l'analyse précédente recommande des fichiers à modifier, suis ses recommandations

Réponds en JSON:
{{
  "artifacts": [
    {{
      "path": "relative/path/file.py",
      "content": "# code complet ici...",
      "description": "ce que fait ce fichier"
    }}
  ],
  "summary": "résumé de ce qui a été généré"
}}""",

    "eval": """Évalue la qualité de ces modifications:

Objectif: {goal_title}
Critères de succès: {success_criteria}

{previous_context}

Score chaque critère de 0 à 1 et donne un verdict global.
Réponds en JSON:
{{
  "score": 0.0,
  "criteria": {{
    "correctness": {{"score": 0.0, "reason": "..."}},
    "readability": {{"score": 0.0, "reason": "..."}},
    "security": {{"score": 0.0, "reason": "..."}},
    "testing": {{"score": 0.0, "reason": "..."}}
  }},
  "verdict": "approve|retry|reject",
  "justification": "explication globale"
}}""",

    "patch": """Collecte et prépare le patch final:

Objectif: {goal_title}

{previous_context}

Produis un résumé du patch en JSON:
{{
  "files_changed": ["file1.py", "file2.py"],
  "summary": "résumé des modifications",
  "breaking_changes": false,
  "notes": "remarques pour le reviewer"
}}""",
}


# ─── Builder ─────────────────────────────────────────────────────────────────

def build_prompt(
    job: Dict[str, Any],
    role_name: str = "",
    extra_skills: str = "",
) -> Tuple[str, str]:
    """
    Construit le couple (system_prompt, user_prompt) pour un job.

    1. Charge le system prompt de base selon le job_type
    2. Enrichit avec le rôle si fourni
    3. Ajoute les skills si fournis
    4. Construit le user prompt avec le template + contexte précédent

    Returns:
        (system_prompt, user_prompt)
    """
    job_type = job.get("job_type", "codegen")
    payload = job.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    # ── System prompt ────────────────────────────────────────────────────
    system = SYSTEM_PROMPTS.get(job_type, SYSTEM_PROMPTS["codegen"])

    # Enrichir avec le rôle
    if role_name:
        try:
            from queen_core.role_registry import get_role_registry
            role_reg = get_role_registry()
            role = role_reg.get(role_name)
            if role:
                role_prompt = role.build_system_prompt()
                system = f"{role_prompt}\n\n{system}"
                logger.debug(f"Enriched system prompt with role '{role_name}'")
        except ImportError:
            pass

    # Enrichir avec les skills
    if extra_skills:
        system += f"\n\n=== Connaissances disponibles ===\n{extra_skills}"

    # ── User prompt ──────────────────────────────────────────────────────
    template = USER_TEMPLATES.get(job_type, "")

    # Récupérer le contexte des étapes précédentes (injecté par job_chain)
    previous_context = payload.get("previous_context", "")
    if previous_context:
        previous_context = f"\n=== Contexte des étapes précédentes ===\n{previous_context}\n"

    # Fichiers existants (pour research)
    existing_files = payload.get("existing_files", [])
    if isinstance(existing_files, list):
        existing_files_str = json.dumps(existing_files[:50], indent=2) if existing_files else "Aucun"
    else:
        existing_files_str = str(existing_files)

    if template:
        user = template.format(
            goal_title=payload.get("goal_title", ""),
            goal_description=payload.get("goal_description", ""),
            description=payload.get("description", ""),
            existing_files=existing_files_str,
            previous_context=previous_context,
            success_criteria=payload.get("success_criteria", ""),
        )
    else:
        # Fallback pour les types inconnus
        user = f"""Tâche: {payload.get('description', '')}
Objectif: {payload.get('goal_title', '')}

{previous_context}

Réponds en JSON."""

    return system, user


def load_skills_for_role(role_name: str) -> str:
    """
    Charge le contenu des skills attachés à un rôle.
    Retourne le texte concaténé, prêt à injecter dans le prompt.
    """
    try:
        from queen_core.role_registry import get_role_registry
        from queen_core.skill_registry import get_skill_registry

        role_reg = get_role_registry()
        skill_reg = get_skill_registry()

        role = role_reg.get(role_name)
        if not role or not role.skills:
            return ""

        parts = []
        total_chars = 0
        max_chars = 6000  # ~1500 tokens max pour les skills

        for skill_name in role.skills:
            content = skill_reg.read_skill(skill_name)
            if content and total_chars + len(content) < max_chars:
                parts.append(f"--- Skill: {skill_name} ---\n{content}")
                total_chars += len(content)
                logger.debug(f"Loaded skill '{skill_name}' ({len(content)} chars)")

        return "\n\n".join(parts)

    except ImportError:
        return ""
    except Exception as e:
        logger.warning(f"Failed to load skills for role {role_name}: {e}")
        return ""
