"""
budget_tracker.py — Suivi des tokens, temps et coût par run.
Inspiré de SuperAGI : chaque run a un budget configurable.
Si le budget est dépassé, le run est arrêté proprement.

Usage:
    from queen_core.budget_tracker import BudgetTracker, get_tracker
    tracker = get_tracker()
    tracker.record_llm_call(run_id, input_tokens=500, output_tokens=200, model="llama3.1:8b")
    tracker.check_budget(run_id, max_tokens=50000, max_seconds=600)
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("queen.budget")

# ─── Cost estimation per 1K tokens (approximatif) ────────────────────────────

COST_PER_1K = {
    # Ollama local = gratuit
    "llama3.1:8b": 0.0,
    "llama3.1:70b": 0.0,
    "codellama": 0.0,
    "mistral": 0.0,
    # OpenAI
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "gpt-4-turbo": 0.01,
    # Anthropic
    "claude-sonnet-4-20250514": 0.003,
    "claude-haiku-4-5-20251001": 0.001,
    # Default
    "default": 0.001,
}


@dataclass
class RunBudget:
    """État du budget d'un run."""
    run_id: str
    started_at: float = field(default_factory=time.time)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    estimated_cost_usd: float = 0.0
    last_model: str = ""

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "last_model": self.last_model,
        }


class BudgetTracker:
    """Tracker global des budgets par run."""

    def __init__(self):
        self._runs: Dict[str, RunBudget] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, run_id: str) -> RunBudget:
        if run_id not in self._runs:
            self._runs[run_id] = RunBudget(run_id=run_id)
        return self._runs[run_id]

    def record_llm_call(
        self,
        run_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "default",
    ):
        """Enregistre un appel LLM et met à jour le budget."""
        with self._lock:
            budget = self._get_or_create(run_id)
            budget.total_input_tokens += input_tokens
            budget.total_output_tokens += output_tokens
            budget.total_tokens += input_tokens + output_tokens
            budget.llm_calls += 1
            budget.last_model = model

            # Estimate cost
            cost_rate = COST_PER_1K.get(model, COST_PER_1K["default"])
            cost = (input_tokens + output_tokens) / 1000.0 * cost_rate
            budget.estimated_cost_usd += cost

            logger.debug(
                f"Budget [{run_id}]: +{input_tokens}in +{output_tokens}out "
                f"= {budget.total_tokens} total, ${budget.estimated_cost_usd:.4f}"
            )

    def check_budget(
        self,
        run_id: str,
        max_tokens: int = 100_000,
        max_seconds: float = 1800,
        max_cost_usd: float = 1.0,
        max_llm_calls: int = 50,
    ) -> Dict:
        """
        Vérifie si un run a dépassé son budget.
        Retourne {"exceeded": False} ou {"exceeded": True, "reason": "..."}.
        """
        with self._lock:
            budget = self._get_or_create(run_id)

        reasons = []
        if budget.total_tokens > max_tokens:
            reasons.append(f"tokens: {budget.total_tokens}/{max_tokens}")
        if budget.elapsed_seconds > max_seconds:
            reasons.append(f"time: {budget.elapsed_seconds:.0f}s/{max_seconds}s")
        if budget.estimated_cost_usd > max_cost_usd:
            reasons.append(f"cost: ${budget.estimated_cost_usd:.4f}/${max_cost_usd}")
        if budget.llm_calls > max_llm_calls:
            reasons.append(f"calls: {budget.llm_calls}/{max_llm_calls}")

        if reasons:
            logger.warning(f"Budget EXCEEDED [{run_id}]: {', '.join(reasons)}")
            return {"exceeded": True, "reasons": reasons}

        return {"exceeded": False}

    def get_budget(self, run_id: str) -> Optional[Dict]:
        """Retourne l'état du budget d'un run."""
        with self._lock:
            budget = self._runs.get(run_id)
            return budget.to_dict() if budget else None

    def get_all_budgets(self) -> Dict[str, Dict]:
        """Retourne tous les budgets actifs."""
        with self._lock:
            return {rid: b.to_dict() for rid, b in self._runs.items()}

    def clear_run(self, run_id: str):
        """Nettoie le budget d'un run terminé."""
        with self._lock:
            self._runs.pop(run_id, None)


# ─── Singleton ────────────────────────────────────────────────────────────────

_tracker: Optional[BudgetTracker] = None
_tracker_lock = threading.Lock()


def get_tracker() -> BudgetTracker:
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = BudgetTracker()
    return _tracker
