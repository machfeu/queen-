"""
self_heal.py — Auto-correction des échecs de test.
Inspiré d'Emergent AI (self-healing) + AutoGen (délégation inter-agents).

Quand un job test/syntax échoue, self_heal :
1. Analyse l'erreur
2. Demande au LLM de proposer un fix
3. Applique le fix dans le workspace
4. Relance le test
5. Si ça échoue encore → escalade (le run est marqué "needs_review")

Maximum 2 tentatives d'auto-correction par job.

Usage:
    from queen_core.self_heal import attempt_self_heal
    healed, result = attempt_self_heal(job, test_result, workspace)
"""

import json
import logging
import os
from typing import Dict, Any, Tuple, Optional

from queen_core.llm_client import generate_json
from queen_core.policy import check_code_safety, validate_file_path
# Notifications (optional)
try:
    from queen_core.notifier import notify, NotifyEvent
except Exception:  # pragma: no cover
    def notify(*args, **kwargs):
        return
    class NotifyEvent:  # type: ignore
        SELF_HEAL_TRIGGERED = 'self_heal_triggered'


logger = logging.getLogger("queen.self_heal")

MAX_HEAL_ATTEMPTS = 2

HEAL_PROMPT = """Un test a échoué. Analyse l'erreur et propose un correctif MINIMAL.

Fichier en erreur: {file_path}
Type d'erreur: {error_type}
Message d'erreur:
{error_message}

Code actuel du fichier:
```python
{file_content}
```

Règles:
- Fix MINIMAL : ne change que ce qui est nécessaire
- Ne casse pas d'autres fonctionnalités
- Pas de eval(), exec(), subprocess, os.system
- Garde le même style de code

Réponds en JSON:
{{
  "diagnosis": "explication courte du bug",
  "fix_description": "ce que le fix change",
  "fixed_content": "le code complet corrigé du fichier",
  "confidence": 0.8
}}"""


def attempt_self_heal(
    job: Dict[str, Any],
    test_result: Dict[str, Any],
    workspace: str,
    attempt: int = 1,
    run_id: str = "",
) -> Tuple[bool, Dict[str, Any]]:
    """
    Tente de corriger automatiquement un échec de test.

    Args:
        job: Le job qui a échoué
        test_result: Résultat du test avec les erreurs
        workspace: Chemin du workspace
        attempt: Numéro de tentative (1 ou 2)
        run_id: ID du run pour le tracking

    Returns:
        (healed, result) — healed=True si le fix a réussi
    """
    if attempt > MAX_HEAL_ATTEMPTS:
        logger.info(f"Self-heal: max attempts reached ({MAX_HEAL_ATTEMPTS}), escalating")
        return False, {"status": "escalated", "attempts": attempt - 1}

    # Notifier
    notify(NotifyEvent.SELF_HEAL_TRIGGERED, {
        "run_id": run_id,
        "attempt": attempt,
    })

    # Extraire les erreurs du test_result
    errors = _extract_errors(test_result)
    if not errors:
        logger.info("Self-heal: no actionable errors found")
        return False, {"status": "no_errors_found"}

    fixes_applied = 0
    fixes_failed = 0

    for error in errors[:3]:  # Max 3 fichiers par tentative
        file_path = error.get("file_path", "")
        if not file_path:
            continue

        # Lire le fichier actuel
        full_path = _resolve_path(file_path, workspace)
        if not full_path or not os.path.isfile(full_path):
            logger.warning(f"Self-heal: file not found: {file_path}")
            fixes_failed += 1
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                current_content = f.read()
        except Exception as e:
            logger.warning(f"Self-heal: cannot read {file_path}: {e}")
            fixes_failed += 1
            continue

        # Demander un fix au LLM
        try:
            fix_result = _ask_llm_for_fix(
                file_path=file_path,
                error_type=error.get("type", "unknown"),
                error_message=error.get("message", ""),
                file_content=current_content,
                run_id=run_id,
            )
        except Exception as e:
            logger.warning(f"Self-heal: LLM fix failed for {file_path}: {e}")
            fixes_failed += 1
            continue

        # Valider le fix
        fixed_content = fix_result.get("fixed_content", "")
        confidence = float(fix_result.get("confidence", 0.0))

        if not fixed_content or confidence < 0.5:
            logger.info(f"Self-heal: low confidence fix ({confidence}) for {file_path}, skipping")
            fixes_failed += 1
            continue

        # Vérifier la sécurité du code fixé
        safe, violations = check_code_safety(fixed_content)
        if not safe:
            logger.warning(f"Self-heal: fix for {file_path} has safety violations: {violations}")
            fixes_failed += 1
            continue

        # Appliquer le fix
        ok, reason = validate_file_path(full_path)
        if not ok:
            logger.warning(f"Self-heal: path validation failed: {reason}")
            fixes_failed += 1
            continue

        try:
            # Backup avant modification
            backup_dir = os.path.join(workspace, ".queen_backups", "self_heal", run_id or "no_run")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, os.path.basename(file_path) + f".attempt{attempt}")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(current_content)

            # Écrire le fix
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            fixes_applied += 1
            logger.info(
                f"Self-heal: applied fix to {file_path} "
                f"(confidence={confidence:.2f}, diagnosis={fix_result.get('diagnosis', '?')})"
            )
        except Exception as e:
            logger.warning(f"Self-heal: failed to write fix to {file_path}: {e}")
            fixes_failed += 1

    if fixes_applied == 0:
        return False, {
            "status": "no_fixes_applied",
            "errors_found": len(errors),
            "fixes_failed": fixes_failed,
            "attempt": attempt,
        }

    # Re-tester après les fixes
    retest_result = _retest(workspace)

    if retest_result.get("all_passed", False):
        logger.info(f"Self-heal: SUCCESS after attempt {attempt} ({fixes_applied} fixes)")
        return True, {
            "status": "healed",
            "attempt": attempt,
            "fixes_applied": fixes_applied,
            "retest_result": retest_result,
        }
    else:
        logger.info(f"Self-heal: attempt {attempt} failed, retrying...")
        # Récursion avec attempt+1
        return attempt_self_heal(
            job=job,
            test_result=retest_result,
            workspace=workspace,
            attempt=attempt + 1,
            run_id=run_id,
        )


