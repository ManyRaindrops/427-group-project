"""Build the bot population and play one table session (the unit of parallel work)."""
import random
from dataclasses import dataclass

import numpy as np

from fairpoker.config import BotConfig, PopulationConfig, TableConfig
from fairpoker.hands.records import HandRecord
from fairpoker.simulation.bots import BotProfile, SkillBot
from fairpoker.simulation.engine import play_hand
from fairpoker.simulation.equity import EquityEstimator, PreflopTable


@dataclass(frozen=True, slots=True)
class SessionJob:
    session_id: str
    players: tuple[BotProfile, ...]  # in seat order
    seed: int
    hands: int
    table: TableConfig
    bots: BotConfig
    preflop: PreflopTable


def build_population(config: PopulationConfig, rng: np.random.Generator) -> list[BotProfile]:
    """Draw each tier's share of players with skill uniform in the tier's range."""
    profiles: list[BotProfile] = []
    remaining = config.player_count
    for index, tier in enumerate(config.tiers):
        count = remaining if index == len(config.tiers) - 1 else round(tier.share * config.player_count)
        remaining -= count
        for skill in rng.uniform(tier.low, tier.high, count):
            profiles.append(BotProfile(player_id=f"bot{len(profiles):02d}", skill=float(skill), tier=tier.name))
    return profiles


def play_session(job: SessionJob) -> list[HandRecord]:
    """Play `job.hands` hands at one table, moving the button each hand."""
    rng = random.Random(job.seed)
    bots = [SkillBot(profile.skill, job.bots, EquityEstimator(job.preflop, job.bots.postflop_equity_samples)) for profile in job.players]
    player_ids = tuple(profile.player_id for profile in job.players)
    return [HandRecord(session_id=job.session_id, players=player_ids, net_bb=tuple(play_hand(bots, hand % len(bots), job.table, rng))) for hand in range(job.hands)]
