"""
policy.py — Règles de sécurité, budgets et allowlists pour Queen V1.
Safe-by-default: tout ce qui n'est pas explicitement autorisé est interdit.
"""

import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger("queen.policy")

# ─── Configuration par défaut (overridable via env) ──────────────────────────

DEFAULT_JOB_TIMEOUT = int(os.getenv("POLICY_JOB_TIMEOUT", "300"))       # 5 min
MAX_JOB_TIMEOUT = int(os.getenv("POLICY_MAX_JOB_TIMEOUT", "1800"))      # 30 min
MAX_OUTPUT_BYTES = int(os.getenv("POLICY_MAX_OUTPUT_BYTES", "10000000")) # 10 MB
MAX_JOBS_PER_RUN = int(os.getenv("POLICY_MAX_JOBS_PER_RUN", "20"))
MAX_CONCURRENT_JOBS = int(os.getenv("POLICY_MAX_CONCURRENT_JOBS", "5"))
MAX_RUNS_PER_GOAL = int(os.getenv("POLICY_MAX_RUNS_PER_GOAL", "10"))
WORKSPACE_BASE = "/workspace"

# Allowed file extensions for codegen output
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".html", ".css", ".sh", ".sql",
    ".dockerfile", ".conf", ".cfg", ".ini", ".env.example",
}

# Blocked patterns in generated code
BLOCKED_PATTERNS = [
    "os.system(",
    "subprocess.call(",
    "subprocess.Popen(",
    "eval(",
    "exec(",
    "__import__(",
    "shutil.rmtree('/'",
    "rm -rf /",
    "chmod 777",
    "curl | bash",
    "wget | sh",
    "nc -l",  # netcat listener
    "bind_shell",
    "reverse_shell",
]

# Blocked pip packages
BLOCKED_PACKAGES = {
    "paramiko",  # SSH — pas dans les workers
    "fabric",
    "ansible",
    "nmap",
    "scapy",
}

# Risk levels
RISK_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def validate_goal_constraints(constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate goal constraints. Returns cleaned constraints.

    Patch 1.2:
    - ajoute le champ optionnel 'role'
    - si un rôle existe (roles/), applique ses default_constraints
      uniquement pour les clés non fournies par l'utilisateur.
    """
    constraints = constraints or {}

    # Role (optionnel)
    role = constraints.get("role", "")
    role = role.strip() if isinstance(role, str) else ""

    # Defaults issus du rôle (si disponible)
    role_defaults: Dict[str, Any] = {}
    if role:
        try:
            from queen_core.role_registry import get_role_registry
            reg = get_role_registry()
            r = reg.get(role)
            if r and isinstance(getattr(r, "default_constraints", None), dict):
                role_defaults = r.default_constraints
        except Exception as e:
            logger.warning(f"Could not load role defaults for '{role}': {e}")

    def _get(key: str, fallback):
        # l'utilisateur a priorité ; sinon on prend le défaut du rôle
        if key in constraints:
            return constraints.get(key, fallback)
        if key in role_defaults:
            return role_defaults.get(key, fallback)
        return fallback

    cleaned: Dict[str, Any] = {}

    cleaned["timeout"] = min(
        _get("timeout", DEFAULT_JOB_TIMEOUT),
        MAX_JOB_TIMEOUT
    )
    cleaned["max_output_bytes"] = min(
        _get("max_output_bytes", MAX_OUTPUT_BYTES),
        MAX_OUTPUT_BYTES
    )

    cleaned["risk_level"] = _get("risk_level", "medium")
    if cleaned["risk_level"] not in RISK_LEVELS:
        cleaned["risk_level"] = "medium"

    cleaned["repo_target"] = _get("repo_target", "default")
    cleaned["success_criteria"] = _get("success_criteria", "")
    cleaned["require_manual_approval"] = bool(_get("require_manual_approval", True))

    # Conserver le role même si inconnu : on pourra le diagnostiquer côté UI/logs
    cleaned["role"] = role

    return cleaned


def validate_job(job_type: str, payload: Dict[str, Any]) -> tuple[bool, str]:
    """Validate a job before queuing. Returns (ok, reason)."""
    if job_type not in ("research", "codegen", "test", "eval", "patch"):
        return False, f"Unknown job type: {job_type}"

    timeout = payload.get("timeout", DEFAULT_JOB_TIMEOUT)
    if timeout > MAX_JOB_TIMEOUT:
        return False, f"Timeout {timeout}s exceeds max {MAX_JOB_TIMEOUT}s"

    return True, "ok"


def check_code_safety(code: str) -> tuple[bool, List[str]]:
    """
    Basic static check for dangerous patterns in generated code.
    Returns (safe, list_of_violations).
    """
    violations = []
    for pattern in BLOCKED_PATTERNS:
        if pattern in code:
            violations.append(f"Blocked pattern found: {pattern}")

    for pkg in BLOCKED_PACKAGES:
        if f"import {pkg}" in code or f"from {pkg}" in code:
            violations.append(f"Blocked package: {pkg}")

    return len(violations) == 0, violations


def validate_file_path(path: str) -> tuple[bool, str]:
    """Ensure file path is within workspace."""
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(WORKSPACE_BASE):
        return False, f"Path {path} is outside workspace {WORKSPACE_BASE}"

    ext = os.path.splitext(path)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        return False, f"Extension {ext} not in allowlist"

    # Block path traversal
    if ".." in path:
        return False, "Path traversal (..) not allowed"

    return True, "ok"


def get_job_budget(risk_level: str = "medium") -> Dict[str, int]:
    """Return resource budgets based on risk level."""
    budgets = {
        "low": {"timeout": 600, "max_output_bytes": 50_000_000, "max_jobs": 20},
        "medium": {"timeout": 300, "max_output_bytes": 10_000_000, "max_jobs": 10},
        "high": {"timeout": 120, "max_output_bytes": 5_000_000, "max_jobs": 5},
        "critical": {"timeout": 60, "max_output_bytes": 1_000_000, "max_jobs": 3},
    }
    return budgets.get(risk_level, budgets["medium"])
