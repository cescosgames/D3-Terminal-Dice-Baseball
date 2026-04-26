# D3 Baseball

Terminal dice baseball game built for Raspberry Pi Zero. Single Python file, zero
external dependencies, plain `print`/`input` only.

## Run it

```bash
python3 baseball_dice.py
```

Transfer to Pi:
```bash
scp baseball_dice.py pi@<ip>:~/
ssh pi@<ip> python3 baseball_dice.py
```

## Core constraints (never break these)

- Single file: `baseball_dice.py`
- Stdlib only: `random`, `os`, `sys` — no pip installs
- Python 3.7+ compatible (Pi Zero may run older Raspbian) — no walrus operator,
  no `match/case`, no `dict | dict` merging
- 80-column max display width
- No curses — plain `print` + `input` only
- ANSI color degrades gracefully when piped (`USE_ANSI` check at startup)
- `KeyboardInterrupt` must propagate to `main()` — do NOT catch it in inner functions

## Game mechanics

### Dice allocation
Player and CPU each assign 9 dice (all D3 = randint 1–3) across 4 slots:

| Slot          | Role                              |
|---------------|-----------------------------------|
| Hit vs SP     | Attack against opponent's starter |
| Hit vs RP     | Attack against opponent's bullpen |
| SP Prevention | Your starter defending            |
| RP Prevention | Your bullpen defending            |

No minimums or maximums per slot — must sum to 9.

### Scoring formula
```
player_runs = max(0, HvSP - cpu_SPprev) + max(0, HvRP - cpu_RPprev)
cpu_runs    = max(0, cpu_HvSP - player_SPprev) + max(0, cpu_HvRP - player_RPprev)
```
Each phase is floored at 0 independently. Ties trigger a sudden-death D3 tiebreaker
(re-rolls until different).

### CPU archetypes
CPU picks a style each game (not revealed) and allocates dice with jitter:
- Balanced, Offense Heavy, Pitching Wall, SP Stack, RP Gamble

## Division / season structure

5 NL West teams: `LA`, `SF`, `COL`, `SD`, `AZ`

Player picks their team at season start. Each of 5 games:
1. Player plays an accurate game vs a random opponent
2. 1 simulated game runs among the other 3 teams (1 gets a bye)
3. Division standings update and display after every game

Standings sort: W desc, then run differential desc. Games behind uses standard
formula `((leader_W - team_W) + (team_L - leader_L)) / 2`. Your team marked `*`.

## Flavor systems

### Game conditions (generated once per game, shown in every header)
- Time of day: Day game / Twilight game / Night game
- Weather: 8 options each with correlated temp range (Sunny=78-97°F, Light rain=48-66°F, etc.)

### Box score (replaces raw math display)
- SP runs (phases 1) distributed randomly across innings 1–6
- RP runs (phase 2) distributed randomly across innings 7–9
- Hits: `runs * uniform(1.0, 2.0)` when runs > 0; scoreless = 1–6 hits (97%) or
  no-hitter (3%)
- Errors: 0 (88%), 1 (10%), 1–3 (2%)

## Screen flow

```
Start screen (title art + diamond)
  → Pick team (1-5)
    → For each of 5 games:
        Allocation screen  →  Reveal screen  →  Rolls screen  →  Box score screen
        [tie: tiebreaker screen]
        → Division standings screen (other results + full table)
  → Season summary (final standings + player stats + flavor line)
  → Play again? (y/n)
```

## Key functions

| Function | Purpose |
|---|---|
| `player_allocate()` | Prompts and validates dice allocation |
| `cpu_allocate()` | Picks archetype, applies jitter, distributes 9 dice |
| `compute_score()` | Runs the scoring formula |
| `_spread_runs(runs, n)` | Distributes runs randomly across n innings |
| `show_boxscore()` | 9-inning grid + R/H/E + win/loss result |
| `show_standings()` | Sorted division table with GB |
| `simulate_game()` | Random runs for CPU vs CPU games (no ties) |
| `play_game()` | Full single-game loop |
| `play_season()` | 5-game loop with division simulation |
| `gen_conditions()` | Time of day + weather + temp string |

## Ideas for future expansion

- Named ballparks per team with home/away flavor
- Player career stats saved across sessions (simple text file)
- Pinch hitter / bullpen decisions as mid-game choices
- Trade deadline event between games 3 and 4
- Playoff mode if you finish top of division
- Expanded roster flavor (starting pitcher names, walk-up music, etc.)
- Weather affecting gameplay (e.g. wind boosts Hit vs RP rolls slightly)
- Difficulty setting (CPU archetype jitter range — easy = more random, hard = more optimal)
