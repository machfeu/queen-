"""archive.py — Evolution archive (DGM-like) for Queen.

Stores candidate variants with lineage (parent_id), fitness and artifacts.
This module is deliberately independent from queen_core.memory to avoid
coupling and to keep the stable core unchanged.

Persistence:
- SQLite database (default: /data/queen_evolution.db)
- Snapshot zips and patch files under /data/evolution/
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("queen.evolution")


DEFAULT_DB_PATH = os.getenv("EVOLUTION_DB_PATH", "/data/queen_evolution.db")
DEFAULT_STORE_DIR = os.getenv("EVOLUTION_STORE_DIR", "/data/evolution")


@dataclass
class VariantRecord:
    variant_id: str
    parent_id: Optional[str]
    created_at: str
    fitness: float
    tests_ok: int
    targets: str
    tags: str
    metrics_json: str
    patch_path: str
    snapshot_path: str

    @property
    def metrics(self) -> Dict[str, Any]:
        try:
            return json.loads(self.metrics_json) if self.metrics_json else {}
        except Exception:
            return {}


class EvolutionArchive:
    def __init__(self, db_path: str = DEFAULT_DB_PATH, store_dir: str = DEFAULT_STORE_DIR):
        self.db_path = db_path
        self.store_dir = store_dir
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.store_dir, exist_ok=True)
        os.makedirs(os.path.join(self.store_dir, "patches"), exist_ok=True)
        os.makedirs(os.path.join(self.store_dir, "snapshots"), exist_ok=True)
        self._conn = self._connect()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # Robustness under concurrent readers/writers
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        return conn

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS variants (
              variant_id TEXT PRIMARY KEY,
              parent_id TEXT,
              created_at TEXT NOT NULL,
              fitness REAL NOT NULL,
              tests_ok INTEGER NOT NULL,
              targets TEXT NOT NULL,
              tags TEXT NOT NULL,
              metrics_json TEXT NOT NULL,
              patch_path TEXT NOT NULL,
              snapshot_path TEXT NOT NULL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_variants_parent ON variants(parent_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_variants_fitness ON variants(fitness)")
        self._conn.commit()

    # ─────────────────────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────────────────────

    def add_variant(
        self,
        variant_id: str,
        parent_id: Optional[str],
        fitness: float,
        tests_ok: bool,
        targets: List[str],
        tags: List[str],
        metrics: Dict[str, Any],
        patch_path: str,
        snapshot_path: str,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        rec = (
            variant_id,
            parent_id,
            created_at,
            float(fitness),
            1 if tests_ok else 0,
            json.dumps(targets, ensure_ascii=False),
            json.dumps(tags, ensure_ascii=False),
            json.dumps(metrics, ensure_ascii=False),
            patch_path,
            snapshot_path,
        )
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO variants
            (variant_id,parent_id,created_at,fitness,tests_ok,targets,tags,metrics_json,patch_path,snapshot_path)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            rec,
        )
        self._conn.commit()

    def list_variants(self, limit: int = 200) -> List[VariantRecord]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT variant_id,parent_id,created_at,fitness,tests_ok,targets,tags,metrics_json,patch_path,snapshot_path
            FROM variants
            ORDER BY fitness DESC, created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        return [VariantRecord(*r) for r in rows]

    def get_variant(self, variant_id: str) -> Optional[VariantRecord]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT variant_id,parent_id,created_at,fitness,tests_ok,targets,tags,metrics_json,patch_path,snapshot_path
            FROM variants WHERE variant_id=?
            """,
            (variant_id,),
        )
        row = cur.fetchone()
        return VariantRecord(*row) if row else None

    def child_count(self, variant_id: str) -> int:
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(1) FROM variants WHERE parent_id=?", (variant_id,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def lineage(self, variant_id: str, max_depth: int = 50) -> List[VariantRecord]:
        """Return lineage from variant to root (inclusive)."""
        lineage: List[VariantRecord] = []
        current = self.get_variant(variant_id)
        depth = 0
        while current and depth < max_depth:
            lineage.append(current)
            if not current.parent_id:
                break
            current = self.get_variant(current.parent_id)
            depth += 1
        return lineage

    # ─────────────────────────────────────────────────────────
    # Storage helpers
    # ─────────────────────────────────────────────────────────

    def new_variant_id(self, prefix: str = "v") -> str:
        # time-based id: sortable and unique enough
        t = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        nonce = str(int(time.time() * 1000))[-6:]
        return f"{prefix}-{t}-{nonce}"

    def patch_file_path(self, variant_id: str) -> str:
        return os.path.join(self.store_dir, "patches", f"{variant_id}.diff")

    def snapshot_file_path(self, variant_id: str) -> str:
        return os.path.join(self.store_dir, "snapshots", f"{variant_id}.zip")
