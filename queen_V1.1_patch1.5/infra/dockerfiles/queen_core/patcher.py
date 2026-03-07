"""
patcher.py — Génère des diffs et applique des patches de manière contrôlée.
Ne touche JAMAIS au noyau stable (queen_core).
Écrit uniquement dans /workspace/.
"""

import difflib
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional

from queen_core.policy import validate_file_path, check_code_safety

logger = logging.getLogger("queen.patcher")

WORKSPACE_BASE = os.getenv("WORKSPACE_BASE", "/workspace")
BACKUP_DIR = os.path.join(WORKSPACE_BASE, ".queen_backups")


def generate_diff(original_path: str, new_content: str, filename: str = "") -> str:
    """
    Generate a unified diff between original file and new content.
    If original doesn't exist, generates a 'new file' diff.
    """
    if not filename:
        filename = os.path.basename(original_path)

    try:
        if os.path.exists(original_path):
            with open(original_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()
        else:
            original_lines = []
    except Exception:
        original_lines = []

    new_lines = new_content.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=max(len(original_lines), len(new_lines), 3),
        lineterm="\n",
    )
    return "".join(diff)


def generate_patch_from_artifacts(artifacts: List[Dict[str, Any]],
                                  workspace_path: str = "") -> str:
    """
    Generate a combined patch from multiple artifacts.
    Each artifact: {"path": "relative/path.py", "content": "..."}
    """
    if not workspace_path:
        workspace_path = WORKSPACE_BASE

    diffs = []
    for art in artifacts:
        if art.get("rejected"):
            continue
        rel_path = (art.get("path", "") or "").lstrip("/\\")
        content = art.get("content", "")

        if not rel_path or not content:
            continue

        original_full = os.path.join(workspace_path, rel_path)
        diff = generate_diff(original_full, content, filename=rel_path)
        if diff:
            diffs.append(diff)

    return "\n".join(diffs)


def apply_patch(patch_content: str, workspace_path: str = "",
                dry_run: bool = False) -> Dict[str, Any]:
    """
    Apply a patch to the workspace.
    Returns: {"applied": [...], "failed": [...], "backup_dir": "..."}
    
    If dry_run=True, only validates without applying.
    """
    if not workspace_path:
        workspace_path = WORKSPACE_BASE

    result = {"applied": [], "failed": [], "backup_dir": "", "dry_run": dry_run}

    # Parse the unified diff to extract file changes
    changes = _parse_unified_diff(patch_content)
    if not changes:
        result["failed"].append({"error": "No parseable changes in patch"})
        return result

    # Create backup
    if not dry_run:
        backup_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, backup_id)
        os.makedirs(backup_path, exist_ok=True)
        result["backup_dir"] = backup_path

    for change in changes:
        target_path = change["path"]
        full_path = os.path.join(workspace_path, target_path)

        # Security checks
        ok, reason = validate_file_path(full_path)
        if not ok:
            result["failed"].append({"path": target_path, "reason": reason})
            continue

        # Code safety check
        if change.get("new_content"):
            safe, violations = check_code_safety(change["new_content"])
            if not safe:
                result["failed"].append({
                    "path": target_path,
                    "reason": f"Code safety violation: {'; '.join(violations)}",
                })
                continue

        if dry_run:
            result["applied"].append({"path": target_path, "action": "would_apply"})
            continue

        try:
            # Backup existing file
            if os.path.exists(full_path):
                backup_file = os.path.join(backup_path, target_path)
                os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                shutil.copy2(full_path, backup_file)

            # Write new content
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(change["new_content"])

            result["applied"].append({"path": target_path, "action": "applied"})
        except Exception as e:
            result["failed"].append({"path": target_path, "reason": str(e)})

    return result


def rollback(backup_dir: str, workspace_path: str = "") -> Dict[str, Any]:
    """Rollback workspace to a previous backup state."""
    if not workspace_path:
        workspace_path = WORKSPACE_BASE

    if not os.path.exists(backup_dir):
        return {"error": f"Backup dir not found: {backup_dir}"}

    restored = []
    for root, dirs, files in os.walk(backup_dir):
        for fname in files:
            src = os.path.join(root, fname)
            rel_path = os.path.relpath(src, backup_dir)
            dst = os.path.join(workspace_path, rel_path)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                restored.append(rel_path)
            except Exception as e:
                logger.error(f"Rollback failed for {rel_path}: {e}")

    return {"restored": restored, "backup_dir": backup_dir}


def _parse_unified_diff(diff_text: str) -> List[Dict[str, Any]]:
    """Parse a unified diff into list of {path, new_content}."""
    changes = []
    current_path = None
    current_new_lines = []
    current_old_lines = []

    for line in diff_text.split("\n"):
        if line.startswith("+++ b/"):
            if current_path and current_new_lines:
                changes.append({
                    "path": current_path,
                    "new_content": "".join(current_new_lines),
                })
            current_path = line[6:].strip()
            current_new_lines = []
            current_old_lines = []
        elif line.startswith("--- a/"):
            continue
        elif line.startswith("@@"):
            continue
        elif line.startswith("+") and not line.startswith("+++"):
            current_new_lines.append(line[1:] + "\n")
        elif line.startswith("-") and not line.startswith("---"):
            current_old_lines.append(line[1:] + "\n")
        elif not line.startswith("\\"):
            # Context line (unchanged)
            current_new_lines.append(line[1:] + "\n" if line.startswith(" ") else line + "\n")

    # Last file
    if current_path and current_new_lines:
        changes.append({
            "path": current_path,
            "new_content": "".join(current_new_lines),
        })

    return changes
