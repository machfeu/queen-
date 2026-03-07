"""fitness.py — Fitness function for Queen evolution (MVP).

We deliberately keep the fitness simple and hard to game.
Primary objective: *stability* (smoke tests pass).
Secondary objective: *efficiency* (runtime and budget).
"""

from __future__ import annotations

from typing import Dict, Any


def compute_fitness(metrics: Dict[str, Any]) -> float:
    """Return a fitness score in [0, 1.5] approximately."""
    smoke_ok = 1.0 if metrics.get("smoke_ok") else 0.0
    compile_ok = 1.0 if metrics.get("compile_ok") else 0.0

    # runtime: prefer faster but don't overfit
    runtime_s = float(metrics.get("runtime_seconds", 9999.0))
    runtime_bonus = 0.0
    if runtime_s <= 10:
        runtime_bonus = 0.15
    elif runtime_s <= 30:
        runtime_bonus = 0.08
    elif runtime_s <= 60:
        runtime_bonus = 0.03

    # Budget: prefer cheaper
    budget_cost = float(metrics.get("budget_cost", 0.0))
    budget_bonus = 0.0
    if budget_cost <= 0.01:
        budget_bonus = 0.10
    elif budget_cost <= 0.05:
        budget_bonus = 0.05

    # Penalize security violations
    violations = int(metrics.get("safety_violations", 0))
    penalty = min(0.5, 0.05 * violations)

    base = 0.65 * smoke_ok + 0.35 * compile_ok
    return max(0.0, base + runtime_bonus + budget_bonus - penalty)
