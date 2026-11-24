"""Skill ratings (PageRank on money flow) and exposure measures (centrality, hands played)."""
from collections import defaultdict

import networkx as nx
import numpy as np
import pandas as pd

from fairpoker.hands.records import HandRecord
from fairpoker.network.graphs import build_coplay_graph, build_money_flow_graph


def add_retention_loops(money: nx.DiGraph) -> nx.DiGraph:
    """Copy of the money graph where each player also has a self-loop worth the money they won.

    Plain PageRank makes a node pass on all of its rank through its out-edges, however small its
    losses are: a big winner who lost 5 bb to one player would hand that player nearly all its
    rank. With the loop, a player passes on rank only in proportion to losses / (losses + wins).
    In the bot experiment this raised the Spearman correlation with true skill from 0.32 to 0.63
    at ~1,000 hands per player (docs/methodology.md).
    """
    graph = money.copy()
    for player in money.nodes:
        won = sum(weight for _, _, weight in money.in_edges(player, data="weight"))
        if won > 0:
            graph.add_edge(player, player, weight=won)
    return graph


def compute_pagerank(money: nx.DiGraph, damping: float) -> pd.Series:
    """PageRank of the money-flow graph with retention loops."""
    return pd.Series(nx.pagerank(add_retention_loops(money), alpha=damping, weight="weight"))


def compute_pagerank_skill(money: nx.DiGraph, damping: float) -> pd.Series:
    """Skill z-score per player: standardized log PageRank of the money-flow graph.

    Money flows loser -> winner, so rank pools at players who win, and beating a player who
    wins themselves counts more than beating someone who loses to everyone.
    """
    log_rank = np.log(compute_pagerank(money, damping))
    std = log_rank.std(ddof=0)
    return (log_rank - log_rank.mean()) / std if std > 0 else log_rank * 0.0


def rate_players(records: list[HandRecord], damping: float) -> pd.Series:
    """Convenience: build the money-flow graph from records and return skill z-scores."""
    return compute_pagerank_skill(build_money_flow_graph(records), damping)


def compute_win_rates(records: list[HandRecord]) -> pd.DataFrame:
    """Hands played and raw win rate (big blinds per 100 hands) per player."""
    hands: dict[str, int] = defaultdict(int)
    total_bb: dict[str, float] = defaultdict(float)
    for record in records:
        for player, net in zip(record.players, record.net_bb):
            hands[player] += 1
            total_bb[player] += net
    return pd.DataFrame({"hands": pd.Series(hands), "bb_per_100": pd.Series({p: 100 * total_bb[p] / hands[p] for p in hands})})


def summarize_players(records: list[HandRecord], damping: float) -> pd.DataFrame:
    """One row per player: PageRank, skill z-score, win rate, and how widely they were exposed."""
    coplay = build_coplay_graph(records)
    money = build_money_flow_graph(records)
    table = compute_win_rates(records)
    table["pagerank"] = compute_pagerank(money, damping)
    table["skill_z"] = compute_pagerank_skill(money, damping)
    table["opponents_faced"] = pd.Series(dict(coplay.degree()))
    table["degree_centrality"] = pd.Series(nx.degree_centrality(coplay))
    table["eigenvector_centrality"] = pd.Series(nx.eigenvector_centrality(coplay, weight="weight", max_iter=1000))
    return table.sort_values("skill_z", ascending=False)
