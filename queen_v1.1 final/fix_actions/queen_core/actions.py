"""
actions.py — Actions autonomes pour le dashboard.
Ne dépend PAS de orchestrator.py (qui tourne dans un autre container).
Utilise une instance Memory lazy + thread-safe.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from queen_core.models import Goal, Run, Job, Patch, GoalStatus, JobStatus, RunStatus, PatchStatus
from queen_core.memory import Memory
from queen_core.policy import validate_goal_constraints
from queen_core import redis_bus

logger = logging.getLogger("queen.actions")

# ─── Lazy singleton Memory ────────────────────────────────────────────────────

_memory: Optional[Memory] = None
_memory_lock = threading.Lock()


def get_memory() -> Memory:
    """Thread-safe lazy init of Memory singleton."""
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                os.makedirs("/data", exist_ok=True)
                _memory = Memory("/data/queen.db")
                logger.info("Memory initialized (actions.py)")
    return _memory


# ─── Goal Ingestion ──────────────────────────────────────────────────────────

def ingest_goal(goal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée un goal en DB et publie un event Redis.
    L'orchestrator (dans son container) écoute les events et lance le pipeline.
    """
    mem = get_memory()
    goal = Goal(
        title=goal_data.get("title", "Untitled"),
        description=goal_data.get("description", ""),
        constraints=validate_goal_constraints(goal_data.get("constraints", {})),
    )
    mem.create_goal(goal)
    logger.info(f"Goal ingested: {goal.id} — {goal.title}")

    # Notify orchestrator via Redis
    redis_bus.publish_event("goal_created", {
        "goal_id": goal.id,
        "title": goal.title,
    })
    redis_bus.publish_log("info", "dashboard", f"New goal: {goal.id} — {goal.title}")

    return {"goal_id": goal.id, "status": "pending"}


# ─── Goal Actions ────────────────────────────────────────────────────────────

def pause_goal(goal_id: str) -> Dict[str, Any]:
    mem = get_memory()
    mem.update_goal_status(goal_id, GoalStatus.PAUSED.value)
    redis_bus.publish_event("goal_paused", {"goal_id": goal_id})
    return {"status": "paused"}


def resume_goal(goal_id: str) -> Dict[str, Any]:
    mem = get_memory()
    mem.update_goal_status(goal_id, GoalStatus.RUNNING.value)
    redis_bus.publish_event("goal_resumed", {"goal_id": goal_id})
    return {"status": "running"}


# ─── Job Actions ─────────────────────────────────────────────────────────────

def retry_job(job_id: str) -> Dict[str, Any]:
    mem = get_memory()
    job = mem.get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    mem.update_job(job_id, status=JobStatus.QUEUED.value, started_at="", finished_at="")
    redis_bus.enqueue_job(job)
    return {"status": "requeued"}


# ─── Patch Actions ───────────────────────────────────────────────────────────

def approve_patch(patch_id: str, actor: str = "user") -> Dict[str, Any]:
    mem = get_memory()
    patch = mem.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}
    mem.update_patch(patch_id, status=PatchStatus.APPROVED.value, approved_by=actor)
    mem.audit("approve_patch", "patch", patch_id, actor=actor)
    redis_bus.publish_event("patch_approved", {"patch_id": patch_id})
    return {"status": "approved"}


def apply_patch(patch_id: str, actor: str = "user") -> Dict[str, Any]:
    from queen_core.patcher import apply_patch as do_apply

    mem = get_memory()
    patch = mem.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}

    result = do_apply(patch["diff_content"], f"/workspace/{patch['goal_id']}")

    if result.get("failed"):
        mem.update_patch(patch_id, status=PatchStatus.GATES_FAILED.value)
        return {"error": "Some files failed to apply", "details": result}

    now = datetime.utcnow().isoformat()
    mem.update_patch(patch_id, status=PatchStatus.APPLIED.value, applied_at=now)
    mem.update_run(patch["run_id"], status=RunStatus.APPLIED.value, finished_at=now)
    mem.update_goal_status(patch["goal_id"], GoalStatus.COMPLETED.value)
    mem.audit("apply_patch", "patch", patch_id, actor=actor, details=result)
    redis_bus.publish_event("patch_applied", {"patch_id": patch_id, "goal_id": patch["goal_id"]})
    return {"status": "applied", "details": result}


def reject_patch(patch_id: str, actor: str = "user", reason: str = "") -> Dict[str, Any]:
    mem = get_memory()
    patch = mem.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}
    mem.update_patch(patch_id, status=PatchStatus.REJECTED.value)
    mem.audit("reject_patch", "patch", patch_id, actor=actor, details={"reason": reason})
    redis_bus.publish_event("patch_rejected", {"patch_id": patch_id})
    return {"status": "rejected"}


def rollback_patch(patch_id: str, actor: str = "user") -> Dict[str, Any]:
    from queen_core.patcher import rollback

    mem = get_memory()
    patch = mem.get_patch(patch_id)
    if not patch:
        return {"error": "Patch not found"}

    backup_dir = "/workspace/.queen_backups"
    if os.path.exists(backup_dir):
        backups = sorted(os.listdir(backup_dir), reverse=True)
        if backups:
            result = rollback(
                os.path.join(backup_dir, backups[0]),
                f"/workspace/{patch['goal_id']}",
            )
            mem.update_patch(patch_id, status=PatchStatus.ROLLED_BACK.value)
            mem.update_run(patch["run_id"], status=RunStatus.ROLLED_BACK.value)
            mem.audit("rollback_patch", "patch", patch_id, actor=actor, details=result)
            return {"status": "rolled_back", "details": result}

    return {"error": "No backup found for rollback"}
