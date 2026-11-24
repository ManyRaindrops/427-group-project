"""Bots whose play quality is a single skill number s in [0, 1].

Skill is never used to decide who wins. It only changes how well a bot judges its hand and
how disciplined it is, so any edge strong bots get comes from playing real hands better:
- equity noise: low-skill bots misjudge how strong their hand is
- looseness: low-skill bots call with worse odds than the pot offers ("calling station")
- hand reading: high-skill bots respect big bets and fold marginal hands to them
- aggression: high-skill bots raise their strong hands for value and bluff a little
"""
import random
from dataclasses import dataclass
from enum import Enum

from fairpoker.config import BotConfig
from fairpoker.simulation.equity import EquityEstimator


class ActionKind(Enum):
    FOLD = "fold"
    CALL = "call"  # check when there is nothing to call
    RAISE = "raise"


@dataclass(frozen=True, slots=True)
class Decision:
    kind: ActionKind
    raise_to: int = 0  # total street bet after the raise


@dataclass(frozen=True, slots=True)
class DecisionContext:
    hole: tuple[int, int]
    board: tuple[int, ...]
    pot: int            # chips in the middle before this decision
    to_call: int
    current_bet: int    # highest street bet so far
    min_raise_to: int
    max_raise_to: int   # all-in
    opponents: int      # opponents still contesting the pot


@dataclass(frozen=True, slots=True)
class BotProfile:
    player_id: str
    skill: float
    tier: str


class SkillBot:
    def __init__(self, skill: float, config: BotConfig, equity: EquityEstimator) -> None:
        self.skill = skill
        self._config = config
        self._equity = equity

    def decide(self, ctx: DecisionContext, rng: random.Random) -> Decision:
        s, cfg = self.skill, self._config
        raw_equity = self._equity.equity(ctx.hole, ctx.board, ctx.opponents, rng)

        pressure = min(1.0, ctx.to_call / max(ctx.pot, 1))
        read_equity = raw_equity ** (1.0 + cfg.hand_reading_max * s * pressure)
        perceived = min(1.0, max(0.0, read_equity + rng.gauss(0.0, cfg.equity_noise_max * (1.0 - s))))

        can_raise = ctx.max_raise_to > ctx.current_bet
        fair_share = 1.0 / (ctx.opponents + 1)
        wants_raise = perceived > fair_share + cfg.raise_margin
        raise_chance = cfg.passive_raise_floor + (1.0 - cfg.passive_raise_floor) * s
        if can_raise and wants_raise and rng.random() < raise_chance:
            return Decision(ActionKind.RAISE, self._bet_size(ctx))

        if ctx.to_call == 0:
            if can_raise and rng.random() < cfg.bluff_rate_max * s:
                return Decision(ActionKind.RAISE, self._bet_size(ctx))
            return Decision(ActionKind.CALL)

        pot_odds = ctx.to_call / (ctx.pot + ctx.to_call)
        if perceived >= pot_odds - cfg.call_looseness_max * (1.0 - s):
            return Decision(ActionKind.CALL)
        return Decision(ActionKind.FOLD)

    def _bet_size(self, ctx: DecisionContext) -> int:
        target = ctx.current_bet + int(self._config.bet_pot_fraction * (ctx.pot + ctx.to_call))
        return max(ctx.min_raise_to, min(target, ctx.max_raise_to))
