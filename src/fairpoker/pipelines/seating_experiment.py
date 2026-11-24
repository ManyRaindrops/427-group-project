"""Evaluation: do bots of known skill lose less when seated by Fairness Score?

1. History phase: everyone plays randomly seated sessions. Nobody knows anyone's skill.
2. The site rates every bot with PageRank on the money-flow graph of that history.
3. Evaluation phase: the same bots play more sessions under each seating policy, with ratings
   refreshed after every session. Table t of session k uses the same deck seed under every
   policy (common random numbers), so policies differ by seating, not by card luck.
"""
from collections.abc import Callable, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fairpoker.config import ProjectConfig
from fairpoker.fairness.penalty import apply_fairness_penalty
from fairpoker.fairness.score import score_table
from fairpoker.fairness.seating import SeatingPolicy, seat_by_skill, seat_randomly
from fairpoker.hands.records import HandRecord
from fairpoker.network.ratings import compute_win_rates, rate_players
from fairpoker.simulation.bots import BotProfile
from fairpoker.simulation.equity import PreflopTable, load_preflop_table
from fairpoker.simulation.sessions import SessionJob, build_population, play_session

HISTORY_PHASE, EVALUATION_PHASE = 0, 1
PENALTY_ARM = "random + penalty"


@dataclass(frozen=True, slots=True)
class PolicySpec:
    name: str
    seat: SeatingPolicy
    skill_source: str  # "estimated" (PageRank) or "true" (oracle upper bound)


POLICIES = (PolicySpec("random", seat_randomly, "estimated"), PolicySpec("fairness (PageRank)", seat_by_skill, "estimated"), PolicySpec("fairness (oracle)", seat_by_skill, "true"))


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    population: pd.DataFrame           # player_id, skill, skill_z, tier
    history: list[HandRecord]
    evaluation: dict[str, list[HandRecord]]  # policy name -> records (incl. penalty arm)
    tables: pd.DataFrame               # one row per (policy, session, table)
    rating_accuracy: pd.DataFrame      # how well ratings track true skill as hands accumulate


def _session_seed(base: int, phase: int, session: int, table: int) -> int:
    return int(np.random.SeedSequence([base, phase, session, table]).generate_state(1)[0])


def _play_sessions(jobs: list[SessionJob], workers: int, pool: ProcessPoolExecutor | None) -> list[list[HandRecord]]:
    if pool is None or workers <= 1:
        return [play_session(job) for job in jobs]
    return list(pool.map(play_session, jobs))


def _make_jobs(tables: list[list[str]], profiles: Mapping[str, BotProfile], label: str, phase: int, session: int, config: ProjectConfig, preflop: PreflopTable) -> list[SessionJob]:
    hands = config.experiment.hands_per_session
    return [SessionJob(session_id=f"{label}-s{session:03d}-t{t}", players=tuple(profiles[p] for p in table), seed=_session_seed(config.experiment.seed, phase, session, t), hands=hands, table=config.table, bots=config.bots, preflop=preflop) for t, table in enumerate(tables)]


def _true_skill_z(population: list[BotProfile]) -> dict[str, float]:
    skills = np.array([p.skill for p in population])
    return {p.player_id: float((p.skill - skills.mean()) / skills.std()) for p in population}


def measure_rating_accuracy(records: list[HandRecord], true_skill: Mapping[str, float], damping: float, checkpoints: list[int]) -> pd.DataFrame:
    """Spearman correlation of PageRank skill and of raw win rate with true skill, after N sessions."""
    session_order = list(dict.fromkeys(r.session_id.rsplit("-t", 1)[0] for r in records))
    rows = []
    for count in checkpoints:
        allowed = set(session_order[:count])
        subset = [r for r in records if r.session_id.rsplit("-t", 1)[0] in allowed]
        rated = rate_players(subset, damping)
        win_rates = compute_win_rates(subset)
        truth = pd.Series(true_skill)
        rows.append({"sessions": count, "hands_per_player": float(win_rates["hands"].mean()), "pagerank_spearman": spearmanr(truth[rated.index], rated).statistic, "winrate_spearman": spearmanr(truth[win_rates.index], win_rates["bb_per_100"]).statistic})
    return pd.DataFrame(rows)


