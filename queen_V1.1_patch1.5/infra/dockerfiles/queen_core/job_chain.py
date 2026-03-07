"""
job_chain.py — Chaînage des résultats entre jobs d'un même run.
Inspiré d'OpenManus : l'output d'une étape devient l'input de la suivante.

Le contexte est résumé automatiquement s'il dépasse MAX_CONTEXT_CHARS
pour ne pas exploser la fenêtre du LLM.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("queen.job_chain")

MAX_CONTEXT_CHARS = 4000  # ~1000 tokens


def collect_previous_results(
    memory,  # Memory instance
    run_id: str,
    current_step: int,
) -> str:
    """
    Collecte les résultats des jobs précédents (step < current_step)
    du même run, et les formate en contexte textuel.

    Retourne un bloc de texte prêt à être injecté dans le prompt LLM.
    """
    jobs = memory.list_jobs(run_id=run_id)
    if not jobs:
        return ""

    previous = []
    for j in jobs:
        payload = j.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        job_step = payload.get("step", 0)
        if job_step >= current_step:
            continue
        if j.get("status") != "success":
            continue

        result = j.get("result", {})
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {"raw": result}

        previous.append({
            "step": job_step,
            "type": j.get("job_type", "unknown"),
            "title": payload.get("title", ""),
            "result": result,
        })

    if not previous:
        return ""

    previous.sort(key=lambda x: x["step"])

    # Build context text
    parts = ["=== Résultats des étapes précédentes ===\n"]
    for p in previous:
        result_text = _format_result(p["result"])
        parts.append(
            f"--- Étape {p['step']} ({p['type']}): {p['title']} ---\n"
            f"{result_text}\n"
        )

    context = "\n".join(parts)

    # Summarize if too long
    if len(context) > MAX_CONTEXT_CHARS:
        context = _truncate_context(context, previous)

    return context


def _format_result(result: Any) -> str:
    """Formate un résultat de job en texte lisible."""
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        # Extraire les champs utiles
        useful_keys = ["summary", "analysis", "findings", "artifacts", "recommendations"]
        extracted = {}
        for k in useful_keys:
            if k in result:
                extracted[k] = result[k]

        if extracted:
            return json.dumps(extracted, indent=2, ensure_ascii=False, default=str)

        # Fallback: tout le dict mais tronqué
        full = json.dumps(result, indent=2, ensure_ascii=False, default=str)
        if len(full) > 2000:
            return full[:2000] + "\n... [tronqué]"
        return full

    return str(result)[:1000]


def _truncate_context(context: str, previous: List[Dict]) -> str:
    """
    Résumé compressé quand le contexte est trop long.
    Garde le summary de chaque étape + les noms d'artifacts.
    """
    parts = ["=== Résumé des étapes précédentes (compressé) ===\n"]
    for p in previous:
        result = p["result"]
        summary = ""
        if isinstance(result, dict):
            summary = result.get("summary", "")
            # List artifact paths if available
            artifacts = result.get("artifacts", [])
            if isinstance(artifacts, list):
                art_paths = [
                    a.get("path", "?") for a in artifacts
                    if isinstance(a, dict)
                ]
                if art_paths:
                    summary += f" | Fichiers: {', '.join(art_paths[:10])}"

        if not summary:
            summary = str(result)[:200] + "..."

        parts.append(f"Étape {p['step']} ({p['type']}): {summary}")

    return "\n".join(parts)


def enrich_job_payload(
    memory,
    job: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrichit le payload d'un job avec le contexte des étapes précédentes.
    À appeler juste avant de dispatch un job.

    Modifie le payload in-place en ajoutant la clé 'previous_context'.
    """
    payload = job.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    run_id = job.get("run_id", "")
    step = payload.get("step", 0)

    if run_id and step > 1:
        context = collect_previous_results(memory, run_id, step)
        if context:
            payload["previous_context"] = context
            logger.info(f"Injected {len(context)} chars context into job step {step}")

    job["payload"] = payload
    return job
