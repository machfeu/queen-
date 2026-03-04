"""
api.py — Dashboard API pour Queen V1.
FastAPI backend: REST API + WebSocket events + static frontend serving.
Port unique: 8080.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, "/app")

from queen_core.models import Goal, GoalStatus
from queen_core.memory import Memory
from queen_core.policy import validate_goal_constraints
from queen_core import redis_bus
from queen_core.llm_client import health_check as llm_health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("queen.dashboard")

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Queen V1 Dashboard",
    version="1.0.0",
    description="API de gestion et monitoring pour le système Queen V1.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared state
# ─────────────────────────────────────────────────────────────────────────────

memory: Optional[Memory] = None


@app.on_event("startup")
def startup():
    global memory
    from queen_core.actions import get_memory
    memory = get_memory()
    logger.info("📊 Dashboard API ready on :8080")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic request/response models
# ─────────────────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field("", max_length=5000)
    constraints: Dict[str, Any] = Field(default_factory=dict)

class PatchAction(BaseModel):
    actor: str = "user"
    reason: str = ""

class RetryRequest(BaseModel):
    actor: str = "user"


# ═════════════════════════════════════════════════════════════════════════════
#  GOALS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/goals", tags=["Goals"])
def list_goals(status: Optional[str] = None):
    """Liste tous les objectifs, filtrable par statut."""
    return memory.list_goals(status=status)


@app.get("/api/goals/{goal_id}", tags=["Goals"])
def get_goal(goal_id: str):
    """Détail d'un objectif."""
    goal = memory.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.post("/api/goals", tags=["Goals"], status_code=201)
def create_goal(data: GoalCreate):
    """
    Crée un nouvel objectif et déclenche le planning.
    Le pipeline complet s'exécute en arrière-plan :
    planning → jobs → scoring → patch → gates.
    """
    from queen_core.actions import ingest_goal
    result = ingest_goal(data.dict())
    return result


@app.post("/api/goals/{goal_id}/pause", tags=["Goals"])
def pause_goal(goal_id: str):
    """Met un objectif en pause."""
    goal = memory.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    from queen_core.actions import pause_goal as do_pause
    return do_pause(goal_id)


@app.post("/api/goals/{goal_id}/resume", tags=["Goals"])
def resume_goal(goal_id: str):
    """Reprend un objectif en pause."""
    goal = memory.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    from queen_core.actions import resume_goal as do_resume
    return do_resume(goal_id)


# ═════════════════════════════════════════════════════════════════════════════
#  RUNS (Experiments)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/runs", tags=["Runs"])
def list_runs(goal_id: Optional[str] = None):
    """Liste les runs, filtrable par goal_id."""
    return memory.list_runs(goal_id=goal_id)


@app.get("/api/runs/{run_id}", tags=["Runs"])
def get_run(run_id: str):
    """Détail d'un run avec son plan et son score."""
    run = memory.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/runs/{run_id}/timeline", tags=["Runs"])
def get_run_timeline(run_id: str):
    """
    Vue timeline d'un run : liste ordonnée des jobs
    avec statuts, timings et résumés.
    """
    run = memory.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    jobs = memory.list_jobs(run_id=run_id)
    timeline = []
    for j in jobs:
        timeline.append({
            "job_id": j["id"],
            "step": j["payload"].get("step", 0) if isinstance(j.get("payload"), dict) else 0,
            "job_type": j["job_type"],
            "title": j["payload"].get("title", "") if isinstance(j.get("payload"), dict) else "",
            "status": j["status"],
            "created_at": j["created_at"],
            "started_at": j.get("started_at", ""),
            "finished_at": j.get("finished_at", ""),
            "worker_id": j.get("worker_id", ""),
        })
    timeline.sort(key=lambda x: x["step"])

    return {
        "run_id": run_id,
        "goal_id": run["goal_id"],
        "run_status": run["status"],
        "score": run.get("score", 0),
        "patch_id": run.get("patch_id", ""),
        "timeline": timeline,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  JOBS (Workers tasks)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/jobs", tags=["Jobs"])
def list_jobs(run_id: Optional[str] = None, status: Optional[str] = None):
    """Liste les jobs, filtrable par run_id et/ou statut."""
    return memory.list_jobs(run_id=run_id, status=status)


@app.get("/api/jobs/{job_id}", tags=["Jobs"])
def get_job(job_id: str):
    """Détail d'un job avec payload, résultat et logs."""
    job = memory.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/retry", tags=["Jobs"])
def retry_job(job_id: str):
    """Re-met un job échoué dans la queue."""
    job = memory.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("failed", "timeout", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry job with status '{job['status']}'. Must be failed/timeout/cancelled.",
        )
    from queen_core.actions import retry_job as do_retry
    return do_retry(job_id)


@app.post("/api/jobs/{job_id}/cancel", tags=["Jobs"])
def cancel_job(job_id: str):
    """Annule un job en attente ou en cours."""
    job = memory.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("queued", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status '{job['status']}'.",
        )
    memory.update_job(job_id, status="cancelled", finished_at=datetime.utcnow().isoformat())
    memory.audit("cancel_job", "job", job_id, actor="user")
    return {"status": "cancelled"}


# ═════════════════════════════════════════════════════════════════════════════
#  PATCHES (Artefacts & Diffs)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/patches", tags=["Patches"])
def list_patches(goal_id: Optional[str] = None):
    """Liste les patches, filtrable par goal_id."""
    return memory.list_patches(goal_id=goal_id)


@app.get("/api/patches/{patch_id}", tags=["Patches"])
def get_patch(patch_id: str):
    """Détail d'un patch : diff, gate results, statut."""
    patch = memory.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    return patch


@app.get("/api/patches/{patch_id}/diff", tags=["Patches"])
def get_patch_diff(patch_id: str):
    """Retourne uniquement le contenu diff du patch (texte brut)."""
    patch = memory.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    return {"patch_id": patch_id, "diff": patch.get("diff_content", "")}


@app.post("/api/patches/{patch_id}/approve", tags=["Patches"])
def approve_patch(patch_id: str, action: PatchAction = PatchAction()):
    """
    Approuve un patch dont les gates sont passées.
    Pré-requis: status == gates_passed.
    """
    patch = memory.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    if patch["status"] != "gates_passed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve patch with status '{patch['status']}'. Must be 'gates_passed'.",
        )
    from queen_core.actions import approve_patch as do_approve
    return do_approve(patch_id, actor=action.actor)


