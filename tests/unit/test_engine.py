import random

from fairpoker.config import load_config
from fairpoker.simulation.bots import SkillBot
from fairpoker.simulation.engine import play_hand
from fairpoker.simulation.equity import compute_preflop_table, EquityEstimator

TEST_HANDS = 300
PREFLOP_SAMPLES = 20  # tiny table: enough for legal play, far too noisy for real use


def test_hands_conserve_chips_and_respect_stacks() -> None:
    config = load_config()
    preflop = compute_preflop_table(PREFLOP_SAMPLES, seed=0)
    bots = [SkillBot(skill, config.bots, EquityEstimator(preflop, 8)) for skill in (1.0, 0.8, 0.5, 0.3, 0.1, 0.0)]
    rng = random.Random(1)
    max_loss = config.table.starting_stack / config.table.big_blind
    for hand in range(TEST_HANDS):
        result = play_hand(bots, hand % 6, config.table, rng)
        assert abs(sum(result)) < 1e-9
        assert min(result) >= -max_loss
