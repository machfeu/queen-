"""
orchestrator.py — Cerveau principal de Queen V1.
Coordonne: Goal → Plan → Jobs → Scoring → Patch → Gates → Approval.

Le "Queen Zero" (noyau stable) n'est JAMAIS modifié.
Toute mutation passe par /workspace + validation.
"""

import json
import logging
import os
import signal
import sys
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent to path for queen_core imports
sys.path.insert(0, "/app")

from queen_core.models import Goal, Run, Job, Patch, GoalStatus, JobStatus, RunStatus, PatchStatus
from queen_core.memory import Memory
from queen_core.planner import create_plan
from queen_core.evaluator import evaluate_run
from queen_core.patcher import generate_patch_from_artifacts
from queen_core.policy import validate_goal_constraints, get_job_budget, validate_file_path
from queen_core.job_chain import enrich_job_payload
from queen_core.budget_tracker import get_tracker
from queen_core import redis_bus

# Notifications (patch 1.4)
try:
    from queen_core.notifier import notify, NotifyEvent
except Exception:  # graceful fallback
    def notify(*args, **kwargs):
        return
    class NotifyEvent:  # type: ignore
        RUN_STARTED = 'run_started'
        RUN_COMPLETED = 'run_completed'
        RUN_FAILED = 'run_failed'
        PATCH_READY = 'patch_ready'
        PATCH_APPROVED = 'patch_approved'
        PATCH_APPLIED = 'patch_applied'
        PATCH_REJECTED = 'patch_rejected'
        BUDGET_WARNING = 'budget_warning'
        BUDGET_EXCEEDED = 'budget_exceeded'
        GOAL_COMPLETED = 'goal_completed'

_budget_warned_runs = set()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("queen.orchestrator")

# ─── State ────────────────────────────────────────────────────────────────────

memory: Optional[Memory] = None
_shutdown = threading.Event()


def init():
    global memory
    os.makedirs("/data", exist_ok=True)
    os.makedirs("/workspace", exist_ok=True)
    memory = Memory("/data/queen.db")
    logger.info("🐝 Queen V1 Orchestrator initialized")
    redis_bus.publish_log("info", "orchestrator", "Queen V1 Orchestrator started")



# ─── Budget defaults (patch 1.3) ──────────────────────────────────────────────

