import numpy as np
import pandas as pd
import pytest

from fairpoker.fairness.penalty import apply_fairness_penalty
from fairpoker.fairness.score import score_table
from fairpoker.fairness.seating import seat_by_skill, seat_randomly
from fairpoker.hands.records import HandRecord
from fairpoker.network.graphs import build_coplay_graph, build_money_flow_graph
from fairpoker.network.ratings import rate_players
from fairpoker.network.tiers import cluster_skill_tiers

DAMPING = 0.85


def _hand(players: str, nets: list[float], session: str = "s1") -> HandRecord:
    return HandRecord(session_id=session, players=tuple(players), net_bb=tuple(nets))


def test_money_flow_nets_pairwise_flows() -> None:
    records = [_hand("AB", [10, -10]), _hand("AB", [-4, 4])]
    money = build_money_flow_graph(records)
    assert list(money.edges(data="weight")) == [("B", "A", 6)]


def test_money_flow_splits_loss_across_winners() -> None:
    money = build_money_flow_graph([_hand("ABC", [3, 1, -4])])
    assert money["C"]["A"]["weight"] == pytest.approx(3)
    assert money["C"]["B"]["weight"] == pytest.approx(1)


def test_coplay_counts_shared_hands() -> None:
    coplay = build_coplay_graph([_hand("ABC", [1, 0, -1]), _hand("AB", [1, -1])])
    assert coplay["A"]["B"]["weight"] == 2 and coplay["A"]["C"]["weight"] == 1


def test_pagerank_ranks_consistent_winner_first() -> None:
    records = [_hand("ABC", [5, -2, -3]) for _ in range(20)] + [_hand("BC", [1, -1]) for _ in range(20)]
    skill = rate_players(records, DAMPING)
    assert list(skill.sort_values(ascending=False).index) == ["A", "B", "C"]


def test_fairness_is_100_for_equal_skill_and_falls_with_spread() -> None:
    assert score_table([0.3] * 6, 1.0).fairness == pytest.approx(100)
    assert score_table([-1, 1] * 3, 1.0).fairness < score_table([-0.2, 0.2] * 3, 1.0).fairness


def test_penalty_conserves_chips_and_skips_fair_tables() -> None:
    record = _hand("ABC", [9, -6, -3])
    adjusted = apply_fairness_penalty(record, fairness=40, rate=0.25)
    assert sum(adjusted.net_bb) == pytest.approx(0)
    assert adjusted.net_bb[0] < 9 and adjusted.net_bb[1] > -6
    assert apply_fairness_penalty(record, fairness=100, rate=0.25) == record


def test_skill_seating_groups_similar_players() -> None:
    players = [f"p{i}" for i in range(12)]
    skill = {p: float(i) for i, p in enumerate(players)}
    tables = seat_by_skill(players, skill, 6, np.random.default_rng(0))
    assert sorted(tables[0]) == sorted(players[6:]) and sorted(tables[1]) == sorted(players[:6])
    random_tables = seat_randomly(players, skill, 6, np.random.default_rng(0))
    assert sorted(p for t in random_tables for p in t) == sorted(players)


def test_tiers_split_three_clear_groups() -> None:
    skill = pd.Series({"a": 2.0, "b": 2.1, "c": 0.0, "d": 0.1, "e": -2.0, "f": -2.1})
    tiers = cluster_skill_tiers(skill, 3)
    assert tiers["a"] == tiers["b"] == 0 and tiers["c"] == tiers["d"] == 1 and tiers["e"] == tiers["f"] == 2