def run_seating_experiment(config: ProjectConfig, progress: Callable[[str], None]) -> ExperimentResult:
    exp = config.experiment
    rng = np.random.default_rng(exp.seed)
    population = build_population(config.population, rng)
    profiles = {p.player_id: p for p in population}
    player_ids = [p.player_id for p in population]
    true_skill = _true_skill_z(population)
    preflop = load_preflop_table(config.paths.cache, config.bots.preflop_equity_samples, exp.seed)
    damping, scale, seats = config.ratings.pagerank_damping, config.fairness.skill_std_scale, config.table.seats

    pool = ProcessPoolExecutor(max_workers=exp.workers) if exp.workers > 1 else None
    try:
        history: list[HandRecord] = []
        for session in range(exp.history_sessions):
            tables = seat_randomly(player_ids, true_skill, seats, rng)
            for records in _play_sessions(_make_jobs(tables, profiles, "history", HISTORY_PHASE, session, config, preflop), exp.workers, pool):
                history.extend(records)
        progress(f"history phase done: {len(history)} hands")

        evaluation: dict[str, list[HandRecord]] = {spec.name: [] for spec in POLICIES}
        table_rows: list[dict] = []
        seat_rngs = {spec.name: np.random.default_rng([exp.seed, index]) for index, spec in enumerate(POLICIES)}
        for session in range(exp.evaluation_sessions):
            jobs: list[SessionJob] = []
            for spec in POLICIES:
                estimated = rate_players(history + evaluation[spec.name], damping).to_dict()
                skill = true_skill if spec.skill_source == "true" else estimated
                tables = spec.seat(player_ids, skill, seats, seat_rngs[spec.name])
                for t, table in enumerate(tables):
                    table_rows.append({"policy": spec.name, "session": session, "table": t, "session_id": f"{spec.name}-s{session:03d}-t{t}", "fairness_true": score_table([true_skill[p] for p in table], scale).fairness, "fairness_estimated": score_table([estimated[p] for p in table], scale).fairness})
                jobs.extend(_make_jobs(tables, profiles, spec.name, EVALUATION_PHASE, session, config, preflop))
            results = _play_sessions(jobs, exp.workers, pool)
            for job, records in zip(jobs, results):
                evaluation[job.session_id.rsplit("-s", 1)[0]].extend(records)
            if (session + 1) % 10 == 0:
                progress(f"evaluation session {session + 1}/{exp.evaluation_sessions}")
    finally:
        if pool is not None:
            pool.shutdown()

    tables_frame = pd.DataFrame(table_rows)
    estimated_fairness = tables_frame.set_index("session_id")["fairness_estimated"].to_dict()
    evaluation[PENALTY_ARM] = [apply_fairness_penalty(r, estimated_fairness[r.session_id], config.fairness.penalty_rate) for r in evaluation["random"]]

    chronological = history + evaluation["random"]
    total_sessions = exp.history_sessions + exp.evaluation_sessions
    checkpoints = sorted({min(total_sessions, 2 ** k) for k in range(int(np.log2(total_sessions)) + 2)})
    accuracy = measure_rating_accuracy(chronological, true_skill, damping, checkpoints)

    population_frame = pd.DataFrame([{"player_id": p.player_id, "skill": p.skill, "skill_z": true_skill[p.player_id], "tier": p.tier} for p in population])
    return ExperimentResult(population=population_frame, history=history, evaluation=evaluation, tables=tables_frame, rating_accuracy=accuracy)


def summarize_tier_results(result: ExperimentResult) -> pd.DataFrame:
    """Mean bb/100 per skill tier under each policy, with a standard error across sessions."""
    tier_of = result.population.set_index("player_id")["tier"].to_dict()
    rows = []
    for policy, records in result.evaluation.items():
        per_session: dict[tuple[str, str], list[float]] = {}
        for record in records:
            session = record.session_id.rsplit("-t", 1)[0]
            for player, net in zip(record.players, record.net_bb):
                per_session.setdefault((tier_of[player], session), []).append(net)
        frame = pd.DataFrame([{"tier": tier, "session": s, "bb_per_100": 100 * float(np.mean(v))} for (tier, s), v in per_session.items()])
        for tier, group in frame.groupby("tier"):
            rows.append({"policy": policy, "tier": tier, "bb_per_100": group["bb_per_100"].mean(), "se": group["bb_per_100"].std(ddof=1) / np.sqrt(len(group))})
    return pd.DataFrame(rows)
