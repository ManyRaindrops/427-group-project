"""Hand equity: chance to win against N random hands, by Monte Carlo.

Preflop equity depends only on the 169 starting-hand classes, so it is computed once and cached.
Postflop equity is sampled on the fly (runout plus random opponent hands).
"""
import json
import random
from collections.abc import Sequence
from pathlib import Path

from fairpoker.simulation.cards import DECK_SIZE, evaluate_hand

MAX_OPPONENTS = 5  # 6-max table
BOARD_SIZE = 5

PreflopTable = dict[str, list[float]]  # class key -> equity vs 1..MAX_OPPONENTS opponents


def preflop_class_key(hole: Sequence[int]) -> str:
    """'AKs', 'AKo' or 'AA' style key."""
    high, low = sorted((hole[0] >> 2, hole[1] >> 2), reverse=True)
    ranks = "23456789TJQKA"
    if high == low:
        return ranks[high] * 2
    return ranks[high] + ranks[low] + ("s" if (hole[0] & 3) == (hole[1] & 3) else "o")


def sample_equity(hole: Sequence[int], board: Sequence[int], opponents: int, samples: int, rng: random.Random) -> float:
    """Monte Carlo equity vs `opponents` random hands. Ties count as a split share."""
    known = set(hole) | set(board)
    deck = [card for card in range(DECK_SIZE) if card not in known]
    missing = BOARD_SIZE - len(board)
    draw = missing + 2 * opponents
    total = 0.0
    for _ in range(samples):
        cards = rng.sample(deck, draw)
        full_board = list(board) + cards[:missing]
        ours = evaluate_hand(list(hole) + full_board)
        best_other = max(evaluate_hand(cards[missing + 2 * i:missing + 2 * i + 2] + full_board) for i in range(opponents))
        if ours > best_other:
            total += 1.0
        elif ours == best_other:
            total += 0.5  # approximation: treats any tie as a two-way split
    return total / samples


def _class_representative(key: str) -> tuple[int, int]:
    ranks = "23456789TJQKA"
    high, low = ranks.index(key[0]), ranks.index(key[1])
    if key.endswith("s"):
        return high * 4, low * 4
    return high * 4, low * 4 + 1


def compute_preflop_table(samples: int, seed: int) -> PreflopTable:
    ranks = "23456789TJQKA"
    keys = [ranks[h] + ranks[l] + suffix for h in range(13) for l in range(h) for suffix in "so"] + [r * 2 for r in ranks]
    rng = random.Random(seed)
    return {key: [sample_equity(_class_representative(key), (), n, samples, rng) for n in range(1, MAX_OPPONENTS + 1)] for key in keys}


def load_preflop_table(cache_dir: Path, samples: int, seed: int) -> PreflopTable:
    """Read the cached preflop table, computing and saving it on first use."""
    path = cache_dir / f"preflop_equity_{samples}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    table = compute_preflop_table(samples, seed)
    path.write_text(json.dumps(table), encoding="utf-8")
    return table


class EquityEstimator:
    """Equity lookups for one bot. Caches the current street so repeated decisions are free."""

    def __init__(self, preflop: PreflopTable, postflop_samples: int) -> None:
        self._preflop = preflop
        self._samples = postflop_samples
        self._cache: dict[tuple, float] = {}

    def equity(self, hole: tuple[int, int], board: tuple[int, ...], opponents: int, rng: random.Random) -> float:
        opponents = max(1, min(opponents, MAX_OPPONENTS))
        if not board:
            return self._preflop[preflop_class_key(hole)][opponents - 1]
        key = (hole, board, opponents)
        if key not in self._cache:
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[key] = sample_equity(hole, board, opponents, self._samples, rng)
        return self._cache[key]
