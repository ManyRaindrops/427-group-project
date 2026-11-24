"""Typed project configuration, loaded once from config/default.toml."""
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.toml"


@dataclass(frozen=True, slots=True)
class OutputPaths:
    dataset_zip: Path
    cache: Path
    reports: Path
    figures: Path


@dataclass(frozen=True, slots=True)
class RatingConfig:
    pagerank_damping: float
    tier_count: int


@dataclass(frozen=True, slots=True)
class FairnessConfig:
    skill_std_scale: float
    penalty_rate: float


@dataclass(frozen=True, slots=True)
class TableConfig:
    seats: int
    small_blind: int
    big_blind: int
    starting_stack: int


@dataclass(frozen=True, slots=True)
class BotConfig:
    equity_noise_max: float
    call_looseness_max: float
    hand_reading_max: float
    raise_margin: float
    passive_raise_floor: float
    bluff_rate_max: float
    bet_pot_fraction: float
    postflop_equity_samples: int
    preflop_equity_samples: int


@dataclass(frozen=True, slots=True)
class SkillTier:
    name: str
    share: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class PopulationConfig:
    player_count: int
    tiers: tuple[SkillTier, ...]


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    seed: int
    hands_per_session: int
    history_sessions: int
    evaluation_sessions: int
    workers: int


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    paths: OutputPaths
    hands_prefix: str
    ratings: RatingConfig
    fairness: FairnessConfig
    table: TableConfig
    bots: BotConfig
    population: PopulationConfig
    experiment: ExperimentConfig


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> ProjectConfig:
    """Parse and validate the TOML config. Raises ValueError naming the bad field."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    paths = OutputPaths(**{key: PROJECT_ROOT / value for key, value in raw["paths"].items()})
    tiers = tuple(SkillTier(**tier) for tier in raw["population"]["tiers"])
    population = PopulationConfig(player_count=raw["population"]["player_count"], tiers=tiers)
    config = ProjectConfig(paths=paths, hands_prefix=raw["dataset"]["hands_prefix"], ratings=RatingConfig(**raw["ratings"]), fairness=FairnessConfig(**raw["fairness"]), table=TableConfig(**raw["table"]), bots=BotConfig(**raw["bots"]), population=population, experiment=ExperimentConfig(**raw["experiment"]))
    validate_config(config, path)
    return config


def validate_config(config: ProjectConfig, source: Path) -> None:
    """Fail at startup on values that would silently break the pipeline."""
    share_total = sum(tier.share for tier in config.population.tiers)
    if abs(share_total - 1.0) > 1e-9:
        raise ValueError(f"{source}: population.tiers shares sum to {share_total}, expected 1.0")
    if config.population.player_count % config.table.seats != 0:
        raise ValueError(f"{source}: population.player_count must be a multiple of table.seats")
    if not config.paths.dataset_zip.is_file():
        raise ValueError(f"{source}: paths.dataset_zip not found at {config.paths.dataset_zip}")


def create_output_dirs(paths: OutputPaths) -> None:
    """The one place that creates generated-output folders."""
    for directory in (paths.cache, paths.reports, paths.figures):
        directory.mkdir(parents=True, exist_ok=True)
