"""Cards as ints 0-51 and a fast 5-to-7 card hold'em hand evaluator.

pokerkit's evaluator is exact but takes ~150 us per hand; the bots need thousands of
evaluations per hand for equity estimates, so the simulator uses this one instead.
tests/unit/test_cards.py checks it against pokerkit on random hands.
"""
from collections.abc import Sequence

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK_SIZE = 52
STRAIGHT_MASK = 0b11111
ACE_RANK = 12

# Hand categories, weakest to strongest.
HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)


def card_from_text(text: str) -> int:
    """'As' -> int. rank = card // 4 (0 = deuce), suit = card % 4."""
    return RANKS.index(text[0]) * 4 + SUITS.index(text[1])


def cards_from_text(text: str) -> list[int]:
    """'AsKd7c' -> [ints]."""
    return [card_from_text(text[i:i + 2]) for i in range(0, len(text), 2)]


def card_rank(card: int) -> int:
    return card >> 2


def _pack(category: int, ranks: Sequence[int]) -> int:
    """Score = category, then up to five tiebreak ranks, each in 4 bits. Higher is better."""
    score = category
    for i in range(5):
        score = (score << 4) | (ranks[i] if i < len(ranks) else 0)
    return score


def _straight_high(rank_mask: int) -> int:
    """Highest rank topping a 5-card straight in the 13-bit rank mask, or -1. Handles A-2-3-4-5."""
    extended = (rank_mask << 1) | ((rank_mask >> ACE_RANK) & 1)  # bit 0 = ace played low
    for top in range(13, 3, -1):
        if (extended >> (top - 4)) & STRAIGHT_MASK == STRAIGHT_MASK:
            return top - 1
    return -1


def _top_ranks(rank_mask: int, count: int) -> list[int]:
    return [r for r in range(ACE_RANK, -1, -1) if rank_mask >> r & 1][:count]


def evaluate_hand(cards: Sequence[int]) -> int:
    """Strength of the best 5-card hand from 5-7 cards. Compare scores with < and ==."""
    counts = [0] * 13
    suit_masks = [0, 0, 0, 0]
    for card in cards:
        counts[card >> 2] += 1
        suit_masks[card & 3] |= 1 << (card >> 2)

    # With at most 7 cards, a 5-card flush rules out quads and full houses, so it decides the hand.
    for mask in suit_masks:
        if bin(mask).count("1") >= 5:
            straight_top = _straight_high(mask)
            if straight_top >= 0:
                return _pack(STRAIGHT_FLUSH, [straight_top])
            return _pack(FLUSH, _top_ranks(mask, 5))

    quads = [r for r in range(ACE_RANK, -1, -1) if counts[r] == 4]
    trips = [r for r in range(ACE_RANK, -1, -1) if counts[r] == 3]
    pairs = [r for r in range(ACE_RANK, -1, -1) if counts[r] == 2]
    singles = [r for r in range(ACE_RANK, -1, -1) if counts[r] == 1]

    if quads:
        kicker = max([r for r in range(13) if counts[r] and r != quads[0]], default=0)
        return _pack(QUADS, [quads[0], kicker])
    if trips and (len(trips) > 1 or pairs):
        pair_rank = max(trips[1:] + pairs)
        return _pack(FULL_HOUSE, [trips[0], pair_rank])

    rank_mask = 0
    for r in range(13):
        if counts[r]:
            rank_mask |= 1 << r
    straight_top = _straight_high(rank_mask)
    if straight_top >= 0:
        return _pack(STRAIGHT, [straight_top])
    if trips:
        return _pack(TRIPS, [trips[0]] + singles[:2])
    if len(pairs) >= 2:
        kicker = max(pairs[2:] + singles, default=0)
        return _pack(TWO_PAIR, [pairs[0], pairs[1], kicker])
    if pairs:
        return _pack(PAIR, [pairs[0]] + singles[:3])
    return _pack(HIGH_CARD, singles[:5])