def _budget_limits_from_constraints(constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Return budget limits for BudgetTracker.check_budget()."""
    constraints = constraints or {}
    # User-provided overrides
    max_tokens = int(constraints.get("max_tokens", 0) or 0)
    max_seconds = float(constraints.get("max_seconds", 0) or 0)
    max_cost_usd = float(constraints.get("max_cost_usd", 0) or 0)
    max_llm_calls = int(constraints.get("max_llm_calls", 0) or 0)

    # Defaults by risk_level (conservative)
    risk = (constraints.get("risk_level") or "medium").lower()
    defaults = {
        "low":      {"max_tokens": 200_000, "max_seconds": 3600, "max_cost_usd": 5.0,  "max_llm_calls": 120},
        "medium":   {"max_tokens": 100_000, "max_seconds": 1800, "max_cost_usd": 2.0,  "max_llm_calls": 80},
        "high":     {"max_tokens": 50_000,  "max_seconds": 900,  "max_cost_usd": 1.0,  "max_llm_calls": 40},
        "critical": {"max_tokens": 25_000,  "max_seconds": 600,  "max_cost_usd": 0.5,  "max_llm_calls": 20},
    }.get(risk, {"max_tokens": 100_000, "max_seconds": 1800, "max_cost_usd": 2.0, "max_llm_calls": 80})

    return {
        "max_tokens": max_tokens or defaults["max_tokens"],
        "max_seconds": max_seconds or defaults["max_seconds"],
        "max_cost_usd": max_cost_usd or defaults["max_cost_usd"],
        "max_llm_calls": max_llm_calls or defaults["max_llm_calls"],
    }

# ─── Goal Ingestion ──────────────────────────────────────────────────────────

def ingest_goal(goal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept a new goal, validate it, store it, and trigger planning.
    Called from the API.
    """
    goal = Goal(
        title=goal_data.get("title", "Untitled"),
        description=goal_data.get("description", ""),
        constraints=validate_goal_constraints(goal_data.get("constraints", {})),
    )
    memory.create_goal(goal)
    logger.info(f"📥 Goal ingested: {goal.id} — {goal.title}")
    redis_bus.publish_event("goal_created", {"goal_id": goal.id, "title": goal.title})

    # Start planning in background
    threading.Thread(target=_process_goal, args=(goal.id,), daemon=True).start()

    return {"goal_id": goal.id, "status": "pending"}


# ─── Main Processing Pipeline ────────────────────────────────────────────────

def _process_goal(goal_id: str):
    """Full pipeline: plan → dispatch → collect → evaluate → patch."""
    try:
        goal = memory.get_goal(goal_id)
        if not goal:
            logger.error(f"Goal {goal_id} not found")
            return

        # Step 1: Planning
        memory.update_goal_status(goal_id, GoalStatus.PLANNING.value)
        redis_bus.publish_log("info", "orchestrator", f"Planning goal: {goal_id}")

        plan_result = create_plan(goal)
        logger.info(f"📋 Plan created for {goal_id}: {plan_result.get('plan_summary', '')}")

        # Step 2: Create Run
        run = Run(goal_id=goal_id, plan=plan_result.get("jobs", []))
        memory.create_run(run)

        memory.update_goal_status(goal_id, GoalStatus.RUNNING.value)
        redis_bus.publish_event("run_started", {"run_id": run.id, "goal_id": goal_id})

        notify(NotifyEvent.RUN_STARTED, {"run_id": run.id, "goal_title": goal.get("title", "")})

        # Step 3: Create and dispatch jobs
        job_map = {}  # step -> job_id
        plan_jobs = plan_result.get("jobs", [])

        for job_spec in plan_jobs:
            job = Job(
                run_id=run.id,
                goal_id=goal_id,
                job_type=job_spec.get("job_type", "research"),
                payload={
                    "title": job_spec.get("title", ""),
                    "description": job_spec.get("description", ""),
                    "step": job_spec.get("step", 0),
                    "depends_on": job_spec.get("depends_on", []),
                    "goal_title": goal.get("title", ""),
                    "goal_description": goal.get("description", ""),
                    "constraints": goal.get("constraints", {}),
                    "role": goal.get("constraints", {}).get("role", ""),
                    "success_criteria": goal.get("constraints", {}).get("success_criteria", ""),
                    "workspace": f"/workspace/{goal_id}",
                },
                timeout_seconds=max(1, min(
                    job_spec.get("estimated_duration_seconds", 300),
                    goal.get("constraints", {}).get("timeout", 300),
                )),
            )
            memory.create_job(job)
            job_map[job_spec.get("step", 0)] = job.id

        # Step 4: Dispatch jobs respecting dependencies
        _dispatch_jobs(run.id, plan_jobs, job_map)

        # Step 5: Wait for all jobs to complete
        _wait_for_jobs(run.id)

        # If run was stopped (budget / shutdown), abort pipeline
        run_state = memory.get_run(run.id)
        if run_state and run_state.get("status") in (RunStatus.REJECTED.value, RunStatus.ROLLED_BACK.value):
            return

        # Step 6: Evaluate
        redis_bus.publish_log("info", "orchestrator", f"Evaluating run: {run.id}")
        all_jobs = memory.list_jobs(run_id=run.id)
        eval_result = evaluate_run(goal, all_jobs)

        memory.update_run(
            run.id,
            score=eval_result.get("score", 0.0),
            score_justification=json.dumps(eval_result, ensure_ascii=False),
        )

        # Step 7: Generate patch if verdict is approve
        verdict = eval_result.get("verdict", "reject")
        if verdict == "approve":
            _generate_and_gate_patch(run.id, goal_id, all_jobs)
        elif verdict == "retry":
            memory.update_run(run.id, status=RunStatus.GATES_FAILED.value)
            redis_bus.publish_log("warn", "orchestrator",
                                  f"Run {run.id} scored too low ({eval_result.get('score')}), retry recommended")
        else:
            memory.update_run(run.id, status=RunStatus.GATES_FAILED.value,
                              finished_at=datetime.utcnow().isoformat())
            memory.update_goal_status(goal_id, GoalStatus.FAILED.value)

        try:
            notify(NotifyEvent.RUN_COMPLETED, {
                "run_id": run.id,
                "score": str(eval_result.get("score", 0)),
                "verdict": verdict,
            })
        except Exception:
            pass

        redis_bus.publish_event("run_finished", {
            "run_id": run.id, "goal_id": goal_id,
            "score": eval_result.get("score", 0), "verdict": verdict,
        })

    except Exception as e:
        logger.exception(f"Pipeline error for goal {goal_id}: {e}")
        redis_bus.publish_log("error", "orchestrator", f"Pipeline error: {e}")
        try:
            notify(NotifyEvent.RUN_FAILED, {"run_id": str(goal_id), "reason": str(e)[:500]})
        except Exception:
            pass
        try:
            memory.update_goal_status(goal_id, GoalStatus.FAILED.value)
        except Exception:
            pass


def _dispatch_jobs(run_id: str, plan_jobs, job_map):
    """Dispatch jobs to Redis queue, respecting dependency order."""
    dispatched = set()
    remaining = list(plan_jobs)
    max_rounds = len(remaining) + 1

    for _ in range(max_rounds):
        if not remaining:
            break
        for job_spec in list(remaining):
            step = job_spec.get("step", 0)
            depends = job_spec.get("depends_on", [])

            # Check if all dependencies are dispatched
            if all(d in dispatched for d in depends):
                job_id = job_map.get(step)
                if job_id:
                    job = memory.get_job(job_id)
                    if job:
                        # Inject context from previous steps
                        job = enrich_job_payload(memory, job)
                        redis_bus.enqueue_job(job)
                        memory.update_job(job_id, status=JobStatus.QUEUED.value)
                        logger.info(f"📤 Dispatched job {job_id} (step {step})")
                dispatched.add(step)
                remaining.remove(job_spec)


def _wait_for_jobs(run_id: str, timeout: int = 1800):
    """Wait for all jobs in a run to complete."""
    start = time.time()
    while time.time() - start < timeout:
        if _shutdown.is_set():
            return

        # Process results from Redis
        result = redis_bus.pop_result(timeout=2)
        if result:
            job_id = result.get("job_id", "")
            if job_id:
                job = memory.get_job(job_id)
                if job and job["run_id"] == run_id:
                    memory.update_job(
                        job_id,
                        status=result.get("status", "failed"),
                        result=result.get("result", {}),
                        logs=result.get("logs", ""),
                        worker_id=result.get("worker_id", ""),
                        finished_at=datetime.utcnow().isoformat(),
                    )

        # Budget check (tokens/time/cost/calls)
        try:
            run = memory.get_run(run_id)
            goal = memory.get_goal(run.get("goal_id", "")) if run else None
            constraints = (goal or {}).get("constraints", {})
            limits = _budget_limits_from_constraints(constraints)
            tracker = get_tracker()
            chk = tracker.check_budget(run_id, **limits)
            if chk.get("exceeded"):
                # Cancel remaining jobs
                for j in memory.list_jobs(run_id=run_id):
                    if j.get("status") not in {"success", "failed", "timeout", "cancelled"}:
                        memory.update_job(j["id"], status=JobStatus.CANCELLED.value, logs=f"Budget exceeded: {chk.get('reasons')}" )
                memory.update_run(run_id, status=RunStatus.REJECTED.value, finished_at=datetime.utcnow().isoformat())
                redis_bus.publish_log("warning", "orchestrator", f"Run {run_id} stopped: budget exceeded {chk.get('reasons')}")
                return
        except Exception:
            pass

        # Budget warning (one-shot)
        try:
            run = memory.get_run(run_id)
            goal = memory.get_goal(run.get("goal_id", "")) if run else None
            constraints = (goal or {}).get("constraints", {})
            limits = _budget_limits_from_constraints(constraints)
            tracker = get_tracker()
            b = tracker.get_budget(run_id) or {}
            if b and run_id not in _budget_warned_runs:
                # compute max utilization across tracked dimensions
                pct = 0.0
                if limits.get("max_tokens"):
                    pct = max(pct, float(b.get("total_tokens", 0)) / float(limits["max_tokens"]))
                if limits.get("max_llm_calls"):
                    pct = max(pct, float(b.get("llm_calls", 0)) / float(limits["max_llm_calls"]))
                if limits.get("max_seconds"):
                    pct = max(pct, float(b.get("elapsed_seconds", 0)) / float(limits["max_seconds"]))
                if limits.get("max_cost_usd"):
                    pct = max(pct, float(b.get("estimated_cost_usd", 0)) / float(limits["max_cost_usd"]))
                if pct >= 0.80:
                    _budget_warned_runs.add(run_id)
                    notify(NotifyEvent.BUDGET_WARNING, {
                        "run_id": run_id,
                        "percent": int(pct * 100),
                        "tokens": b.get("total_tokens", 0),
                        "cost": b.get("estimated_cost_usd", 0),
                    })
        except Exception:
            pass

        # Check if all jobs are done
        jobs = memory.list_jobs(run_id=run_id)
        terminal = {"success", "failed", "timeout", "cancelled"}
        if all(j["status"] in terminal for j in jobs):
            return

    logger.warning(f"Timeout waiting for jobs in run {run_id}")


def _generate_and_gate_patch(run_id: str, goal_id: str, jobs):
    """Generate patch from codegen artifacts and run gates."""
    # Collect artifacts from codegen jobs
    artifacts = []
    for job in jobs:
        if job["job_type"] == "codegen" and job["status"] == "success":
            result = job.get("result", {})
            if isinstance(result, dict) and "artifacts" in result:
                artifacts.extend(result["artifacts"])

    if not artifacts:
        logger.info(f"No artifacts to patch for run {run_id}")
        memory.update_run(run_id, status=RunStatus.GATES_PASSED.value,
                          finished_at=datetime.utcnow().isoformat())
        return

    # Generate diff
    workspace_path = f"/workspace/{goal_id}"
    os.makedirs(workspace_path, exist_ok=True)
    diff = generate_patch_from_artifacts(artifacts, workspace_path)

    # Create patch record
    patch = Patch(
        run_id=run_id,
        goal_id=goal_id,
        diff_content=diff,
        status=PatchStatus.GATES_RUNNING.value,
    )
    memory.create_patch(patch)
    memory.update_run(run_id, patch_id=patch.id, status=RunStatus.GATES_PENDING.value)

    # Run gates (lint, tests, security)
    gate_results = _run_gates(artifacts, goal_id)
    memory.update_patch(patch.id, gate_results=gate_results)

    all_passed = all(g.get("passed", False) for g in gate_results.values())
    if all_passed:
        memory.update_patch(patch.id, status=PatchStatus.GATES_PASSED.value)
        memory.update_run(run_id, status=RunStatus.GATES_PASSED.value)
        redis_bus.publish_event("patch_ready", {
            "patch_id": patch.id, "run_id": run_id, "goal_id": goal_id,
        })
        redis_bus.publish_log("info", "orchestrator",
                              f"✅ Patch {patch.id} passed all gates — awaiting approval")

        try:
            run_state = memory.get_run(run_id)
            notify(NotifyEvent.PATCH_READY, {
                "run_id": run_id,
                "score": str(run_state.get("score", "")) if run_state else "",
            })
        except Exception:
            pass
    else:
        memory.update_patch(patch.id, status=PatchStatus.GATES_FAILED.value)
        memory.update_run(run_id, status=RunStatus.GATES_FAILED.value,
                          finished_at=datetime.utcnow().isoformat())
        redis_bus.publish_log("warn", "orchestrator",
                              f"❌ Patch {patch.id} failed gates: {json.dumps(gate_results)}")


def _run_gates(artifacts, goal_id: str) -> Dict[str, Any]:
    """Run quality gates on artifacts."""
    from queen_core.policy import check_code_safety

    results = {}

    # Gate 1: Code safety check
    all_safe = True
    safety_violations = []
    for art in artifacts:
        content = art.get("content", "")
        safe, violations = check_code_safety(content)
        if not safe:
            all_safe = False
            safety_violations.extend(violations)
    results["code_safety"] = {"passed": all_safe, "violations": safety_violations}

    # Gate 2: Basic syntax check (Python files)
    syntax_ok = True
    syntax_errors = []
    for art in artifacts:
        if art.get("path", "").endswith(".py"):
            try:
                compile(art.get("content", ""), art["path"], "exec")
            except SyntaxError as e:
                syntax_ok = False
                syntax_errors.append(f"{art['path']}: {e}")
    results["syntax_check"] = {"passed": syntax_ok, "errors": syntax_errors}

    # Gate 3: File path validation
    path_ok = True
    path_errors = []
    for art in artifacts:
        ok, reason = validate_file_path(f"/workspace/{goal_id}/{art.get('path', '')}")
        if not ok:
            path_ok = False
            path_errors.append(reason)
    results["path_validation"] = {"passed": path_ok, "errors": path_errors}

    return results


# ─── Actions (called from API) ───────────────────────────────────────────────

def approve_patch(patch_id: str, actor: str = "user") -> Dict[str, Any]:
    """Approve a patch for application."""
    patch = memory.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}
    if patch["status"] != PatchStatus.GATES_PASSED.value:
        return {"error": f"Patch status is {patch['status']}, expected gates_passed"}

    memory.update_patch(patch_id, status=PatchStatus.APPROVED.value, approved_by=actor)
    memory.audit("approve_patch", "patch", patch_id, actor=actor)
    redis_bus.publish_event("patch_approved", {"patch_id": patch_id})
    try:
        notify(NotifyEvent.PATCH_APPROVED, {"run_id": patch.get("run_id", ""), "patch_id": patch_id})
    except Exception:
        pass
    return {"status": "approved"}


