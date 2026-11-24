"""A compact no-limit hold'em hand engine: blinds, four betting rounds, side pots, showdown.

Simplification: every raise reopens the betting (real rules do not reopen on a short all-in).
"""
import random
from collections import deque
from collections.abc import Sequence

from fairpoker.config import TableConfig
from fairpoker.simulation.bots import ActionKind, DecisionContext, SkillBot
from fairpoker.simulation.cards import DECK_SIZE, evaluate_hand

STREET_BOARD_SIZES = (0, 3, 4, 5)  # preflop, flop, turn, river


class _Hand:
    """Mutable chip state of one hand in progress."""

    def __init__(self, seats: int, stack: int) -> None:
        self.stacks = [stack] * seats
        self.committed = [0] * seats
        self.street_bets = [0] * seats
        self.folded = [False] * seats

    def put(self, seat: int, amount: int) -> None:
        amount = min(amount, self.stacks[seat])
        self.stacks[seat] -= amount
        self.committed[seat] += amount
        self.street_bets[seat] += amount

    def live(self) -> list[int]:
        return [seat for seat, folded in enumerate(self.folded) if not folded]

    def can_act(self, seat: int) -> bool:
        return not self.folded[seat] and self.stacks[seat] > 0


def play_hand(bots: Sequence[SkillBot], button: int, table: TableConfig, rng: random.Random) -> list[float]:
    """Play one hand and return each seat's net result in big blinds."""
    seats = len(bots)
    deck = list(range(DECK_SIZE))
    rng.shuffle(deck)
    holes = [(deck[2 * i], deck[2 * i + 1]) for i in range(seats)]
    board_cards = deck[2 * seats:2 * seats + 5]

    hand = _Hand(seats, table.starting_stack)
    small_blind_seat, big_blind_seat = (button + 1) % seats, (button + 2) % seats
    hand.put(small_blind_seat, table.small_blind)
    hand.put(big_blind_seat, table.big_blind)

    for street, board_size in enumerate(STREET_BOARD_SIZES):
        board = tuple(board_cards[:board_size])
        if street > 0:
            hand.street_bets = [0] * seats
        first_to_act = (big_blind_seat + 1) % seats if street == 0 else (button + 1) % seats
        _run_betting_round(hand, bots, holes, board, first_to_act, table.big_blind, rng)
        if len(hand.live()) == 1:
            break

    payouts = _award_pots(hand, holes, board_cards)
    return [(payouts[seat] - hand.committed[seat]) / table.big_blind for seat in range(seats)]


def _run_betting_round(hand: _Hand, bots: Sequence[SkillBot], holes: list[tuple[int, int]], board: tuple[int, ...], first: int, big_blind: int, rng: random.Random) -> None:
    seats = len(bots)
    order = [(first + i) % seats for i in range(seats)]
    current_bet = max(hand.street_bets)
    last_raise = big_blind
    pending = deque(seat for seat in order if hand.can_act(seat))
    if sum(hand.can_act(seat) for seat in order) <= 1 and all(hand.street_bets[s] >= current_bet for s in hand.live() if hand.can_act(s)):
        return

    while pending and len(hand.live()) > 1:
        seat = pending.popleft()
        if not hand.can_act(seat):
            continue
        to_call = min(current_bet - hand.street_bets[seat], hand.stacks[seat])
        max_raise_to = hand.street_bets[seat] + hand.stacks[seat]
        contesting = sum(1 for s in hand.live() if s != seat and hand.committed[s] > 0)
        ctx = DecisionContext(hole=holes[seat], board=board, pot=sum(hand.committed), to_call=to_call, current_bet=current_bet, min_raise_to=min(current_bet + last_raise, max_raise_to), max_raise_to=max_raise_to, opponents=max(1, contesting))
        decision = bots[seat].decide(ctx, rng)

        if decision.kind is ActionKind.FOLD and to_call > 0:
            hand.folded[seat] = True
            continue
        if decision.kind is ActionKind.RAISE and hand.stacks[seat] > to_call:
            raise_to = max(ctx.min_raise_to, min(decision.raise_to, max_raise_to))
            last_raise = max(last_raise, raise_to - current_bet)
            current_bet = max(current_bet, raise_to)
            hand.put(seat, raise_to - hand.street_bets[seat])
            position = order.index(seat)
            pending = deque(s for s in order[position + 1:] + order[:position] if hand.can_act(s))
            continue
        hand.put(seat, to_call)


def _award_pots(hand: _Hand, holes: list[tuple[int, int]], board_cards: list[int]) -> list[int]:
    """Split the main pot and any side pots between the best live hands eligible for each."""
    seats = len(holes)
    payouts = [0] * seats
    live = hand.live()
    if len(live) == 1:
        payouts[live[0]] = sum(hand.committed)
        return payouts

    scores = {seat: evaluate_hand(list(holes[seat]) + board_cards) for seat in live}
    previous_level = 0
    winners: list[int] = []
    for level in sorted({hand.committed[seat] for seat in live}):
        pot = sum(min(c, level) - min(c, previous_level) for c in hand.committed)
        eligible = [seat for seat in live if hand.committed[seat] >= level]
        best = max(scores[seat] for seat in eligible)
        winners = [seat for seat in eligible if scores[seat] == best]
        share, remainder = divmod(pot, len(winners))
        for seat in winners:
            payouts[seat] += share
        payouts[winners[0]] += remainder
        previous_level = level
    # Chips a folded player put in above the top live level go to the last pot's winners.
    payouts[winners[0]] += sum(hand.committed) - sum(payouts)
    return payouts
