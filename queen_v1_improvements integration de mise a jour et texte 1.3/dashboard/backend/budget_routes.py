"""
budget_routes.py — Endpoints API pour le budget tracker.
À inclure dans api.py via: app.include_router(budget_router)
"""

from fastapi import APIRouter
from queen_core.budget_tracker import get_tracker

budget_router = APIRouter(prefix="/api/budget", tags=["Budget"])


@budget_router.get("")
def list_budgets():
    """Liste tous les budgets actifs."""
    tracker = get_tracker()
    return tracker.get_all_budgets()


@budget_router.get("/{run_id}")
def get_run_budget(run_id: str):
    """Budget d'un run spécifique."""
    tracker = get_tracker()
    budget = tracker.get_budget(run_id)
    if not budget:
        return {"run_id": run_id, "status": "no_data"}
    return budget
