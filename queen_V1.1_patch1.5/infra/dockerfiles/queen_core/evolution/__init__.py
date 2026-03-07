"""queen_core.evolution

MVP "DGM-like" evolution engine for Queen.

Design goals:
- Queen core stays stable; evolution happens by generating *candidate variants*.
- Each candidate is evaluated (smoke tests) and archived with lineage (parent_id).
- Optional: promote a candidate by applying its patch manually.
"""

from .archive import EvolutionArchive
from .evolver import run_evolution

__all__ = ["EvolutionArchive", "run_evolution"]
