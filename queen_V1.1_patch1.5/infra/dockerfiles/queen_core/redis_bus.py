"""
redis_bus.py — Communication inter-modules via Redis (queues + pubsub).
"""

import json
import logging
import os
import time
import threading
from typing import Optional, Dict, Any, Callable

import redis

logger = logging.getLogger("queen.redis")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


_redis_singleton = None
_redis_lock = threading.Lock()

# Queue names
QUEUE_JOBS = "queen:jobs"                    # Main job queue
QUEUE_JOBS_PRIORITY = "queen:jobs:priority"  # Priority queue
QUEUE_RESULTS = "queen:results"              # Results from workers

# PubSub channels
CHANNEL_EVENTS = "queen:events"              # Real-time events for dashboard
CHANNEL_LOGS = "queen:logs"                  # Log stream


def get_redis() -> redis.Redis:
    """Get Redis connection (singleton)."""
    global _redis_singleton
    if _redis_singleton is None:
        with _redis_lock:
            if _redis_singleton is None:
                pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
                _redis_singleton = redis.Redis(connection_pool=pool, decode_responses=True)
    return _redis_singleton


def enqueue_job(job_data: Dict[str, Any], priority: bool = False):
    """Push a job onto the queue."""
    r = get_redis()
    queue = QUEUE_JOBS_PRIORITY if priority else QUEUE_JOBS
    r.lpush(queue, json.dumps(job_data, ensure_ascii=False))
    publish_event("job_queued", {"job_id": job_data.get("id"), "type": job_data.get("job_type")})


def dequeue_job(timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Pop a job from the queue (priority first). Blocking with timeout."""
    r = get_redis()
    # Try priority queue first
    result = r.brpop([QUEUE_JOBS_PRIORITY, QUEUE_JOBS], timeout=timeout)
    if result:
        _, data = result
        return json.loads(data)
    return None


def push_result(result_data: Dict[str, Any]):
    """Push a job result."""
    r = get_redis()
    r.lpush(QUEUE_RESULTS, json.dumps(result_data, ensure_ascii=False))
    publish_event("job_completed", {
        "job_id": result_data.get("job_id"),
        "status": result_data.get("status"),
    })


def pop_result(timeout: int = 1) -> Optional[Dict[str, Any]]:
    """Pop a job result. Non-blocking friendly."""
    r = get_redis()
    result = r.brpop(QUEUE_RESULTS, timeout=timeout)
    if result:
        _, data = result
        return json.loads(data)
    return None


def publish_event(event_type: str, data: Dict[str, Any]):
    """Publish a real-time event for the dashboard."""
    r = get_redis()
    event = {"type": event_type, "data": data, "timestamp": time.time()}
    r.publish(CHANNEL_EVENTS, json.dumps(event, ensure_ascii=False))


def publish_log(level: str, source: str, message: str):
    """Publish a log entry."""
    r = get_redis()
    entry = {
        "level": level, "source": source, "message": message,
        "timestamp": time.time(),
    }
    r.publish(CHANNEL_LOGS, json.dumps(entry, ensure_ascii=False))
    # Also keep last 1000 logs in a list
    r.lpush("queen:log_history", json.dumps(entry, ensure_ascii=False))
    r.ltrim("queen:log_history", 0, 999)


def get_recent_logs(count: int = 100):
    """Get recent log entries (tolérant aux entrées corrompues)."""
    r = get_redis()
    entries = r.lrange("queen:log_history", 0, count - 1)
    out = []
    for e in entries:
        try:
            out.append(json.loads(e))
        except Exception:
            continue
    return out


def subscribe_events(callback: Callable[[Dict[str, Any]], None]):
    """Subscribe to real-time events. Blocking."""
    r = get_redis()
    pubsub = r.pubsub()
    pubsub.subscribe(CHANNEL_EVENTS)
    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                event = json.loads(message["data"])
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")


def health_check() -> Dict[str, Any]:
    """Check Redis availability."""
    try:
        r = get_redis()
        r.ping()
        info = r.info("memory")
        return {
            "status": "ok",
            "used_memory_human": info.get("used_memory_human", "?"),
            "connected_clients": r.info("clients").get("connected_clients", 0),
            "queue_length": r.llen(QUEUE_JOBS) + r.llen(QUEUE_JOBS_PRIORITY),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
