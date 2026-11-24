"""Real-data analysis of the PHH Pluribus hands: graphs, ratings, tiers, and table fairness.

Two checks of how much the ratings are skill versus luck:
- split-half reliability: rate players on odd sessions and on even sessions separately, then
  correlate the two. Skill repeats across halves; luck does not.
- leave-one-session-out: rate players without session S, score S's table, and test whether
  lower fairness predicts a bigger loss for the table's weakest player.
"""
from collections import defaultdict
from dataclasses import dataclass

import networkx as nx
import pandas as pd
from scipy.stats import spearmanr

from fairpoker.config import ProjectConfig
from fairpoker.fairness.score import score_table
from fairpoker.hands.phh_loader import load_zip_dataset
from fairpoker.hands.records import HandRecord
from fairpoker.network.graphs import build_coplay_graph, build_money_flow_graph
from fairpoker.network.ratings import compute_win_rates, rate_players, summarize_players
from fairpoker.network.tiers import cluster_skill_tiers, detect_player_pools, name_tier


@dataclass(frozen=True, slots=True)
class DatasetAnalysis:
    records: list[HandRecord]
    players: pd.DataFrame       # one row per player
    sessions: pd.DataFrame      # one row per session (table)
    coplay: nx.Graph
    money: nx.DiGraph
    pools: list[set[str]]
    reliability: dict[str, float]


def group_by_session(records: list[HandRecord]) -> dict[str, list[HandRecord]]:
    sessions: dict[str, list[HandRecord]] = defaultdict(list)
    for record in records:
        sessions[record.session_id].append(record)
    return dict(sessions)


def measure_split_half_reliability(records: list[HandRecord], damping: float) -> dict[str, float]:
    """Spearman correlation between ratings from odd sessions and ratings from even sessions."""
    session_ids = sorted({r.session_id for r in records})
    halves = [set(session_ids[0::2]), set(session_ids[1::2])]
    parts = [[r for r in records if r.session_id in half] for half in halves]
    ranks = [rate_players(part, damping) for part in parts]
    rates = [compute_win_rates(part)["bb_per_100"] for part in parts]
    common_rank = ranks[0].index.intersection(ranks[1].index)
    common_rate = rates[0].index.intersection(rates[1].index)
    return {"pagerank_split_half": float(spearmanr(ranks[0][common_rank], ranks[1][common_rank]).statistic), "winrate_split_half": float(spearmanr(rates[0][common_rate], rates[1][common_rate]).statistic), "players_in_both_halves": float(len(common_rank))}


def score_sessions(sessions: dict[str, list[HandRecord]], global_skill: pd.Series, damping: float, scale: float) -> pd.DataFrame:
    """Fairness per session table, with both in-sample and leave-one-session-out ratings."""
    all_records = [r for records in sessions.values() for r in records]
    rows = []
    for session_id, records in sessions.items():
        players = sorted({p for r in records for p in r.players})
        held_out = rate_players([r for r in all_records if r.session_id != session_id], damping)
        known = [p for p in players if p in held_out.index]
        weakest = min(known, key=lambda p: held_out[p])
        weakest_net = sum(net for r in records for p, net in zip(r.players, r.net_bb) if p == weakest)
        weakest_hands = sum(1 for r in records if weakest in r.players)
        rows.append({"session": session_id, "hands": len(records), "players": ", ".join(players), "fairness": score_table([global_skill[p] for p in players], scale).fairness, "fairness_held_out": score_table([held_out[p] for p in known], scale).fairness, "weakest_player": weakest, "weakest_bb_per_100": 100 * weakest_net / weakest_hands})
    return pd.DataFrame(rows).sort_values("fairness")


def run_dataset_analysis(config: ProjectConfig) -> DatasetAnalysis:
    damping = config.ratings.pagerank_damping
    records = load_zip_dataset(config.paths.dataset_zip, config.hands_prefix)
    coplay = build_coplay_graph(records)
    money = build_money_flow_graph(records)
    players = summarize_players(records, damping)
    tier_rank = cluster_skill_tiers(players["skill_z"], config.ratings.tier_count)
    players["tier"] = tier_rank.map(lambda rank: name_tier(int(rank), config.ratings.tier_count))
    pools = detect_player_pools(coplay, config.experiment.seed)
    players["pool"] = pd.Series({p: index for index, pool in enumerate(pools) for p in pool})
    sessions = score_sessions(group_by_session(records), players["skill_z"], damping, config.fairness.skill_std_scale)
    reliability = measure_split_half_reliability(records, damping)
    correlation = spearmanr(sessions["fairness_held_out"], sessions["weakest_bb_per_100"])
    reliability.update({"held_out_fairness_vs_weakest_loss_spearman": float(correlation.statistic), "held_out_fairness_vs_weakest_loss_p": float(correlation.pvalue)})
    return DatasetAnalysis(records=records, players=players, sessions=sessions, coplay=coplay, money=money, pools=pools, reliability=reliability)