def apply_patch(patch_id: str, actor: str = "user") -> Dict[str, Any]:
    """Apply an approved patch to workspace."""
    from queen_core.patcher import apply_patch as do_apply

    patch = memory.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}
    if patch["status"] != PatchStatus.APPROVED.value:
        return {"error": f"Patch status is {patch['status']}, expected approved"}

    result = do_apply(patch["diff_content"], f"/workspace/{patch['goal_id']}")

    if result.get("failed"):
        memory.update_patch(patch_id, status=PatchStatus.GATES_FAILED.value)
        return {"error": "Some files failed to apply", "details": result}

    now = datetime.utcnow().isoformat()
    memory.update_patch(patch_id, status=PatchStatus.APPLIED.value, applied_at=now)
    memory.update_run(patch["run_id"], status=RunStatus.APPLIED.value, finished_at=now)
    memory.update_goal_status(patch["goal_id"], GoalStatus.COMPLETED.value)
    memory.audit("apply_patch", "patch", patch_id, actor=actor, details=result)

    redis_bus.publish_event("patch_applied", {"patch_id": patch_id, "goal_id": patch["goal_id"]})
    try:
        notify(NotifyEvent.PATCH_APPLIED, {"run_id": patch.get("run_id", ""), "files_changed": result.get("files_applied", 0)})
        goal_obj = memory.get_goal(patch.get("goal_id", "")) if memory else None
        notify(NotifyEvent.GOAL_COMPLETED, {"goal_title": (goal_obj or {}).get("title", patch.get("goal_id", ""))})
    except Exception:
        pass
    return {"status": "applied", "details": result}


