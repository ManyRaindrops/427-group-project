"""Static PNG figures for the slides. Every function takes data and the one output path it writes."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

# Validated categorical order (dataviz reference palette, light mode). Fixed per entity, never by rank.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE, INK, INK_SECONDARY, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
# Diverging skill scale: orange (weak) -> neutral gray -> blue (strong).
SKILL_CMAP = LinearSegmentedColormap.from_list("skill", ["#eb6834", "#d9d8d3", "#2a78d6"])
DPI = 200


def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _new_figure(width: float, height: float) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(width, height), facecolor=SURFACE)
    _style_axes(ax)
    return fig, ax


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    return path


def plot_coplay_network(coplay: nx.Graph, players: pd.DataFrame, path: Path) -> Path:
    """Who sat with whom. Node size = hands played, color = PageRank skill, edge width = shared hands."""
    fig, ax = plt.subplots(figsize=(7, 6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    layout = nx.spring_layout(coplay, weight="weight", seed=7, k=1.2)
    weights = np.array([d["weight"] for _, _, d in coplay.edges(data=True)], dtype=float)
    nx.draw_networkx_edges(coplay, layout, ax=ax, width=0.4 + 4 * weights / weights.max(), edge_color="#bdbcb7", alpha=0.8)
    nodes = list(coplay.nodes())
    norm = TwoSlopeNorm(vmin=players["skill_z"].min(), vcenter=0, vmax=players["skill_z"].max())
    nx.draw_networkx_nodes(coplay, layout, ax=ax, nodelist=nodes, node_size=[80 + players.loc[n, "hands"] / 12 for n in nodes], node_color=[players.loc[n, "skill_z"] for n in nodes], cmap=SKILL_CMAP, vmin=norm.vmin, vmax=norm.vmax, edgecolors=SURFACE, linewidths=2)
    nx.draw_networkx_labels(coplay, layout, ax=ax, font_size=8, font_color=INK)
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=SKILL_CMAP), ax=ax, shrink=0.6)
    bar.set_label("PageRank skill (z)", color=INK_SECONDARY)
    return _save(fig, path)


def plot_money_flow(money: nx.DiGraph, players: pd.DataFrame, path: Path, top_edges: int) -> Path:
    """Largest net money flows, loser -> winner. Arrow width = big blinds moved."""
    fig, ax = plt.subplots(figsize=(7, 6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    edges = sorted(money.edges(data=True), key=lambda e: e[2]["weight"], reverse=True)[:top_edges]
    shown = nx.DiGraph()
    shown.add_nodes_from(money.nodes())
    shown.add_edges_from((a, b, d) for a, b, d in edges)
    layout = nx.circular_layout(sorted(shown.nodes(), key=lambda n: -players.loc[n, "skill_z"]))
    max_weight = max(d["weight"] for _, _, d in edges)
    nx.draw_networkx_edges(shown, layout, ax=ax, width=[0.5 + 5 * d["weight"] / max_weight for _, _, d in edges], edge_color="#9d9c97", arrows=True, arrowsize=12, connectionstyle="arc3,rad=0.12", node_size=900)
    norm = TwoSlopeNorm(vmin=players["skill_z"].min(), vcenter=0, vmax=players["skill_z"].max())
    nodes = list(shown.nodes())
    nx.draw_networkx_nodes(shown, layout, ax=ax, nodelist=nodes, node_size=900, node_color=[players.loc[n, "skill_z"] for n in nodes], cmap=SKILL_CMAP, vmin=norm.vmin, vmax=norm.vmax, edgecolors=SURFACE, linewidths=2)
    nx.draw_networkx_labels(shown, layout, ax=ax, font_size=7, font_color=INK)
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=SKILL_CMAP), ax=ax, shrink=0.6)
    bar.set_label("PageRank skill (z)", color=INK_SECONDARY)
    return _save(fig, path)


def plot_skill_vs_winrate(players: pd.DataFrame, path: Path) -> Path:
    """PageRank skill against raw win rate; point size = hands played."""
    fig, ax = _new_figure(7, 4.5)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.axhline(0, color=INK_SECONDARY, linewidth=0.8)
    ax.scatter(players["skill_z"], players["bb_per_100"], s=20 + players["hands"] / 40, color=SERIES[0], edgecolors=SURFACE, linewidths=2, zorder=3)
    x_span = players["skill_z"].max() - players["skill_z"].min()
    y_span = players["bb_per_100"].max() - players["bb_per_100"].min()
    for name, row in players.iterrows():
        # Drop the label below the point when a higher neighbour would collide with it.
        crowded = ((abs(players["skill_z"] - row["skill_z"]) < 0.08 * x_span) & (abs(players["bb_per_100"] - row["bb_per_100"]) < 0.06 * y_span) & (players["bb_per_100"] > row["bb_per_100"])).any()
        ax.annotate(name, (row["skill_z"], row["bb_per_100"]), textcoords="offset points", xytext=(6, -11 if crowded else 4), fontsize=8, color=INK)
    ax.set_xlabel("PageRank skill (z-score)", color=INK_SECONDARY)
    ax.set_ylabel("Raw win rate (bb / 100 hands)", color=INK_SECONDARY)
    return _save(fig, path)


def plot_rating_accuracy(accuracy: pd.DataFrame, path: Path) -> Path:
    """How well each rating recovers true bot skill as hands pile up."""
    fig, ax = _new_figure(7, 4.2)
    series = [("pagerank_spearman", "PageRank on money flow", SERIES[0], 8), ("winrate_spearman", "Raw win rate", SERIES[1], -16)]
    last = accuracy.iloc[-1]
    for column, label, color, label_offset in series:
        ax.plot(accuracy["hands_per_player"], accuracy[column], color=color, linewidth=2, marker="o", markersize=6, label=label)
        ax.annotate(f"{label}: {last[column]:.2f}", (last["hands_per_player"], last[column]), textcoords="offset points", xytext=(-8, label_offset), ha="right", fontsize=8, color=INK)
    ax.set_xscale("log")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Hands played per bot (log scale)", color=INK_SECONDARY)
    ax.set_ylabel("Spearman vs true skill", color=INK_SECONDARY)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    return _save(fig, path)


def plot_tier_results(summary: pd.DataFrame, policies: list[str], tiers: list[str], path: Path) -> Path:
    """Win rate per skill tier under each seating policy, with +/- 1 standard error."""
    fig, ax = _new_figure(8, 4.5)
    width = 0.8 / len(policies)
    x = np.arange(len(tiers))
    for i, policy in enumerate(policies):
        rows = summary[summary["policy"] == policy].set_index("tier").loc[tiers]
        ax.bar(x + (i - (len(policies) - 1) / 2) * width, rows["bb_per_100"], width * 0.92, yerr=rows["se"], color=SERIES[i], label=policy, error_kw={"ecolor": INK_SECONDARY, "elinewidth": 1, "capsize": 2})
    ax.axhline(0, color=INK_SECONDARY, linewidth=0.8)
    ax.set_xticks(x, tiers)
    ax.set_ylabel("Win rate (bb / 100 hands)", color=INK_SECONDARY)
    ax.legend(frameon=False, fontsize=8, ncols=len(policies), loc="upper center", bbox_to_anchor=(0.5, 1.12))
    return _save(fig, path)


def plot_table_fairness(tables: pd.DataFrame, policies: list[str], path: Path) -> Path:
    """Distribution of true table Fairness Score under each seating policy."""
    fig, ax = _new_figure(7, 4.2)
    data = [tables.loc[tables["policy"] == p, "fairness_true"] for p in policies]
    parts = ax.boxplot(data, patch_artist=True, widths=0.5, medianprops={"color": INK})
    for patch, color in zip(parts["boxes"], SERIES):
        patch.set_facecolor(color)
        patch.set_edgecolor(SURFACE)
    ax.set_xticks(range(1, len(policies) + 1), policies)
    ax.set_ylabel("Table Fairness Score (true skill)", color=INK_SECONDARY)
    ax.set_ylim(0, 100)
    return _save(fig, path)
