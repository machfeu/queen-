"""evolution_routes.py — Endpoints API for the evolution archive.

This is intentionally read-only in MVP (no remote 'promote' endpoint).
"""

import json

from fastapi import APIRouter, HTTPException

from queen_core.evolution.archive import EvolutionArchive


evolution_router = APIRouter(prefix="/api/evolution", tags=["Evolution"])


def _loads_list(s: str):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


@evolution_router.get("/variants")
def list_variants(limit: int = 200):
    a = EvolutionArchive()
    vs = a.list_variants(limit=limit)
    return [
        {
            "variant_id": v.variant_id,
            "parent_id": v.parent_id,
            "created_at": v.created_at,
            "fitness": v.fitness,
            "tests_ok": bool(v.tests_ok),
            "targets": _loads_list(v.targets),
            "tags": _loads_list(v.tags),
            "patch_path": v.patch_path,
            "snapshot_path": v.snapshot_path,
        }
        for v in vs
    ]


@evolution_router.get("/variants/{variant_id}")
def get_variant(variant_id: str):
    a = EvolutionArchive()
    v = a.get_variant(variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="variant not found")
    return {
        "variant_id": v.variant_id,
        "parent_id": v.parent_id,
        "created_at": v.created_at,
        "fitness": v.fitness,
        "tests_ok": bool(v.tests_ok),
        "targets": _loads_list(v.targets),
        "tags": _loads_list(v.tags),
        "metrics": v.metrics,
        "patch_path": v.patch_path,
        "snapshot_path": v.snapshot_path,
    }


@evolution_router.get("/lineage/{variant_id}")
def get_lineage(variant_id: str, max_depth: int = 50):
    a = EvolutionArchive()
    chain = a.lineage(variant_id, max_depth=max_depth)
    if not chain:
        raise HTTPException(status_code=404, detail="variant not found")
    return [
        {
            "variant_id": v.variant_id,
            "parent_id": v.parent_id,
            "created_at": v.created_at,
            "fitness": v.fitness,
            "tests_ok": bool(v.tests_ok),
        }
        for v in chain
    ]
