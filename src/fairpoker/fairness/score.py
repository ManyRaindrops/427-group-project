"""The table Fairness Score: how evenly matched the players at one table are."""
import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableFairness:
    fairness: float   # 0-100, 100 = everyone equally skilled
    skill_std: float  # spread of skill z-scores at the table
    skill_gap: float  # strongest minus weakest player


def score_table(skills: Sequence[float], scale: float) -> TableFairness:
    """Fairness = 100 * exp(-std / scale).

    Why std: a player's expected loss at a table grows with how far they sit below the table's
    average skill, and the table-wide sum of those gaps is driven by the spread of skill.
    """
    count = len(skills)
    mean = sum(skills) / count
    std = math.sqrt(sum((s - mean) ** 2 for s in skills) / count)
    return TableFairness(fairness=100.0 * math.exp(-std / scale), skill_std=std, skill_gap=max(skills) - min(skills))
