"""Command-line entry point.

    python main.py analyze     # real PHH data: graphs, PageRank, tiers, table fairness
    python main.py simulate    # bot experiment: random vs fairness-based seating
    python main.py all         # both

Results go to var/reports (CSV / JSON) and var/figures (PNG). Settings: config/default.toml.
"""
import argparse
import sys
import time
from pathlib import Path

from fairpoker.config import DEFAULT_CONFIG_PATH, create_output_dirs, load_config
from fairpoker.pipelines.dataset_analysis import run_dataset_analysis
from fairpoker.pipelines.seating_experiment import run_seating_experiment
from fairpoker.reporting.reports import format_summary, write_dataset_report, write_experiment_report

COMMANDS = ("analyze", "simulate", "all")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Finding fair poker tables with network analysis")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    create_output_dirs(config.paths)
    if args.command in ("analyze", "all"):
        log("analyzing PHH dataset")
        log(format_summary(write_dataset_report(run_dataset_analysis(config), config.paths)))
    if args.command in ("simulate", "all"):
        log("running seating experiment")
        log(format_summary(write_experiment_report(run_seating_experiment(config, log), config.paths)))
    log(f"reports in {config.paths.reports}, figures in {config.paths.figures}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
