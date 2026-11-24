"""The two player graphs: who sat together, and who won money from whom."""
from collections import defaultdict
from itertools import combinations

import networkx as nx

from fairpoker.hands.records import HandRecord


def build_coplay_graph(records: list[HandRecord]) -> nx.Graph:
    """Undirected graph. Edge weight = number of hands two players shared a table."""
    shared: dict[tuple[str, str], int] = defaultdict(int)
    for record in records:
        for a, b in combinations(sorted(record.players), 2):
            shared[(a, b)] += 1
    graph = nx.Graph()
    graph.add_nodes_from(sorted({player for record in records for player in record.players}))  # sorted: set order varies per run
    graph.add_weighted_edges_from((a, b, count) for (a, b), count in shared.items())
    return graph


def build_money_flow_graph(records: list[HandRecord]) -> nx.DiGraph:
    """Directed graph loser -> winner, weight in big blinds.

    In each hand a loser's chips are split across that hand's winners by their share of the winnings.
    Flows between a pair are then netted, so at most one edge joins any two players.
    """
    gross: dict[tuple[str, str], float] = defaultdict(float)
    for record in records:
        winnings = {player: net for player, net in zip(record.players, record.net_bb) if net > 0}
        total_won = sum(winnings.values())
        if total_won == 0:
            continue
        for loser, net in zip(record.players, record.net_bb):
            if net >= 0:
                continue
            for winner, won in winnings.items():
                gross[(loser, winner)] += -net * won / total_won
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted({player for record in records for player in record.players}))  # sorted: set order varies per run
    for (loser, winner), amount in gross.items():
        net_flow = amount - gross.get((winner, loser), 0.0)
        if net_flow > 0:
            graph.add_edge(loser, winner, weight=net_flow)
    return graph
