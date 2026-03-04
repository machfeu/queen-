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
from queen_core.prompt_builder import build_prompt, load_skills_for_role

logger = logging.getLogger("worker.unified")


def _get_role_from_payload(payload: Dict[str, Any]) -> str:
    """Extrait le nom du rôle depuis les constraints du payload."""
    constraints = payload.get("constraints", {})
    if isinstance(constraints, str):
        try:
            constraints = json.loads(constraints)
        except Exception:
            constraints = {}
    return constraints.get("role", "")


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
        workspace = payload.get("workspace", "/workspace/default")

        # Analyze existing files in workspace
        existing_files = []
        if os.path.exists(workspace):
            for root, dirs, files in os.walk(workspace):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), workspace)
                    existing_files.append(rel)
        payload["existing_files"] = existing_files

        # Build specialized prompt with role + skills + previous context
        role_name = _get_role_from_payload(payload)
        skills_text = load_skills_for_role(role_name) if role_name else ""
        job["payload"] = payload
        system, user = build_prompt(job, role_name=role_name, extra_skills=skills_text)

        result = generate_json(user, system=system)
        return result

    # ─── Codegen ──────────────────────────────────────────────────────────

    def handle_codegen(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Code generation job: create or modify code files."""
        payload = job.get("payload", {})
        workspace = payload.get("workspace", "/workspace/default")

        # Build specialized prompt
        role_name = _get_role_from_payload(payload)
        skills_text = load_skills_for_role(role_name) if role_name else ""
        system, user = build_prompt(job, role_name=role_name, extra_skills=skills_text)

        result = generate_json(
            user,
            system=system,
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

        # Self-heal: if tests failed, try auto-correction
        if not all_passed:
            try:
                from queen_core.self_heal import attempt_self_heal
                run_id = job.get("run_id", "")
                test_result = {"results": results, "all_passed": False}
                healed, heal_result = attempt_self_heal(
                    job=job,
                    test_result=test_result,
                    workspace=workspace,
                    attempt=1,
                    run_id=run_id,
                )
                if healed:
                    logger.info("Self-heal succeeded, returning healed results")
                    return {
                        "results": heal_result.get("retest_result", {}).get("results", results),
                        "all_passed": True,
                        "summary": f"Self-healed after {heal_result.get('attempt', 1)} attempt(s)",
                        "self_healed": True,
                        "heal_details": heal_result,
                    }
                else:
                    logger.info(f"Self-heal failed: {heal_result.get('status')}")
            except Exception as e:
                logger.warning(f"Self-heal error: {e}")

        return {
            "results": results,
            "all_passed": all_passed,
            "summary": "All checks passed" if all_passed else "Some checks failed",
        }

    # ─── Eval ─────────────────────────────────────────────────────────────

    def handle_eval(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluation job: assess quality using multi-evaluator consensus."""
        payload = job.get("payload", {})
        run_id = job.get("run_id", "")

        # Collect context for consensus evaluation
        previous_context = payload.get("previous_context", "")
        context = {
            "goal_title": payload.get("goal_title", ""),
            "goal_description": payload.get("goal_description", ""),
            "success_criteria": payload.get("success_criteria", ""),
            "result_summary": previous_context or payload.get("description", ""),
        }

        try:
            from queen_core.consensus import evaluate_with_consensus
            from queen_core.notifier import notify, NotifyEvent

            result = evaluate_with_consensus(
                context=context,
                num_evaluators=3,
                run_id=run_id,
            )

            # Notify if evaluators disagree significantly
            if result.get("score_spread", 0) > 0.3:
                notify(NotifyEvent.CONSENSUS_DISAGREEMENT, {
                    "run_id": run_id,
                    "scores": str(result.get("scores", [])),
                    "spread": str(result.get("score_spread", 0)),
                })

            # Map to expected output format
            return {
                "score": result.get("consensus_score", 0.0),
                "verdict": result.get("consensus_verdict", "retry"),
                "criteria_scores": {
                    r.get("focus", "unknown"): r.get("score", 0.0)
                    for r in result.get("individual_results", [])
                },
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "consensus": {
                    "num_evaluators": result.get("num_evaluators", 0),
                    "approvals": result.get("approvals", 0),
                    "rejections": result.get("rejections", 0),
                    "score_spread": result.get("score_spread", 0),
                },
            }
        except ImportError:
            # Fallback: single eval if consensus module not available
            role_name = _get_role_from_payload(payload)
            system, user = build_prompt(job, role_name=role_name)
            return generate_json(user, system=system)

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
