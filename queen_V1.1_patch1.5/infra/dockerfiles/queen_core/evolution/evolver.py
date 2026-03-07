"""evolver.py — DGM-like evolution loop (MVP).

This runs *outside* the main orchestrator loop.

Workflow per iteration:
1) select a parent variant (or root)
2) create a candidate snapshot under /workspace/.queen_evolution/
3) ask LLM to propose artifacts (full-file contents) for a small allowlisted set
4) apply patch to candidate snapshot
5) run smoke checks
6) compute fitness and archive (patch + snapshot + metrics)

Notes:
- The candidate is NOT automatically promoted into the live system.
- Promotion is a manual step: apply the archived patch to your repo/workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from queen_core.patcher import generate_patch_from_artifacts, apply_patch

from .archive import EvolutionArchive
from .fitness import compute_fitness
from .mutator import propose_artifacts
from .selector import select_parent
from .smoke import run_smoke

logger = logging.getLogger("queen.evolution")


DEFAULT_ALLOWLIST = [
    "queen_core/orchestrator.py",
    "queen_core/redis_bus.py",
    "queen_core/policy.py",
    "queen_core/patcher.py",
    "queen_core/notifier.py",
    "queen_core/self_heal.py",
    "workers/worker_unified.py",
]


def _hash_tree(base_dir: str, rel_paths: List[str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(set(rel_paths)):
        p = os.path.join(base_dir, rel)
        if not os.path.exists(p):
            continue
        try:
            with open(p, "rb") as f:
                h.update(rel.encode("utf-8"))
                h.update(b"\0")
                h.update(f.read())
                h.update(b"\0")
        except Exception:
            continue
    return h.hexdigest()


def _copy_snapshot(src_root: str, dst_root: str, include_dirs: Optional[List[str]] = None) -> None:
    os.makedirs(dst_root, exist_ok=True)
    include_dirs = include_dirs or ["queen_core", "workers", "dashboard/backend"]
    for d in include_dirs:
        s = os.path.join(src_root, d)
        if not os.path.exists(s):
            continue
        t = os.path.join(dst_root, d)
        if os.path.exists(t):
            shutil.rmtree(t)
        shutil.copytree(s, t)


def _zip_dir(src_dir: str, out_zip: str) -> None:
    os.makedirs(os.path.dirname(out_zip), exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src_dir):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, src_dir)
                z.write(p, rel)


def run_evolution(
    iterations: int = 5,
    instruction: str = "Improve reliability and bug-resilience without changing external behavior.",
    targets: Optional[List[str]] = None,
    allowlist: Optional[List[str]] = None,
    max_files: int = 2,
    exploration: float = 0.15,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run the evolution loop and return summary."""

    archive = EvolutionArchive()
    allowlist = allowlist or DEFAULT_ALLOWLIST
    targets = targets or allowlist

    # Parent snapshot source is the running container /app (mounted code)
    src_root = os.getenv("EVOLUTION_SOURCE_ROOT", "/app")
    workspace_base = os.getenv("WORKSPACE_BASE", "/workspace")
    evo_root = os.path.join(workspace_base, ".queen_evolution")
    candidates_root = os.path.join(evo_root, "candidates")
    os.makedirs(candidates_root, exist_ok=True)

    # Create a stable root variant if archive is empty
    variants = archive.list_variants(limit=1)
    if not variants:
        code_hash = _hash_tree(src_root, allowlist)[:12]
        root_id = f"root-{code_hash}"
        # Root record has neutral fitness but tests_ok=1 (it is the baseline)
        patch_path = archive.patch_file_path(root_id)
        snapshot_path = archive.snapshot_file_path(root_id)
        if not os.path.exists(snapshot_path):
            tmp = os.path.join(candidates_root, root_id, "src")
            _copy_snapshot(src_root, tmp)
            _zip_dir(tmp, snapshot_path)
        if not os.path.exists(patch_path):
            with open(patch_path, "w", encoding="utf-8") as f:
                f.write("# root variant (no patch)\n")
        archive.add_variant(
            variant_id=root_id,
            parent_id=None,
            fitness=0.50,
            tests_ok=True,
            targets=[],
            tags=["root"],
            metrics={"smoke_ok": True, "compile_ok": True, "root": True},
            patch_path=patch_path,
            snapshot_path=snapshot_path,
        )

    created: List[str] = []
    last_parent: Optional[str] = None
    for i in range(int(iterations)):
        parent = select_parent(archive, exploration=exploration)
        if not parent:
            break
        last_parent = parent.variant_id

        variant_id = archive.new_variant_id(prefix="cand")
        created.append(variant_id)

        candidate_src = os.path.join(candidates_root, variant_id, "src")
        _copy_snapshot(src_root, candidate_src)

        run_id = f"evo-{variant_id}"
        # Limit mutation to allowlisted paths and requested targets
        chosen_targets = [t for t in (targets or []) if t in allowlist]
        if not chosen_targets:
            chosen_targets = allowlist[:]

        artifacts = propose_artifacts(
            parent_src=candidate_src,
            targets=chosen_targets,
            instruction=instruction,
            run_id=run_id,
            max_files=max_files,
        )

        patch_text = generate_patch_from_artifacts(artifacts, workspace_path=candidate_src)
        patch_path = archive.patch_file_path(variant_id)
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(patch_text or "")

        applied = {"applied": [], "failed": []}
        changed_paths: List[str] = []
        if patch_text.strip():
            applied = apply_patch(patch_text, workspace_path=candidate_src, dry_run=dry_run)
            changed_paths = [os.path.join(candidate_src, x.get("path", "")) for x in applied.get("applied", [])]

        # Smoke checks
        smoke_metrics = run_smoke(candidate_src=candidate_src, changed_paths=changed_paths)
        metrics: Dict[str, Any] = {
            "iteration": i,
            "parent_id": parent.variant_id,
            "smoke_ok": smoke_metrics.get("smoke_ok"),
            "compile_ok": smoke_metrics.get("compile_ok"),
            "import_ok": smoke_metrics.get("import_ok"),
            "runtime_seconds": smoke_metrics.get("runtime_seconds"),
            "applied": applied.get("applied", []),
            "failed": applied.get("failed", []),
            "notes": "dry_run" if dry_run else "",
        }

        fitness = compute_fitness(metrics)

        snapshot_path = archive.snapshot_file_path(variant_id)
        _zip_dir(candidate_src, snapshot_path)

        archive.add_variant(
            variant_id=variant_id,
            parent_id=parent.variant_id,
            fitness=fitness,
            tests_ok=bool(metrics.get("smoke_ok")),
            targets=chosen_targets[:max_files],
            tags=["candidate"],
            metrics=metrics,
            patch_path=patch_path,
            snapshot_path=snapshot_path,
        )

        logger.info(
            f"Evolution candidate archived: {variant_id} parent={parent.variant_id} "
            f"fitness={fitness:.3f} smoke_ok={metrics.get('smoke_ok')}"
        )

    return {"created": created, "last_parent": last_parent}


