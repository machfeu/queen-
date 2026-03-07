"""mutator.py — Proposes code edits for a candidate variant.

MVP strategy:
- read target files from parent snapshot
- ask the LLM to output full file contents (artifacts) for a small subset
- rely on policy.check_code_safety() during patch application
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from queen_core.llm_client import generate_json

logger = logging.getLogger("queen.evolution")


def _read_file(path: str, max_chars: int = 12000) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n# [TRUNCATED]"
        return text
    except Exception as e:
        return f"# [ERROR reading {path}: {e}]"


def propose_artifacts(
    parent_src: str,
    targets: List[str],
    instruction: str,
    run_id: str,
    max_files: int = 2,
) -> List[Dict[str, Any]]:
    targets = [t.strip().lstrip("/\\") for t in targets if t and isinstance(t, str)]
    targets = targets[: max_files]
    if not targets:
        return []

    file_blocks = []
    for rel in targets:
        abs_path = os.path.join(parent_src, rel)
        file_blocks.append(
            {
                "path": rel,
                "content": _read_file(abs_path),
            }
        )

    prompt = {
        "task": "Propose improved file contents for the target files.",
        "constraints": [
            "Return JSON only.",
            "Do not add new dependencies.",
            "Keep public function signatures stable unless strictly necessary.",
            "Do not use os.system, subprocess.call/Popen, eval, exec or other dangerous patterns.",
            "Prefer small, safe changes.",
            "Return FULL file content for each changed file.",
        ],
        "instruction": instruction,
        "files": file_blocks,
        "output_schema": {
            "artifacts": [
                {
                    "path": "relative/path.py",
                    "content": "FULL FILE CONTENT",
                    "reason": "short reason",
                }
            ],
            "notes": "optional",
        },
    }

    system = (
        "You are a senior software engineer improving an orchestrator/agent system. "
        "You must be conservative: minimal changes, high reliability. "
        "Output MUST be valid JSON matching output_schema."
    )
    data = generate_json(
        prompt=str(prompt),
        system=system,
        temperature=0.2,
        max_tokens=4096,
        run_id=run_id,
    )

    arts = data.get("artifacts", []) if isinstance(data, dict) else []
    valid: List[Dict[str, Any]] = []
    for a in arts:
        if not isinstance(a, dict):
            continue
        p = (a.get("path") or "").strip().lstrip("/\\")
        c = a.get("content")
        if not p or not isinstance(c, str) or not c.strip():
            continue
        valid.append({"path": p, "content": c, "reason": a.get("reason", "")})

    return valid