def _extract_errors(test_result: Dict[str, Any]) -> list:
    """Extrait les erreurs actionnables d'un résultat de test."""
    errors = []

    results = test_result.get("results", {})

    # Erreurs de syntaxe
    syntax = results.get("syntax", {})
    for err_str in syntax.get("errors", []):
        # Format attendu : "filepath: SyntaxError: ..."
        parts = err_str.split(":", 1)
        if len(parts) >= 2:
            errors.append({
                "file_path": parts[0].strip(),
                "type": "SyntaxError",
                "message": parts[1].strip(),
            })

    # Issues de sécurité
    security = results.get("security", {})
    for issue_str in security.get("issues", []):
        parts = issue_str.split(":", 1)
        if len(parts) >= 2:
            errors.append({
                "file_path": parts[0].strip(),
                "type": "SecurityIssue",
                "message": parts[1].strip(),
            })

    # Erreurs de lint
    lint = results.get("lint", {})
    if not lint.get("passed", True) and lint.get("stderr"):
        errors.append({
            "file_path": "unknown",
            "type": "LintError",
            "message": lint["stderr"][:500],
        })

    return errors


def _ask_llm_for_fix(
    file_path: str,
    error_type: str,
    error_message: str,
    file_content: str,
    run_id: str = "",
) -> Dict[str, Any]:
    """Demande au LLM de proposer un fix."""
    # Tronquer le contenu si trop long
    if len(file_content) > 5000:
        file_content = file_content[:5000] + "\n# ... [tronqué]"

    prompt = HEAL_PROMPT.format(
        file_path=file_path,
        error_type=error_type,
        error_message=error_message[:1000],
        file_content=file_content,
    )

    return generate_json(
        prompt,
        system=(
            "Tu es un debugger Python expert. Tu corriges les bugs avec des "
            "modifications minimales. Tu ne changes JAMAIS plus que nécessaire. "
            "Tu réponds UNIQUEMENT en JSON valide."
        ),
        temperature=0.2,
        max_tokens=4096,
        run_id=run_id,
    )


def _retest(workspace: str) -> Dict[str, Any]:
    """Relance les tests de base sur le workspace."""
    import subprocess

    results = {"syntax": {}, "security": {}}

    # Trouver les fichiers Python
    py_files = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    if not py_files:
        return {"all_passed": True, "results": results, "note": "No Python files"}

    # Syntax check
    syntax_errors = []
    for fp in py_files:
        try:
            with open(fp, "r") as f:
                compile(f.read(), fp, "exec")
        except SyntaxError as e:
            syntax_errors.append(f"{fp}: {e}")

    results["syntax"] = {
        "passed": len(syntax_errors) == 0,
        "errors": syntax_errors,
    }

    # Security check
    security_issues = []
    for fp in py_files:
        try:
            with open(fp, "r") as f:
                content = f.read()
            safe, violations = check_code_safety(content)
            if not safe:
                security_issues.extend([f"{fp}: {v}" for v in violations])
        except Exception:
            pass

    results["security"] = {
        "passed": len(security_issues) == 0,
        "issues": security_issues,
    }

    all_passed = all(
        r.get("passed", False) for r in results.values() if isinstance(r, dict)
    )

    return {"all_passed": all_passed, "results": results}


def _resolve_path(file_path: str, workspace: str) -> Optional[str]:
    """Résout un chemin de fichier relatif ou absolu dans le workspace."""
    if os.path.isabs(file_path):
        if file_path.startswith(workspace):
            return file_path
        return None

    full = os.path.join(workspace, file_path)
    if os.path.isfile(full):
        return full

    # Chercher le fichier par nom
    basename = os.path.basename(file_path)
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if basename in files:
            return os.path.join(root, basename)

    return None
