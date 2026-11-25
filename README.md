# 427-group-project
How Do I Get Rinsed Less? Finding Fair Poker Tables with Network Analysis

**Problem:** in online poker, recreational players lose a lot of money just because of who they sit with. A player cannot tell whether a table is "fair".

**Solution:** rate every player with PageRank on a who-won-money-from-whom graph, then give each table a **Fairness Score** (0–100) based on the skill spread of the people at it. Players can avoid unfair tables, and the site can seat players by skill.

**Result:** in a simulation with 36 bots of known skill, seating by Fairness Score cut weak players' losses by **85%** compared with random seating, using only ratings learned from play history. Details: [docs/results.md](docs/results.md).

**Group members, start with [docs/project-guide.md](docs/project-guide.md):** what to fill in, where every file lives, a slide-by-slide map, and the full analysis and results.

## Quick start

```powershell
pip install -e ".[dev]"
python main.py all        # real-data analysis + bot experiment, about 2 minutes
python -m pytest          # unit tests
```

- `python main.py analyze` runs only the real PHH data (about 10 s).
- `python main.py simulate` runs only the bot experiment (about 75 s on 12 worker processes).
- Outputs: CSV / JSON in `var/reports/`, PNG charts in `var/figures/`. Both are gitignored and rebuilt on every run.
- All settings (paths, bot traits, population, session counts) live in [config/default.toml](config/default.toml).

## How it works

1. **Load** the Pluribus hands from `poker-hand-histories.zip` with pokerkit.
2. **Build two graphs:** who shared a table (co-play), and who lost money to whom (money flow).
3. **Rate skill** with PageRank on the money-flow graph. Centrality (opponents faced, hands played) shows how far to trust each rating.
4. **Cluster** players into shark / regular / fish tiers, and find pools of players who sit together.
5. **Score tables:** Fairness = 100 × exp(−skill spread at the table).
6. **Evaluate** with bots of known skill: random seating vs fairness-based seating vs an unfair-table penalty.

Full explanation: [docs/methodology.md](docs/methodology.md).

## Project layout

```text
config/default.toml        every tunable value
main.py                    command-line entry point (thin)
src/fairpoker/
  config.py                typed config loading and validation
  hands/                   HandRecord + PHH zip loader (pokerkit)
  network/                 graphs, PageRank ratings, centrality, tiers / communities
  fairness/                Fairness Score, seating policies, unfair-table penalty
  simulation/              fast hold'em engine, hand evaluator, equity, skill bots
  pipelines/               real-data analysis and seating experiment workflows
  reporting/               CSV / JSON reports and PNG figures
tests/unit/                evaluator vs pokerkit, engine chip conservation, graphs, fairness
docs/                      project guide, methodology, results, chart images
var/                       generated output (gitignored)
```