@app.post("/api/patches/{patch_id}/apply", tags=["Patches"])
def apply_patch(patch_id: str, action: PatchAction = PatchAction()):
    """
    Applique un patch approuvé dans le workspace.
    Pré-requis: status == approved.
    Crée un backup automatique avant application.
    """
    patch = memory.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    if patch["status"] != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot apply patch with status '{patch['status']}'. Must be 'approved'.",
        )
    from queen_core.actions import apply_patch as do_apply
    return do_apply(patch_id, actor=action.actor)


@app.post("/api/patches/{patch_id}/reject", tags=["Patches"])
def reject_patch(patch_id: str, action: PatchAction = PatchAction()):
    """Rejette un patch avec une raison optionnelle."""
    patch = memory.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    from queen_core.actions import reject_patch as do_reject
    return do_reject(patch_id, actor=action.actor, reason=action.reason)


@app.post("/api/patches/{patch_id}/rollback", tags=["Patches"])
def rollback_patch(patch_id: str, action: PatchAction = PatchAction()):
    """
    Annule l'application d'un patch (rollback depuis backup).
    Pré-requis: status == applied.
    """
    patch = memory.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    if patch["status"] != "applied":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot rollback patch with status '{patch['status']}'. Must be 'applied'.",
        )
    from queen_core.actions import rollback_patch as do_rollback
    return do_rollback(patch_id, actor=action.actor)


# ═════════════════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/audit", tags=["Audit"])
def list_audit(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
):
    """Journal d'audit complet. Filtrable par type et ID d'entité."""
    return memory.list_audit(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=min(limit, 500),
    )


# ═════════════════════════════════════════════════════════════════════════════
#  LOGS (Redis stream)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/logs", tags=["Logs"])
def get_logs(count: int = 100):
    """Dernières entrées de log depuis Redis."""
    return redis_bus.get_recent_logs(count=min(count, 500))


# ═════════════════════════════════════════════════════════════════════════════
#  STATS & HEALTH & METRICS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/stats", tags=["Monitoring"])
def get_stats():
    """Statistiques globales du système."""
    return memory.get_stats()


@app.get("/api/health", tags=["Monitoring"])
def health():
    """Vérification de santé de tous les sous-systèmes."""
    redis_status = redis_bus.health_check()
    llm_status = llm_health()
    db_ok = True
    try:
        memory.get_stats()
    except Exception:
        db_ok = False

    return {
        "status": "ok" if (redis_status.get("status") == "ok" and db_ok) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": {"status": "ok" if db_ok else "error"},
            "redis": redis_status,
            "llm": llm_status,
        },
    }


@app.get("/api/metrics", tags=["Monitoring"])
def get_metrics():
    """
    Métriques système : CPU, RAM, disque, GPU (si nvidia-smi disponible).
    """
    metrics: Dict[str, Any] = {}

    # Disk
    try:
        disk = shutil.disk_usage("/data")
        metrics["disk"] = {
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "percent_used": round(disk.used / disk.total * 100, 1),
        }
    except Exception:
        metrics["disk"] = None

    # Memory
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":")
                if key in ("MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached"):
                    meminfo[key] = int(parts[1])  # kB
        total_mb = meminfo.get("MemTotal", 0) // 1024
        avail_mb = meminfo.get("MemAvailable", 0) // 1024
        metrics["memory"] = {
            "total_mb": total_mb,
            "available_mb": avail_mb,
            "used_mb": total_mb - avail_mb,
            "percent_used": round((total_mb - avail_mb) / total_mb * 100, 1) if total_mb else 0,
        }
    except Exception:
        metrics["memory"] = None

    # CPU load
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        metrics["cpu"] = {
            "load_1m": float(parts[0]),
            "load_5m": float(parts[1]),
            "load_15m": float(parts[2]),
        }
    except Exception:
        metrics["cpu"] = None

    # GPU via nvidia-smi
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 5:
                metrics["gpu"] = {
                    "name": parts[0],
                    "memory_used_mb": int(parts[1]),
                    "memory_total_mb": int(parts[2]),
                    "utilization_percent": int(parts[3]),
                    "temperature_c": int(parts[4]),
                }
    except Exception:
        metrics["gpu"] = None

    return metrics


