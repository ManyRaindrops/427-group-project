"""Clustering: split players into skill tiers, and find pools of players who sit together."""
import networkx as nx
import numpy as np
import pandas as pd

KMEANS_ITERATIONS = 100  # 1-D k-means converges in a handful of steps; this is a safety cap


def cluster_skill_tiers(skill: pd.Series, tier_count: int) -> pd.Series:
    """1-D k-means on skill. Returns tier rank per player: 0 = strongest tier."""
    values = skill.to_numpy(dtype=float)
    centers = np.quantile(values, np.linspace(0, 1, tier_count + 2)[1:-1])
    for _ in range(KMEANS_ITERATIONS):
        labels = np.argmin(np.abs(values[:, None] - centers[None, :]), axis=1)
        updated = np.array([values[labels == k].mean() if np.any(labels == k) else centers[k] for k in range(tier_count)])
        if np.allclose(updated, centers):
            break
        centers = updated
    rank_of_center = np.argsort(np.argsort(-centers))
    return pd.Series(rank_of_center[labels], index=skill.index)


def name_tier(tier_rank: int, tier_count: int) -> str:
    """Top tier = shark, bottom tier = fish, anything between = regular."""
    if tier_rank == 0:
        return "shark"
    if tier_rank == tier_count - 1:
        return "fish"
    return "regular"


def detect_player_pools(coplay: nx.Graph, seed: int) -> list[set[str]]:
    """Louvain communities of the co-play graph: groups of players who mostly sit together."""
    return [set(community) for community in nx.community.louvain_communities(coplay, weight="weight", seed=seed)]