def reject_patch(patch_id: str, actor: str = "user", reason: str = "") -> Dict[str, Any]:
    """Reject a patch."""
    patch = memory.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}

    memory.update_patch(patch_id, status=PatchStatus.REJECTED.value)
    memory.audit("reject_patch", "patch", patch_id, actor=actor, details={"reason": reason})
    redis_bus.publish_event("patch_rejected", {"patch_id": patch_id})
    try:
        notify(NotifyEvent.PATCH_REJECTED, {"run_id": patch.get("run_id", ""), "reason": reason})
    except Exception:
        pass
    return {"status": "rejected"}


def rollback_patch(patch_id: str, actor: str = "user") -> Dict[str, Any]:
    """Rollback a previously applied patch."""
    from queen_core.patcher import rollback

    patch = memory.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}
    if patch["status"] != PatchStatus.APPLIED.value:
        return {"error": f"Can only rollback applied patches, current: {patch['status']}"}

    gate_results = patch.get("gate_results", {})
    # Look for backup dir in gate application results
    # For now, rollback based on patch ID
    backup_dir = f"/workspace/.queen_backups"
    if os.path.exists(backup_dir):
        # Find most recent backup
        backups = sorted(os.listdir(backup_dir), reverse=True)
        if backups:
            result = rollback(os.path.join(backup_dir, backups[0]),
                              f"/workspace/{patch['goal_id']}")
            memory.update_patch(patch_id, status=PatchStatus.ROLLED_BACK.value)
            memory.update_run(patch["run_id"], status=RunStatus.ROLLED_BACK.value)
            memory.audit("rollback_patch", "patch", patch_id, actor=actor, details=result)
            return {"status": "rolled_back", "details": result}

    return {"error": "No backup found for rollback"}


