"""Write analysis and experiment results as CSV / JSON plus the figures that go with them."""
import json

from fairpoker.config import OutputPaths
from fairpoker.pipelines.dataset_analysis import DatasetAnalysis
from fairpoker.pipelines.seating_experiment import POLICIES, PENALTY_ARM, ExperimentResult, summarize_tier_results
from fairpoker.reporting import figures

MONEY_FLOW_EDGES_SHOWN = 25  # the Pluribus flow graph has 65 edges; the top 25 stay readable on a slide
TIER_ORDER = ["shark", "regular", "fish"]


def write_dataset_report(analysis: DatasetAnalysis, paths: OutputPaths) -> dict:
    reports, figs = paths.reports, paths.figures
    analysis.players.to_csv(reports / "dataset_players.csv", index_label="player")
    analysis.sessions.to_csv(reports / "dataset_sessions.csv", index=False)
    summary = {"hands": len(analysis.records), "players": analysis.coplay.number_of_nodes(), "sessions": int(analysis.sessions.shape[0]), "coplay_edges": analysis.coplay.number_of_edges(), "money_flow_edges": analysis.money.number_of_edges(), "player_pools": [sorted(pool) for pool in analysis.pools], **analysis.reliability}
    (reports / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    figures.plot_coplay_network(analysis.coplay, analysis.players, figs / "dataset_coplay_network.png")
    figures.plot_money_flow(analysis.money, analysis.players, figs / "dataset_money_flow.png", MONEY_FLOW_EDGES_SHOWN)
    figures.plot_skill_vs_winrate(analysis.players, figs / "dataset_skill_vs_winrate.png")
    return summary


def write_experiment_report(result: ExperimentResult, paths: OutputPaths) -> dict:
    reports, figs = paths.reports, paths.figures
    tiers = summarize_tier_results(result)
    tiers.to_csv(reports / "experiment_tier_results.csv", index=False)
    result.tables.to_csv(reports / "experiment_tables.csv", index=False)
    result.rating_accuracy.to_csv(reports / "experiment_rating_accuracy.csv", index=False)
    result.population.to_csv(reports / "experiment_population.csv", index=False)

    policy_names = [spec.name for spec in POLICIES]
    fish = tiers[tiers["tier"] == "fish"].set_index("policy")["bb_per_100"]
    fairness = result.tables.groupby("policy")["fairness_true"].mean()
    summary = {
        "history_hands": len(result.history),
        "evaluation_hands_per_policy": len(result.evaluation["random"]),
        "fish_bb_per_100": fish.to_dict(),
        "fish_loss_reduction_vs_random": {p: float(1 - fish[p] / fish["random"]) for p in fish.index if p != "random"},
        "mean_table_fairness": fairness.to_dict(),
        "final_rating_accuracy": result.rating_accuracy.iloc[-1].to_dict(),
    }
    (reports / "experiment_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    figures.plot_rating_accuracy(result.rating_accuracy, figs / "experiment_rating_accuracy.png")
    figures.plot_tier_results(tiers, policy_names + [PENALTY_ARM], TIER_ORDER, figs / "experiment_tier_results.png")
    figures.plot_table_fairness(result.tables, policy_names, figs / "experiment_table_fairness.png")
    return summary


def format_summary(summary: dict) -> str:
    return json.dumps(summary, indent=2, default=lambda value: round(value, 3) if isinstance(value, float) else str(value))

