"""
models.py — Modèles de données Queen V1
Dataclasses pures + fonctions SQLite.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


# ─── Enums ────────────────────────────────────────────────────────────────────

class GoalStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class JobType(str, Enum):
    RESEARCH = "research"
    CODEGEN = "codegen"
    TEST = "test"
    EVAL = "eval"
    PATCH = "patch"

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class RunStatus(str, Enum):
    RUNNING = "running"
    GATES_PENDING = "gates_pending"
    GATES_PASSED = "gates_passed"
    GATES_FAILED = "gates_failed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

class PatchStatus(str, Enum):
    GENERATED = "generated"
    GATES_RUNNING = "gates_running"
    GATES_PASSED = "gates_passed"
    GATES_FAILED = "gates_failed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class Goal:
    id: str = field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)
    status: str = GoalStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class Job:
    id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    goal_id: str = ""
    job_type: str = JobType.RESEARCH.value
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = JobStatus.QUEUED.value
    result: Dict[str, Any] = field(default_factory=dict)
    logs: str = ""
    worker_id: str = ""
    timeout_seconds: int = 300
    max_output_bytes: int = 10_000_000  # 10 MB
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: str = ""
    finished_at: str = ""

@dataclass
class Run:
    id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    goal_id: str = ""
    status: str = RunStatus.RUNNING.value
    plan: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0
    score_justification: str = ""
    patch_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: str = ""

@dataclass
class Patch:
    id: str = field(default_factory=lambda: f"patch_{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    goal_id: str = ""
    diff_content: str = ""
    status: str = PatchStatus.GENERATED.value
    gate_results: Dict[str, Any] = field(default_factory=dict)
    applied_at: str = ""
    approved_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class AuditEntry:
    id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = ""
    entity_type: str = ""
    entity_id: str = ""
    actor: str = "system"
    details: Dict[str, Any] = field(default_factory=dict)


# ─── SQLite Schema & Helpers ──────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    constraints TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    plan TEXT DEFAULT '[]',
    score REAL DEFAULT 0.0,
    score_justification TEXT DEFAULT '',
    patch_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    finished_at TEXT DEFAULT '',
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    status TEXT DEFAULT 'queued',
    result TEXT DEFAULT '{}',
    logs TEXT DEFAULT '',
    worker_id TEXT DEFAULT '',
    timeout_seconds INTEGER DEFAULT 300,
    max_output_bytes INTEGER DEFAULT 10000000,
    created_at TEXT NOT NULL,
    started_at TEXT DEFAULT '',
    finished_at TEXT DEFAULT '',
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS patches (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    diff_content TEXT DEFAULT '',
    status TEXT DEFAULT 'generated',
    gate_results TEXT DEFAULT '{}',
    applied_at TEXT DEFAULT '',
    approved_by TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    actor TEXT DEFAULT 'system',
    details TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_jobs_run_id ON jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_runs_goal_id ON runs(goal_id);
CREATE INDEX IF NOT EXISTS idx_patches_run_id ON patches(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
"""


def init_db(db_path: str = "/data/queen.db") -> sqlite3.Connection:
    """Initialize database with schema."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def dict_to_json(d: Any) -> str:
    if isinstance(d, (dict, list)):
        return json.dumps(d, ensure_ascii=False)
    return str(d)


def json_to_dict(s: str) -> Any:
    try:
        return json.loads(s) if s else {}
    except (json.JSONDecodeError, TypeError):
        return {}