# ═════════════════════════════════════════════════════════════════════════════
#  SETTINGS (read-only view of current config)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/settings", tags=["Settings"])
def get_settings():
    """Configuration actuelle (lecture seule, issue des variables d'env)."""
    return {
        "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        "ollama_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "policy_job_timeout": int(os.getenv("POLICY_JOB_TIMEOUT", "300")),
        "policy_max_job_timeout": int(os.getenv("POLICY_MAX_JOB_TIMEOUT", "1800")),
        "policy_max_output_bytes": int(os.getenv("POLICY_MAX_OUTPUT_BYTES", "10000000")),
        "policy_max_jobs_per_run": int(os.getenv("POLICY_MAX_JOBS_PER_RUN", "20")),
        "policy_max_concurrent_jobs": int(os.getenv("POLICY_MAX_CONCURRENT_JOBS", "5")),
        "require_manual_approval": True,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  WORKSPACE (browse workspace files)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/workspace", tags=["Workspace"])
def list_workspace(path: str = ""):
    """
    Parcourir le contenu du workspace.
    Retourne fichiers et dossiers à la racine ou dans un sous-dossier.
    """
    base = "/workspace"
    target = os.path.normpath(os.path.join(base, path))

    # Sécurité : ne pas sortir du workspace
    if not target.startswith(base):
        raise HTTPException(status_code=403, detail="Path traversal denied")

    if not os.path.exists(target):
        return {"path": path, "entries": []}

    if os.path.isfile(target):
        # Retourne le contenu du fichier (limité à 100 KB)
        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read(102400)
            return {
                "path": path,
                "type": "file",
                "size": os.path.getsize(target),
                "content": content,
            }
        except Exception:
            return {"path": path, "type": "file", "size": os.path.getsize(target), "content": "[binary]"}

    entries = []
    try:
        for name in sorted(os.listdir(target)):
            full = os.path.join(target, name)
            entries.append({
                "name": name,
                "type": "dir" if os.path.isdir(full) else "file",
                "size": os.path.getsize(full) if os.path.isfile(full) else 0,
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"path": path, "type": "dir", "entries": entries}


# ═════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET — Real-time events
# ═════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket pour le streaming temps réel des événements et logs.
    Le frontend se connecte ici pour les mises à jour live.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    import redis as redis_lib
    r = redis_lib.from_url(redis_bus.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(redis_bus.CHANNEL_EVENTS, redis_bus.CHANNEL_LOGS)

    try:
        while True:
            message = pubsub.get_message(timeout=0.3)
            if message and message["type"] == "message":
                await websocket.send_text(message["data"])
            # Heartbeat pour détecter les déconnexions
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        try:
            pubsub.unsubscribe()
            pubsub.close()
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
#  FRONTEND SERVING (fallback si pas de build React)
# ═════════════════════════════════════════════════════════════════════════════

FRONTEND_DIST = "/app/dashboard/frontend/dist"


# Mount static files if the built frontend exists
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_root():
    """Sert le frontend React (index.html) ou un fallback intégré."""
    return _serve_index()


@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
def serve_spa_catchall(full_path: str):
    """
    Catch-all SPA : renvoie index.html pour toutes les routes frontend
    (goals, runs/xxx, patches…). Les routes /api, /ws, /assets et /docs
    sont déjà matchées par les handlers précédents donc ne tombent pas ici.
    """
    # Ne pas intercepter les fichiers statiques réels
    if full_path.startswith(("api/", "ws/", "assets/", "docs", "openapi.json", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")
    # Essayer de servir un fichier statique exact (favicon, etc.)
    static_path = os.path.join(FRONTEND_DIST, full_path)
    if os.path.isfile(static_path):
        return FileResponse(static_path)
    return _serve_index()


def _serve_index() -> HTMLResponse:
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index):
        with open(index, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content=_fallback_html())


def _fallback_html() -> str:
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Queen V1</title>
<style>
body{font-family:system-ui;background:#0f0f13;color:#e4e4ef;display:flex;
justify-content:center;align-items:center;min-height:100vh;margin:0}
.c{text-align:center;max-width:500px}
h1{font-size:2rem;margin-bottom:.5rem}
p{color:#9898b0;line-height:1.6}
a{color:#a29bfe;text-decoration:none}
a:hover{text-decoration:underline}
</style></head><body><div class="c">
<h1>🐝 Queen V1</h1>
<p>Le frontend React n'est pas encore buildé.<br>
L'API est opérationnelle.</p>
<p><a href="/docs">📖 Documentation API (Swagger)</a></p>
<p><a href="/api/health">💚 Health check</a> ·
<a href="/api/stats">📊 Stats</a> ·
<a href="/api/goals">🎯 Goals</a></p>
</div></body></html>"""
