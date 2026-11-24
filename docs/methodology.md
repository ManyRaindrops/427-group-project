# Methodology

How each piece works, and why we built it that way. For the numbers, see [results.md](results.md).

## 1. Data

- **Source:** the University of Toronto PHH dataset ([Zenodo 10796886](https://zenodo.org/records/10796886)), stored in the repo as `poker-hand-histories.zip`.
- **What we use:** `data/pluribus/`. That is 10,000 six-player no-limit hold'em hands from the 2019 Pluribus experiment. Each hand has 5 human pros and the Pluribus AI.
- **Loading:** `hands/phh_loader.py` reads each `.phh` file straight from the zip with pokerkit's `HandHistory`. It keeps the players and each player's net result in big blinds (finishing stack minus starting stack).
- **Sessions:** the folder name (`100`, `100b`, ...) is the session id. One session = one table lineup. There are 92 sessions.
- **Limit:** only 14 distinct players, and Pluribus plays every hand. So the real data can show the method, but it is too small to prove that seating works. The bot experiment (section 5) does that.

## 2. The two graphs (`network/graphs.py`)

| Graph | Nodes | Edge | Weight |
| --- | --- | --- | --- |
| Co-play | players | undirected: sat at the same table | hands shared |
| Money flow | players | directed: loser → winner | big blinds moved, netted per pair |

**Building money flow:** in each hand, each loser's chips are split between that hand's winners, in proportion to how much each winner won. Then flows in both directions between two players cancel out, so at most one edge joins any pair.

## 3. Skill rating: PageRank on money flow (`network/ratings.py`)

**Idea:** money flows toward skill. PageRank collects "rank" at the nodes that money flows into. Beating a strong player is worth more than beating someone who loses to everyone. Raw win rate cannot tell those two cases apart.

**Fix we needed: retention loops.** Plain PageRank makes a node pass on *all* of its rank through its out-edges, no matter how small its losses are. A big winner who lost 5 bb to one player would hand that player nearly all of its rank. So each player also gets a self-loop worth the money they won. Now a player passes on rank only in proportion to `losses / (losses + wins)`.

We tested this on simulated bots with known skill (Spearman correlation with true skill):

| Hands per bot | Plain PageRank | With retention loops | Raw win rate |
| --- | --- | --- | --- |
| 480 | −0.06 | 0.49 | 0.66 |
| 960 | 0.32 | 0.63 | 0.65 |
| 1,920 | 0.65 | 0.80 | 0.77 |

**Skill score:** `skill_z` is the z-scored log of PageRank. That puts skill on a common scale, so the Fairness Score means the same thing on any dataset.

**Centrality = exposure:** degree centrality (how many different opponents a player faced) and hands played tell us how much to trust a rating. A player who faced few opponents over few hands has a rating that is mostly luck.

## 4. Clustering (`network/tiers.py`)

- **Skill tiers:** 1-D k-means (k = 3) on `skill_z`. Top tier = shark, bottom tier = fish, the rest = regular.
- **Player pools:** Louvain community detection on the co-play graph finds groups of players who mostly sat together.

## 5. Fairness Score (`fairness/score.py`)

```
Fairness = 100 × exp(−σ / scale)
```

- `σ` is the standard deviation of the seated players' `skill_z`. `scale` is set in config (default 1.0).
- 100 means everyone at the table is equally skilled. A table as spread out as the whole player pool scores about 37.
- **Why σ:** a player's expected loss grows with how far they sit below the table's average skill. Across the whole table, those gaps add up to the spread of skill.

## 6. Two ways to act on it

- **Fairness-based seating** (`fairness/seating.py`): sort players by estimated skill and fill tables in order. With tables of equal size, this split gives the lowest possible total skill variance inside tables.
- **Unfair-table penalty** (`fairness/penalty.py`): on each hand, winners give back `rate × (1 − Fairness/100)` of their profit, split among that hand's losers. Total chips do not change, and a perfectly fair table pays nothing.

## 7. Game theory view

- **Players:** sharks earn most at tables with fish, so they want unfair tables. Fish want fair tables but cannot see skill. That information gap is why the site has to act.
- **The site's choice:** fish who lose fast quit, and the player pool shrinks. Skill-based seating is a mechanism-design choice. It gives up some shark profit now so recreational players stay longer.
- **The penalty** changes payoffs instead of seating. It makes picking a fish table less profitable without forcing anyone's seat.

## 8. Evaluation: bots with known skill (`simulation/`, `pipelines/seating_experiment.py`)

**Engine:** a compact 6-max no-limit hold'em engine with blinds 50/100 and a 100 bb stack at the start of every hand, matching the Pluribus format. It handles side pots and showdowns. Its hand evaluator is checked against pokerkit's on 3,000 random showdowns (`tests/unit/test_cards.py`). It is about 35× faster than pokerkit, which the equity sampling needs.

**Bots:** one skill number `s` in [0, 1] controls behavior. Skill never decides who wins a hand. It only changes how well a bot plays:

| Trait | Low skill | High skill |
| --- | --- | --- |
| Equity noise | misjudges hand strength | judges it accurately |
| Looseness | calls with worse odds than the pot gives | respects pot odds |
| Hand reading | ignores bet size | folds marginal hands to big bets |
| Aggression | passive, rarely raises | value-raises, bluffs a little |

**Population:** 36 bots. 25% sharks (s 0.85–1.0), 40% regulars (0.45–0.65), 35% fish (0–0.2).

**Protocol:**
1. **History:** 20 sessions × 60 hands with random seating. Nobody knows anyone's skill.
2. **Rating:** PageRank on the money-flow graph of that history.
3. **Evaluation:** 40 more sessions under each policy, with ratings refreshed after every session:
   - `random`: today's default
   - `fairness (PageRank)`: our method, using estimated skill only
   - `fairness (oracle)`: seated by true skill, as an upper bound
   - `random + penalty`: random seating plus the unfair-table penalty
4. **Common random numbers:** table *t* of session *k* uses the same deck seed under every policy. So the policies differ by seating, not by card luck.

**Metric:** mean win rate (bb/100) for each true-skill tier, with standard errors across sessions.

## Known limits

- The bot skill gaps are large on purpose, so the signal is clear. Real fish lose closer to 10–100 bb/100, not 300.
- The engine lets every raise reopen betting. Real rules do not reopen on a short all-in.
- On real data, Pluribus sits at every table. So fairness differences between sessions are small, and a held-out test of fairness against losses is underpowered (see results).
