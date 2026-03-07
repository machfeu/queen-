"""
memory.py — Couche de persistance SQLite pour Queen V1.
Thread-safe via un lock. Toutes les opérations CRUD centralisées ici.
"""

import json
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any

from queen_core.models import (
    Goal, Run, Job, Patch, AuditEntry,
    init_db, dict_to_json, json_to_dict,
)


class Memory:
    """Single-writer SQLite memory backend."""

    def __init__(self, db_path: str = "/data/queen.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = init_db(db_path)

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, params).fetchone()

    def _fetchall(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    # ─── Goals ────────────────────────────────────────────────────────────

    def create_goal(self, goal: Goal) -> Goal:
        self._execute(
            "INSERT INTO goals (id, title, description, constraints, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (goal.id, goal.title, goal.description, dict_to_json(goal.constraints),
             goal.status, goal.created_at, goal.updated_at),
        )
        self.audit("create", "goal", goal.id, details={"title": goal.title})
        return goal

    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone("SELECT * FROM goals WHERE id = ?", (goal_id,))
        if not row:
            return None
        d = dict(row)
        d["constraints"] = json_to_dict(d["constraints"])
        return d

    def list_goals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status:
            rows = self._fetchall("SELECT * FROM goals WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            rows = self._fetchall("SELECT * FROM goals ORDER BY created_at DESC")
        results = []
        for row in rows:
            d = dict(row)
            d["constraints"] = json_to_dict(d["constraints"])
            results.append(d)
        return results

    def update_goal_status(self, goal_id: str, status: str):
        now = datetime.utcnow().isoformat()
        self._execute("UPDATE goals SET status = ?, updated_at = ? WHERE id = ?", (status, now, goal_id))
        self.audit("update_status", "goal", goal_id, details={"status": status})

    # ─── Runs ─────────────────────────────────────────────────────────────

    def create_run(self, run: Run) -> Run:
        self._execute(
            "INSERT INTO runs (id, goal_id, status, plan, score, score_justification, patch_id, created_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run.id, run.goal_id, run.status, dict_to_json(run.plan), run.score,
             run.score_justification, run.patch_id, run.created_at, run.finished_at),
        )
        self.audit("create", "run", run.id, details={"goal_id": run.goal_id})
        return run

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not row:
            return None
        d = dict(row)
        d["plan"] = json_to_dict(d["plan"])
        return d

    def list_runs(self, goal_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if goal_id:
            rows = self._fetchall("SELECT * FROM runs WHERE goal_id = ? ORDER BY created_at DESC", (goal_id,))
        else:
            rows = self._fetchall("SELECT * FROM runs ORDER BY created_at DESC")
        results = []
        for row in rows:
            d = dict(row)
            d["plan"] = json_to_dict(d["plan"])
            results.append(d)
        return results

    def update_run(self, run_id: str, **kwargs):
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in ("plan", "gate_results") and isinstance(v, (dict, list)):
                v = dict_to_json(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(run_id)
        self._execute(f"UPDATE runs SET {', '.join(sets)} WHERE id = ?", tuple(vals))

    # ─── Jobs ─────────────────────────────────────────────────────────────

    def create_job(self, job: Job) -> Job:
        self._execute(
            "INSERT INTO jobs (id, run_id, goal_id, job_type, payload, status, result, logs, "
            "worker_id, timeout_seconds, max_output_bytes, created_at, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job.id, job.run_id, job.goal_id, job.job_type, dict_to_json(job.payload),
             job.status, dict_to_json(job.result), job.logs, job.worker_id,
             job.timeout_seconds, job.max_output_bytes, job.created_at, job.started_at, job.finished_at),
        )
        return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            return None
        d = dict(row)
        d["payload"] = json_to_dict(d["payload"])
        d["result"] = json_to_dict(d["result"])
        return d

    def list_jobs(self, run_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conditions = []
        params = []
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._fetchall(f"SELECT * FROM jobs{where} ORDER BY created_at ASC", tuple(params))
        results = []
        for row in rows:
            d = dict(row)
            d["payload"] = json_to_dict(d["payload"])
            d["result"] = json_to_dict(d["result"])
            results.append(d)
        return results

    def update_job(self, job_id: str, **kwargs):
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in ("payload", "result") and isinstance(v, (dict, list)):
                v = dict_to_json(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(job_id)
        self._execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", tuple(vals))

    # ─── Patches ──────────────────────────────────────────────────────────

    def create_patch(self, patch: Patch) -> Patch:
        self._execute(
            "INSERT INTO patches (id, run_id, goal_id, diff_content, status, gate_results, "
            "applied_at, approved_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (patch.id, patch.run_id, patch.goal_id, patch.diff_content, patch.status,
             dict_to_json(patch.gate_results), patch.applied_at, patch.approved_by, patch.created_at),
        )
        self.audit("create", "patch", patch.id, details={"run_id": patch.run_id})
        return patch

    def get_patch(self, patch_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone("SELECT * FROM patches WHERE id = ?", (patch_id,))
        if not row:
            return None
        d = dict(row)
        d["gate_results"] = json_to_dict(d["gate_results"])
        return d

    def list_patches(self, goal_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if goal_id:
            rows = self._fetchall("SELECT * FROM patches WHERE goal_id = ? ORDER BY created_at DESC", (goal_id,))
        else:
            rows = self._fetchall("SELECT * FROM patches ORDER BY created_at DESC")
        results = []
        for row in rows:
            d = dict(row)
            d["gate_results"] = json_to_dict(d["gate_results"])
            results.append(d)
        return results

    def update_patch(self, patch_id: str, **kwargs):
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in ("gate_results",) and isinstance(v, (dict, list)):
                v = dict_to_json(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(patch_id)
        self._execute(f"UPDATE patches SET {', '.join(sets)} WHERE id = ?", tuple(vals))

    # ─── Audit ────────────────────────────────────────────────────────────

    def audit(self, action: str, entity_type: str, entity_id: str,
              actor: str = "system", details: Optional[Dict] = None):
        entry = AuditEntry(
            action=action, entity_type=entity_type, entity_id=entity_id,
            actor=actor, details=details or {},
        )
        self._execute(
            "INSERT INTO audit_log (id, timestamp, action, entity_type, entity_id, actor, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry.id, entry.timestamp, entry.action, entry.entity_type,
             entry.entity_id, entry.actor, dict_to_json(entry.details)),
        )

    def list_audit(self, entity_type: Optional[str] = None, entity_id: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        conditions = []
        params: list = []
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        rows = self._fetchall(
            f"SELECT * FROM audit_log{where} ORDER BY timestamp DESC LIMIT ?", tuple(params)
        )
        results = []
        for row in rows:
            d = dict(row)
            d["details"] = json_to_dict(d["details"])
            results.append(d)
        return results

    # ─── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Dashboard statistics."""
        goals_total = self._fetchone("SELECT COUNT(*) as c FROM goals")[0]
        goals_running = self._fetchone("SELECT COUNT(*) as c FROM goals WHERE status = 'running'")[0]
        runs_total = self._fetchone("SELECT COUNT(*) as c FROM runs")[0]
        jobs_total = self._fetchone("SELECT COUNT(*) as c FROM jobs")[0]
        jobs_running = self._fetchone("SELECT COUNT(*) as c FROM jobs WHERE status = 'running'")[0]
        patches_total = self._fetchone("SELECT COUNT(*) as c FROM patches")[0]
        patches_applied = self._fetchone("SELECT COUNT(*) as c FROM patches WHERE status = 'applied'")[0]
        return {
            "goals_total": goals_total,
            "goals_running": goals_running,
            "runs_total": runs_total,
            "jobs_total": jobs_total,
            "jobs_running": jobs_running,
            "patches_total": patches_total,
            "patches_applied": patches_applied,
        }