def _parse_list_arg(v: str) -> List[str]:
    if not v:
        return []
    # Accept JSON array or comma-separated
    v = v.strip()
    if v.startswith("["):
        try:
            data = json.loads(v)
            return [str(x) for x in data]
        except Exception:
            return []
    return [x.strip() for x in v.split(",") if x.strip()]


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    ap = argparse.ArgumentParser(description="Queen evolution loop (DGM-like MVP)")
    ap.add_argument("--iterations", type=int, default=int(os.getenv("EVOLUTION_ITERS", "5")))
    ap.add_argument("--max-files", type=int, default=int(os.getenv("EVOLUTION_MAX_FILES", "2")))
    ap.add_argument("--exploration", type=float, default=float(os.getenv("EVOLUTION_EXPLORATION", "0.15")))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--instruction", type=str, default=os.getenv(
        "EVOLUTION_INSTRUCTION",
        "Improve reliability and bug-resilience without changing external behavior.",
    ))
    ap.add_argument("--allowlist", type=str, default=os.getenv("EVOLUTION_ALLOWLIST", ""))
    ap.add_argument("--targets", type=str, default=os.getenv("EVOLUTION_TARGETS", ""))

    args = ap.parse_args()
    allowlist = _parse_list_arg(args.allowlist) or DEFAULT_ALLOWLIST
    targets = _parse_list_arg(args.targets) or None

    summary = run_evolution(
        iterations=args.iterations,
        instruction=args.instruction,
        targets=targets,
        allowlist=allowlist,
        max_files=args.max_files,
        exploration=args.exploration,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
