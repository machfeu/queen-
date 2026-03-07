"""selector.py — Parent selection strategy (DGM-like).

We want two things:
- exploit: prefer high-fitness variants
- explore: avoid premature convergence by penalizing variants with many children

This is inspired by the selection heuristic used in DGM: favor variants with
good score but limit over-exploited branches.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from .archive import EvolutionArchive, VariantRecord

logger = logging.getLogger("queen.evolution")


def select_parent(
    archive: EvolutionArchive,
    exploration: float = 0.15,
    child_penalty: float = 0.35,
    top_k: int = 30,
) -> Optional[VariantRecord]:
    variants = archive.list_variants(limit=max(top_k, 50))
    if not variants:
        return None

    # Explore: random pick sometimes (keeps diversity)
    if random.random() < exploration:
        return random.choice(variants)

    best = None
    best_score = float("-inf")
    for v in variants[:top_k]:
        children = archive.child_count(v.variant_id)
        # Penalize crowded branches
        adjusted = float(v.fitness) / (1.0 + child_penalty * max(children, 0))
        if adjusted > best_score:
            best = v
            best_score = adjusted
    return best
