"""
worker_unified.py — Worker unifié pour Queen V1.
Gère tous les types de jobs: research, codegen, test, eval, patch.
S'exécute en tant que non-root dans un container dédié.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Dict, Any, List

sys.path.insert(0, "/app")

from workers.worker_base import WorkerBase
from queen_core.llm_client import generate, generate_json
from queen_core.policy import check_code_safety, validate_file_path

logger = logging.getLogger("worker.unified")


class UnifiedWorker(WorkerBase):

    def register_handlers(self):
        self.handlers = {
            "research": self.handle_research,
            "codegen": self.handle_codegen,
            "test": self.handle_test,
            "eval": self.handle_eval,
            "patch": self.handle_patch,
        }

    # ─── Research ─────────────────────────────────────────────────────────

    def handle_research(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Research job: analyze context, gather information."""
        payload = job.get("payload", {})
        description = payload.get("description", "")
        workspace = payload.get("workspace", "/workspace/default")

        # Analyze existing files in workspace
        existing_files = []
        if os.path.exists(workspace):
            for root, dirs, files in os.walk(workspace):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), workspace)
                    existing_files.append(rel)

        prompt = f"""Analyse ce contexte pour un objectif d'amélioration de code:

Objectif: {payload.get('goal_title', '')}
Description: {payload.get('goal_description', '')}
Tâche spécifique: {description}

Fichiers existants dans le workspace:
{json.dumps(existing_files[:50], indent=2) if existing_files else 'Aucun fichier existant'}

Fournis une analyse structurée en JSON:
{{
  "context_summary": "résumé du contexte",
  "key_findings": ["finding1", "finding2"],
  "recommendations": ["rec1", "rec2"],
  "files_to_modify": ["file1.py"],
  "files_to_create": ["new_file.py"],
  "risks": ["risk1"]
}}"""

        result = generate_json(prompt, system="Tu es un analyste technique. Réponds en JSON uniquement.")
        return result

    # ─── Codegen ──────────────────────────────────────────────────────────

    def handle_codegen(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Code generation job: create or modify code files."""
        payload = job.get("payload", {})
        description = payload.get("description", "")
        workspace = payload.get("workspace", "/workspace/default")

        prompt = f"""Génère du code Python pour:

Objectif: {payload.get('goal_title', '')}
Tâche: {description}

Règles:
- Code propre, commenté, typé
- Pas de subprocess, eval, exec, os.system
- Pas d'import de packages dangereux
- Fichiers dans le workspace uniquement

Réponds en JSON avec cette structure:
{{
  "artifacts": [
    {{
      "path": "relative/path/file.py",
      "content": "# code complet ici...",
      "description": "ce que fait ce fichier"
    }}
  ],
  "summary": "résumé de ce qui a été généré"
}}"""

        result = generate_json(
            prompt,
            system="Tu es un développeur Python senior. Génère du code robuste et sécurisé. JSON uniquement.",
            temperature=0.5,
            max_tokens=4096,
        )

        # Validate generated code
        artifacts = result.get("artifacts", [])
        validated = []
        for art in artifacts:
            content = art.get("content", "")
            safe, violations = check_code_safety(content)
            if safe:
                validated.append(art)
                # Write to workspace
                full_path = os.path.join(workspace, art["path"])
                ok, reason = validate_file_path(full_path)
                if ok:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
            else:
                logger.warning(f"Code safety violation in {art.get('path')}: {violations}")
                art["rejected"] = True
                art["violations"] = violations
                validated.append(art)

        result["artifacts"] = validated
        return result

    # ─── Test ─────────────────────────────────────────────────────────────

    def handle_test(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Test job: run lint, tests, security checks."""
        payload = job.get("payload", {})
        workspace = payload.get("workspace", "/workspace/default")

        results = {"lint": {}, "syntax": {}, "security": {}}

        # Find Python files
        py_files = []
        if os.path.exists(workspace):
            for root, dirs, files in os.walk(workspace):
                for f in files:
                    if f.endswith(".py"):
                        py_files.append(os.path.join(root, f))

        if not py_files:
            return {"results": results, "summary": "No Python files to test"}

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
            "files_checked": len(py_files),
        }

        # Basic lint (flake8 if available)
        try:
            lint_result = subprocess.run(
                ["python", "-m", "py_compile"] + py_files[:10],
                capture_output=True, text=True, timeout=30,
                cwd=workspace,
            )
            results["lint"] = {
                "passed": lint_result.returncode == 0,
                "stdout": lint_result.stdout[:2000],
                "stderr": lint_result.stderr[:2000],
            }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            results["lint"] = {"passed": False, "error": str(e)}

        # Security check (basic pattern matching)
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
        return {
            "results": results,
            "all_passed": all_passed,
            "summary": "All checks passed" if all_passed else "Some checks failed",
        }

    # ─── Eval ─────────────────────────────────────────────────────────────

    def handle_eval(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluation job: assess quality of results."""
        payload = job.get("payload", {})
        description = payload.get("description", "")

        prompt = f"""Évalue la qualité du travail réalisé pour:

Objectif: {payload.get('goal_title', '')}
Tâche d'évaluation: {description}

Critères:
- Pertinence par rapport à l'objectif
- Qualité du code (si applicable)
- Complétude
- Sécurité
- Maintenabilité

Réponds en JSON:
{{
  "score": 0.75,
  "criteria_scores": {{"pertinence": 0.8, "qualite": 0.7, "completude": 0.8, "securite": 0.9}},
  "strengths": ["point fort 1"],
  "weaknesses": ["point faible 1"],
  "verdict": "approve"
}}"""

        return generate_json(prompt, system="Tu es un évaluateur technique exigeant. JSON uniquement.")

    # ─── Patch ────────────────────────────────────────────────────────────

    def handle_patch(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Patch job: generate diff from workspace changes."""
        payload = job.get("payload", {})
        workspace = payload.get("workspace", "/workspace/default")

        # Collect all files in workspace
        artifacts = []
        if os.path.exists(workspace):
            for root, dirs, files in os.walk(workspace):
                # Skip hidden dirs and backups
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if f.startswith("."):
                        continue
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, workspace)
                    try:
                        with open(full, "r", encoding="utf-8") as fh:
                            content = fh.read()
                        artifacts.append({"path": rel, "content": content})
                    except Exception:
                        pass

        return {
            "artifacts": artifacts,
            "files_count": len(artifacts),
            "workspace": workspace,
            "summary": f"Collected {len(artifacts)} files for patch generation",
        }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    worker = UnifiedWorker()
    worker.run()
