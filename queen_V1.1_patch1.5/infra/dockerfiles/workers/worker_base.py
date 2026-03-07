"""
worker_base.py — Worker de base pour Queen V1.
Écoute Redis, exécute les jobs, renvoie les résultats.
Chaque worker tourne dans un container séparé, non-root.
"""

import json
import logging
import os
import signal
import sys
import time
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Optional

sys.path.insert(0, "/app")

from queen_core import redis_bus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

WORKER_ID = os.getenv("WORKER_ID", f"worker_{uuid.uuid4().hex[:6]}")
WORKER_TYPES = os.getenv("WORKER_TYPES", "research,codegen,test,eval,patch").split(",")

logger = logging.getLogger(f"worker.{WORKER_ID}")
_shutdown = threading.Event()


class WorkerBase:
    """Base class for all workers."""

    def __init__(self):
        self.worker_id = WORKER_ID
        self.handlers: Dict[str, Callable] = {}
        self.register_handlers()

    def register_handlers(self):
        """Override in subclass to register job type handlers."""
        pass

    def handle_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single job. Returns result dict."""
        job_type = job.get("job_type", "")
        handler = self.handlers.get(job_type)

        if not handler:
            return {
                "job_id": job.get("id", ""),
                "worker_id": self.worker_id,
                "status": "failed",
                "result": {"error": f"No handler for job type: {job_type}"},
                "logs": f"Worker {self.worker_id} has no handler for {job_type}",
            }

        start = time.time()
        timeout = job.get("timeout_seconds", 300)

        try:
            redis_bus.publish_log("info", self.worker_id,
                                  f"Starting job {job.get('id')} ({job_type})")

            # Execute with timeout
            result_container = [None]
            error_container = [None]

            def _run():
                try:
                    result_container[0] = handler(job)
                except Exception as e:
                    error_container[0] = str(e)

            thread = threading.Thread(target=_run)
            thread.start()
            thread.join(timeout=timeout)

            elapsed = time.time() - start

            if thread.is_alive():
                return {
                    "job_id": job.get("id", ""),
                    "worker_id": self.worker_id,
                    "status": "timeout",
                    "result": {"error": f"Job timed out after {timeout}s"},
                    "logs": f"Timeout after {elapsed:.1f}s",
                }

            if error_container[0]:
                return {
                    "job_id": job.get("id", ""),
                    "worker_id": self.worker_id,
                    "status": "failed",
                    "result": {"error": error_container[0]},
                    "logs": f"Error after {elapsed:.1f}s: {error_container[0]}",
                }

            result = result_container[0] or {}
            return {
                "job_id": job.get("id", ""),
                "worker_id": self.worker_id,
                "status": "success",
                "result": result,
                "logs": f"Completed in {elapsed:.1f}s",
            }

        except Exception as e:
            return {
                "job_id": job.get("id", ""),
                "worker_id": self.worker_id,
                "status": "failed",
                "result": {"error": str(e)},
                "logs": str(e),
            }

    def run(self):
        """Main worker loop."""
        logger.info(f"🔧 Worker {self.worker_id} started (types: {WORKER_TYPES})")
        redis_bus.publish_log("info", self.worker_id, f"Worker started: {WORKER_TYPES}")

        def handle_signal(sig, frame):
            logger.info("Shutting down worker...")
            _shutdown.set()

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        while not _shutdown.is_set():
            try:
                job = redis_bus.dequeue_job(timeout=3)
                if not job:
                    continue

                job_type = job.get("job_type", "")
                if job_type not in WORKER_TYPES and "*" not in WORKER_TYPES:
                    # Not for us — requeue
                    redis_bus.enqueue_job(job)
                    continue

                result = self.handle_job(job)
                redis_bus.push_result(result)

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(2)

        logger.info(f"🔧 Worker {self.worker_id} shut down")
