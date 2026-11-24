import random

from pokerkit import StandardHighHand

from fairpoker.simulation.cards import RANKS, SUITS, cards_from_text, evaluate_hand

SAMPLE_PAIRS = 3000


def _to_text(card: int) -> str:
    return RANKS[card >> 2] + SUITS[card & 3]


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def test_matches_pokerkit_ordering_on_random_hands() -> None:
    rng = random.Random(0)
    for _ in range(SAMPLE_PAIRS):
        deck = rng.sample(range(52), 9)
        board, hole_a, hole_b = deck[:5], deck[5:7], deck[7:9]
        ours = _sign(evaluate_hand(hole_a + board) - evaluate_hand(hole_b + board))
        hand_a = StandardHighHand.from_game("".join(map(_to_text, hole_a)), "".join(map(_to_text, board)))
        hand_b = StandardHighHand.from_game("".join(map(_to_text, hole_b)), "".join(map(_to_text, board)))
        theirs = (hand_a > hand_b) - (hand_a < hand_b)
        assert ours == theirs, (hole_a, hole_b, board)


def test_wheel_straight_and_flush_beats_straight() -> None:
    wheel = evaluate_hand(cards_from_text("As2d3c4h5s9dKc"))
    six_high = evaluate_hand(cards_from_text("2d3c4h5s6s9dKc"))
    flush = evaluate_hand(cards_from_text("2h7h9hJhKh3c4d"))
    assert wheel < six_high < flush


def test_card_parsing_round_trip() -> None:
    assert [_to_text(c) for c in cards_from_text("AsTd2c")] == ["As", "Td", "2c"]
