# Results

**Bottom line:** seating players by Fairness Score cut weak bots' losses by **85%** compared with random seating (−311 → −46 bb/100). The ratings behind it were learned only from play history. On the real Pluribus data, PageRank ratings were far more stable than raw win rate, but the data is too small to prove the seating effect by itself.

All numbers come from `python main.py all` with [config/default.toml](../config/default.toml) (seed 427). The run is deterministic, so the numbers reproduce exactly. Source files are in `var/reports/`.

## Real data: 10,000 Pluribus hands

| Measure | Value |
| --- | --- |
| Hands / players / sessions | 10,000 / 14 / 92 |
| Co-play edges | 65 of 91 possible pairs |
| Split-half stability, PageRank skill | **0.34** |
| Split-half stability, raw win rate | **0.02** |
| Table fairness range across sessions | 31.7 – 54.4 (mean 43.7) |
| Held-out fairness vs weakest player's loss | Spearman −0.08, p = 0.42 (no detectable link) |

**What it means:**

- **Win rate over a few thousand hands is almost pure luck.** Rating players on odd sessions and on even sessions gives two win-rate rankings that do not agree at all (0.02). PageRank rankings agree much better (0.34), because they also use *who* you beat.
- **Pluribus shows the gap.** It finished at −7.1 bb/100 in raw results, below 8 of the 13 humans. But the original study, which used variance reduction, found Pluribus beat the pros. PageRank puts it above average (+0.29 z), because it took money from strong players.
- **Tiers:** sharks = MrBlue, Eddie, Budd. Fish = MrWhite, Joe, MrBlonde, Gogo. Gogo's −57 bb/100 comes from only 488 hands, so centrality matters here: Gogo faced the fewest opponents (5), and that rating is the least trustworthy.
- **Player pools (Louvain):** a core of 8 players around Pluribus, plus two smaller groups ({Budd, Gogo, Hattori, ORen} and {MrBlonde, MrWhite}) who mostly sat with each other. On a real site, pools like these show where a seating change would actually move people.
- **Why the held-out test finds nothing:** Pluribus sits at every table, so table fairness only varies between 32 and 54. And each session is only about 100 hands, where luck dominates. The bot experiment exists to answer this question with enough data.

Charts: `dataset_coplay_network.png`, `dataset_money_flow.png`, `dataset_skill_vs_winrate.png`.

## Bot experiment: random vs fairness-based seating

36 bots (9 sharks, 14 regulars, 13 fish). 7,200 history hands, then 14,400 evaluation hands per policy.

**Win rate by true skill tier (bb/100, ± standard error across sessions):**

| Policy | Sharks | Regulars | Fish | Fish loss cut |
| --- | --- | --- | --- | --- |
| Random seating | +213 ± 17 | +151 ± 18 | −311 ± 19 | — |
| **Fairness seating (PageRank)** | +52 ± 9 | +9 ± 10 | **−46 ± 10** | **85%** |
| Fairness seating (oracle) | +12 ± 6 | +9 ± 7 | −18 ± 7 | 94% |
| Random + unfair-table penalty | +180 ± 14 | +128 ± 15 | −262 ± 16 | 16% |

**Mean table Fairness Score (scored with true skill):** random 41, PageRank seating 68, oracle 84.

**Rating accuracy (Spearman correlation with true skill):**

| Hands per bot | 60 | 240 | 960 | 1,920 | 3,600 |
| --- | --- | --- | --- | --- | --- |
| PageRank | 0.24 | 0.30 | 0.63 | 0.87 | **0.88** |
| Raw win rate | 0.28 | 0.48 | 0.65 | 0.83 | 0.83 |

**What it means:**

- **Seating does almost all the work.** Using only estimated skill, it gets 90% of the way from random seating to the perfect-knowledge oracle.
- **The penalty alone is weak.** At a 25% rate it only returns a slice of each pot. It works better as a deterrent for picking fish tables than as protection for fish.
- **PageRank needs volume.** Below about 1,000 hands per player, raw win rate ranks bots slightly better. Above that, PageRank overtakes it. A site would mix the two, or require a minimum number of hands before seating by rating.
- **The site trades shark profit for fish retention.** Sharks' edge falls from +213 to +52 bb/100. That is the game-theory cost in section 7 of the methodology.
- **The ratings are overconfident.** Under PageRank seating, the site *thinks* its tables score 81 on average, but true fairness is 68. Mis-rated players get sorted into the wrong table. That gap is the room left for better ratings.

Charts: `experiment_tier_results.png`, `experiment_table_fairness.png`, `experiment_rating_accuracy.png`.
