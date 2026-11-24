"""Seating policies: how a site splits its player pool into tables."""
from collections.abc import Callable, Mapping, Sequence

import numpy as np

# A policy gets the players, a skill estimate per player, the table size and an RNG,
# and returns the list of tables (each a list of player ids).
SeatingPolicy = Callable[[Sequence[str], Mapping[str, float], int, np.random.Generator], list[list[str]]]


def seat_randomly(players: Sequence[str], skill: Mapping[str, float], seats: int, rng: np.random.Generator) -> list[list[str]]:
    """Today's default: whoever clicks join first. Skill is ignored."""
    shuffled = [players[i] for i in rng.permutation(len(players))]
    return [shuffled[i:i + seats] for i in range(0, len(shuffled), seats)]


def seat_by_skill(players: Sequence[str], skill: Mapping[str, float], seats: int, rng: np.random.Generator) -> list[list[str]]:
    """Fairness-based seating: sort by estimated skill and fill tables in order.

    For equal-size tables, contiguous blocks of the sorted list minimize the total within-table
    skill variance, which is exactly what the Fairness Score penalizes. Ties are broken randomly.
    """
    jitter = rng.random(len(players))
    ordered = [player for _, _, player in sorted(zip((-skill[p] for p in players), jitter, players))]
    return [ordered[i:i + seats] for i in range(0, len(ordered), seats)]
