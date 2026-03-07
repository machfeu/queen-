"""smoke.py — Candidate validation for evolution.

We run fast checks only (seconds):
- python compilation for changed files
- import critical modules under candidate PYTHONPATH

This is not a full integration test. It is designed to be cheap enough to run
many times during evolution.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Dict, List

logger = logging.getLogger("queen.evolution")


def _run(cmd: List[str], env: Dict[str, str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        text=True,
    )


def run_smoke(candidate_src: str, changed_paths: List[str]) -> Dict[str, object]:
    start = time.time()
    env = dict(os.environ)
    env["PYTHONPATH"] = candidate_src + (":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")

    # Compile changed python files
    py_files = [p for p in changed_paths if p.endswith(".py")]
    compile_ok = True
    compile_output = ""
    if py_files:
        proc = _run(["python", "-m", "py_compile", *py_files], env=env, timeout=60)
        compile_ok = proc.returncode == 0
        compile_output = proc.stdout[-4000:]

    # Import critical modules
    import_ok = True
    imp = _run(
        [
            "python",
            "-c",
            "import queen_core; import queen_core.orchestrator; import queen_core.redis_bus; import workers.worker_unified",
        ],
        env=env,
        timeout=60,
    )
    import_ok = imp.returncode == 0
    import_output = imp.stdout[-4000:]

    runtime = time.time() - start
    return {
        "compile_ok": compile_ok,
        "compile_output": compile_output,
        "smoke_ok": bool(compile_ok and import_ok),
        "import_ok": import_ok,
        "import_output": import_output,
        "runtime_seconds": round(runtime, 3),
    }
