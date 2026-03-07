"""
notifier.py — Système de notifications par webhooks.
Inspiré d'OpenClaw : le système prend l'initiative de communiquer
au lieu d'attendre qu'on le sollicite.

Supporte : Slack, Discord, Telegram, et tout endpoint HTTP POST.
Configurable via variables d'environnement ou config YAML.

Usage:
    from queen_core.notifier import notify, NotifyEvent
    notify(NotifyEvent.PATCH_READY, {"run_id": "abc", "score": 0.85})
"""

import json
import logging
import os
import threading
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("queen.notifier")

try:
    import requests
except ImportError:
    requests = None


# ─── Event types ──────────────────────────────────────────────────────────────

class NotifyEvent(str, Enum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    PATCH_READY = "patch_ready"           # Patch en attente d'approbation
    PATCH_APPROVED = "patch_approved"
    PATCH_APPLIED = "patch_applied"
    PATCH_REJECTED = "patch_rejected"
    BUDGET_WARNING = "budget_warning"     # 80% du budget consommé
    BUDGET_EXCEEDED = "budget_exceeded"
    GOAL_COMPLETED = "goal_completed"
    SELF_HEAL_TRIGGERED = "self_heal_triggered"
    CONSENSUS_DISAGREEMENT = "consensus_disagreement"  # Evaluateurs pas d'accord


# ─── Message formatting ──────────────────────────────────────────────────────

EMOJI_MAP = {
    NotifyEvent.RUN_STARTED: "🚀",
    NotifyEvent.RUN_COMPLETED: "✅",
    NotifyEvent.RUN_FAILED: "❌",
    NotifyEvent.PATCH_READY: "📋",
    NotifyEvent.PATCH_APPROVED: "👍",
    NotifyEvent.PATCH_APPLIED: "🎯",
    NotifyEvent.PATCH_REJECTED: "🚫",
    NotifyEvent.BUDGET_WARNING: "⚠️",
    NotifyEvent.BUDGET_EXCEEDED: "🛑",
    NotifyEvent.GOAL_COMPLETED: "🏆",
    NotifyEvent.SELF_HEAL_TRIGGERED: "🔄",
    NotifyEvent.CONSENSUS_DISAGREEMENT: "🤔",
}

MESSAGE_TEMPLATES = {
    NotifyEvent.RUN_STARTED: "Run `{run_id}` démarré pour le goal « {goal_title} »",
    NotifyEvent.RUN_COMPLETED: "Run `{run_id}` terminé — score: {score}",
    NotifyEvent.RUN_FAILED: "Run `{run_id}` échoué : {reason}",
    NotifyEvent.PATCH_READY: "Patch prêt pour approbation — run `{run_id}`, score: {score}",
    NotifyEvent.PATCH_APPROVED: "Patch approuvé — run `{run_id}`",
    NotifyEvent.PATCH_APPLIED: "Patch appliqué avec succès — {files_changed} fichiers modifiés",
    NotifyEvent.PATCH_REJECTED: "Patch rejeté — run `{run_id}` : {reason}",
    NotifyEvent.BUDGET_WARNING: "Budget à {percent}% — run `{run_id}` ({tokens} tokens, ${cost})",
    NotifyEvent.BUDGET_EXCEEDED: "Budget DÉPASSÉ — run `{run_id}` arrêté ({tokens} tokens, ${cost})",
    NotifyEvent.GOAL_COMPLETED: "Goal « {goal_title} » atteint avec succès !",
    NotifyEvent.SELF_HEAL_TRIGGERED: "Auto-correction déclenchée — tentative {attempt}/2 sur run `{run_id}`",
    NotifyEvent.CONSENSUS_DISAGREEMENT: "Désaccord entre évaluateurs — scores: {scores}, spread: {spread}",
}


def _format_message(event: NotifyEvent, data: Dict[str, Any]) -> str:
    """Formate le message pour un événement."""
    emoji = EMOJI_MAP.get(event, "📢")
    template = MESSAGE_TEMPLATES.get(event, str(event.value))
    try:
        text = template.format(**{k: str(v) for k, v in data.items()})
    except KeyError:
        text = f"{event.value}: {json.dumps(data, default=str)}"
    return f"{emoji} **Queen V1** — {text}"


# ─── Webhook targets ─────────────────────────────────────────────────────────

class WebhookTarget:
    """Un endpoint webhook avec son format."""

    def __init__(self, url: str, format_type: str = "generic", events: Optional[List[str]] = None):
        self.url = url
        self.format_type = format_type  # "slack", "discord", "telegram", "generic"
        self.events = events  # None = tous les événements

    def should_send(self, event: NotifyEvent) -> bool:
        if self.events is None:
            return True
        return event.value in self.events

    def build_payload(self, message: str, event: NotifyEvent, data: Dict[str, Any]) -> Dict:
        """Construit le payload selon le format du webhook."""
        if self.format_type == "slack":
            return {
                "text": message,
                "username": "Queen V1",
                "icon_emoji": EMOJI_MAP.get(event, ":bee:"),
            }
        if self.format_type == "discord":
            return {
                "content": message,
                "username": "Queen V1",
            }
        if self.format_type == "telegram":
            # Telegram bot API: nécessite chat_id. On le lit depuis l'env si dispo.
            chat_id = os.getenv("NOTIFY_TELEGRAM_CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID", "")
            payload = {
                "text": message,
                "parse_mode": "Markdown",
            }
            if chat_id:
                payload["chat_id"] = chat_id
            return payload

        # Format générique
        return {
            "event": event.value,
            "message": message,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "queen_v1",
        }


# ─── Notifier singleton ──────────────────────────────────────────────────────

class Notifier:
    """Gestionnaire de notifications."""

    def __init__(self):
        self._targets: List[WebhookTarget] = []
        self._lock = threading.Lock()
        self._enabled = True
        self._load_from_env()

    def _load_from_env(self):
        """Charge les webhooks depuis les variables d'environnement."""
        # NOTIFY_WEBHOOK_URL=https://hooks.slack.com/services/xxx
        # NOTIFY_WEBHOOK_FORMAT=slack
        # NOTIFY_WEBHOOK_EVENTS=patch_ready,run_failed,budget_exceeded (optionnel)
        url = os.getenv("NOTIFY_WEBHOOK_URL", "")
        if url:
            fmt = os.getenv("NOTIFY_WEBHOOK_FORMAT", "generic")
            events_str = os.getenv("NOTIFY_WEBHOOK_EVENTS", "")
            events = events_str.split(",") if events_str else None
            self.add_target(url, fmt, events)
            logger.info(f"Notifier: loaded webhook ({fmt}) from env")

        # Support de webhooks multiples: NOTIFY_WEBHOOK_URL_2, _3, etc.
        for i in range(2, 6):
            url = os.getenv(f"NOTIFY_WEBHOOK_URL_{i}", "")
            if url:
                fmt = os.getenv(f"NOTIFY_WEBHOOK_FORMAT_{i}", "generic")
                events_str = os.getenv(f"NOTIFY_WEBHOOK_EVENTS_{i}", "")
                events = events_str.split(",") if events_str else None
                self.add_target(url, fmt, events)

    def add_target(self, url: str, format_type: str = "generic",
                   events: Optional[List[str]] = None):
        """Ajoute un webhook target."""
        with self._lock:
            self._targets.append(WebhookTarget(url, format_type, events))

    def send(self, event: NotifyEvent, data: Dict[str, Any]):
        """
        Envoie une notification à tous les targets configurés.
        Non-bloquant : envoie dans un thread séparé.
        """
        if not self._enabled or not self._targets:
            return

        message = _format_message(event, data)

        # Envoi non-bloquant
        thread = threading.Thread(
            target=self._send_all,
            args=(event, message, data),
            daemon=True,
        )
        thread.start()

    def _send_all(self, event: NotifyEvent, message: str, data: Dict[str, Any]):
        """Envoie à tous les targets (appelé dans un thread)."""
        if not requests:
            logger.warning("requests library not available, notifications disabled")
            return

        with self._lock:
            targets = list(self._targets)

        for target in targets:
            if not target.should_send(event):
                continue
            try:
                payload = target.build_payload(message, event, data)
                # Telegram: si chat_id absent, log et skip
                if target.format_type == "telegram" and not payload.get("chat_id"):
                    logger.warning("Telegram webhook configured but chat_id missing (set NOTIFY_TELEGRAM_CHAT_ID)")
                    continue
                last_err = None
                for attempt in range(1, 4):
                    try:
                        resp = requests.post(
                            target.url,
                            json=payload,
                            timeout=10,
                            headers={"Content-Type": "application/json"},
                        )
                        if resp.status_code >= 400:
                            last_err = f"HTTP {resp.status_code}"
                            # Retry on 429/5xx
                            if resp.status_code in (429,) or resp.status_code >= 500:
                                time.sleep(1.5 * attempt)
                                continue
                            logger.warning(f"Webhook {target.format_type} returned {resp.status_code}")
                        else:
                            logger.debug(f"Notification sent: {event.value} → {target.format_type}")
                            last_err = None
                        break
                    except Exception as e:
                        last_err = str(e)
                        time.sleep(1.5 * attempt)
                        continue
                if last_err:
                    logger.warning(f"Webhook send failed ({target.format_type}): {last_err}")
            except Exception as e:
                logger.warning(f"Webhook send failed ({target.format_type}): {e}")

    @property
    def target_count(self) -> int:
        with self._lock:
            return len(self._targets)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled


# ─── Singleton + convenience ──────────────────────────────────────────────────

_notifier: Optional[Notifier] = None
_notifier_lock = threading.Lock()


def get_notifier() -> Notifier:
    global _notifier
    if _notifier is None:
        with _notifier_lock:
            if _notifier is None:
                _notifier = Notifier()
    return _notifier


def notify(event: NotifyEvent, data: Optional[Dict[str, Any]] = None):
    """Shortcut pour envoyer une notification."""
    get_notifier().send(event, data or {})
