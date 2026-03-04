"""
notifier_routes.py — Endpoints API pour le système de notifications.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from queen_core.notifier import get_notifier, notify, NotifyEvent

notifier_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class WebhookConfig(BaseModel):
    url: str
    format: str = "generic"  # slack, discord, telegram, generic
    events: Optional[List[str]] = None


@notifier_router.get("/status")
def notification_status():
    """Statut du notifier : nombre de targets, activé/désactivé."""
    n = get_notifier()
    return {
        "enabled": n._enabled,
        "targets": n.target_count,
    }


@notifier_router.post("/webhook")
def add_webhook(config: WebhookConfig):
    """Ajoute un webhook dynamiquement."""
    n = get_notifier()
    n.add_target(config.url, config.format, config.events)
    return {"status": "added", "targets": n.target_count}


@notifier_router.post("/test")
def test_notification():
    """Envoie une notification de test à tous les webhooks."""
    notify(NotifyEvent.RUN_COMPLETED, {
        "run_id": "test-000",
        "score": "0.95 (test)",
    })
    return {"status": "sent"}


@notifier_router.post("/enable")
def enable_notifications(enabled: bool = True):
    """Active ou désactive les notifications."""
    n = get_notifier()
    n.set_enabled(enabled)
    return {"enabled": enabled}