def pause_goal(goal_id: str) -> Dict[str, Any]:
    memory.update_goal_status(goal_id, GoalStatus.PAUSED.value)
    return {"status": "paused"}


def resume_goal(goal_id: str) -> Dict[str, Any]:
    memory.update_goal_status(goal_id, GoalStatus.RUNNING.value)
    return {"status": "running"}


def retry_job(job_id: str) -> Dict[str, Any]:
    """Re-queue a failed job."""
    job = memory.get_job(job_id)
    if not job:
        return {"error": "Job not found"}

    memory.update_job(job_id, status=JobStatus.QUEUED.value, started_at="", finished_at="")
    redis_bus.enqueue_job(job)
    return {"status": "requeued"}


# ─── Main Loop ────────────────────────────────────────────────────────────────

def run_forever():
    """Main orchestrator loop — processes results and manages state."""
    init()
    logger.info("🐝 Orchestrator main loop started")

    def handle_signal(sig, frame):
        logger.info("Shutting down...")
        _shutdown.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while not _shutdown.is_set():
        try:
            # NOTE: Les résultats de jobs sont consommés dans _wait_for_jobs(run_id).
            # Garder run_forever léger évite les pertes de résultats (double-consommation).
            time.sleep(1)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(5)

    logger.info("🐝 Orchestrator shut down")


if __name__ == "__main__":
    run_forever()
