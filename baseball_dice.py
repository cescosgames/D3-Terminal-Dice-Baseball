#!/usr/bin/env python3
"""D3 Baseball — terminal dice baseball game for Raspberry Pi Zero."""

import os
import random
import sys

# ---------------------------------------------------------------------------
# ANSI helpers — degrade gracefully when piped or terminal has no color
# ---------------------------------------------------------------------------

try:
    _USE_ANSI = os.isatty(sys.stdout.fileno())
except Exception:
    _USE_ANSI = False


# Build an ANSI escape sequence, or empty string if color is disabled.
def _esc(code):
    return f'\033[{code}m' if _USE_ANSI else ''


BOLD  = _esc('1')
DIM   = _esc('2')
GREEN = _esc('32')
RED   = _esc('31')
CYAN  = _esc('36')
RST   = _esc('0')


# Wrap a string in the matching ANSI color/style.
def bold(s):  return f'{BOLD}{s}{RST}'
def green(s): return f'{GREEN}{s}{RST}'
def red(s):   return f'{RED}{s}{RST}'
def cyan(s):  return f'{CYAN}{s}{RST}'
def dim(s):   return f'{DIM}{s}{RST}'


# Clear the terminal (no-op when piped).
def clear():
    if _USE_ANSI:
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()


# Print a full-width horizontal rule.
def hr():
    print(dim('-' * 80))


# Block until the user presses ENTER; tolerates piped input gracefully.
def pause(msg='Press ENTER to continue...'):
    try:
        input(dim(f'\n  {msg}'))
    except EOFError:
        print()


# ---------------------------------------------------------------------------
# Game constants
# ---------------------------------------------------------------------------

SLOTS = ['Hit vs SP', 'Hit vs RP', 'SP Prevention', 'RP Prevention']
TOTAL_DICE = 9
SEASON_GAMES = 5
TEAMS = ['LA', 'SF', 'COL', 'SD', 'AZ']

# Weather options: (label, temp_lo, temp_hi)
_WEATHER = [
    ('Sunny',         78, 97),
    ('Hot and humid', 84, 99),
    ('Partly cloudy', 66, 84),
    ('Overcast',      55, 72),
    ('Windy',         52, 74),
    ('Light rain',    48, 66),
    ('Foggy',         45, 63),
    ('Cold and clear',34, 54),
]

_TIME_OF_DAY = ['Day game', 'Twilight game', 'Night game']


# Pick a random time of day, weather type, and temperature for the game.
def gen_conditions():
    time  = random.choice(_TIME_OF_DAY)
    label, lo, hi = random.choice(_WEATHER)
    temp  = random.randint(lo, hi)
    return f'{time}  ·  {label}  ·  {temp}°F'


# Prompt the player to choose one of the five NL West teams.
def pick_player_team():
    clear()
    hr()
    print(bold(cyan('\n  CHOOSE YOUR TEAM\n')))
    hr()
    for i, team in enumerate(TEAMS, 1):
        print(f'  {i}.  {team}')
    hr()
    while True:
        try:
            raw = input(f'\n  Enter 1-{len(TEAMS)}: ').strip()
            idx = int(raw) - 1
            if 0 <= idx < len(TEAMS):
                return TEAMS[idx]
            print(red(f'  Enter a number between 1 and {len(TEAMS)}.\n'))
        except (ValueError, EOFError):
            print(red('  Enter a number.\n'))


# CPU archetype base weights: [HvSP, HvRP, SPprev, RPprev]
_ARCHETYPES = {
    'Balanced':      [2, 2, 2, 2],
    'Offense Heavy': [4, 3, 1, 1],
    'Pitching Wall': [1, 1, 4, 3],
    'SP Stack':      [4, 1, 3, 1],
    'RP Gamble':     [1, 4, 1, 3],
}

# ---------------------------------------------------------------------------
# CPU allocation
# ---------------------------------------------------------------------------

# Distribute exactly 9 dice proportional to a list of 4 weights, no rounding loss.
def _distribute_9(weights):
    """Distribute exactly 9 dice proportional to a list of 4 weights."""
    total = sum(weights)
    counts = [int(9 * w / total) for w in weights]
    remainder = 9 - sum(counts)
    # Give leftover dice to slots with the largest fractional parts
    fracs = sorted(
        range(4),
        key=lambda i: (9 * weights[i] / total - counts[i]),
        reverse=True
    )
    for i in range(remainder):
        counts[fracs[i]] += 1
    return counts


# Pick a random CPU archetype and allocate its 9 dice with slight jitter.
def cpu_allocate():
    style = random.choice(list(_ARCHETYPES.keys()))
    base = _ARCHETYPES[style]
    # Jitter so the same archetype isn't always identical
    weights = [max(0.1, b + random.uniform(-0.5, 0.5)) for b in base]
    return _distribute_9(weights), style


# ---------------------------------------------------------------------------
# Player allocation
# ---------------------------------------------------------------------------

# Interactively prompt the player to assign 9 dice across the 4 slots.
def player_allocate():
    print(bold(f'\n  Allocate your {TOTAL_DICE} dice across 4 slots (must sum to {TOTAL_DICE}):'))
    while True:
        try:
            vals = []
            for slot in SLOTS:
                raw = input(f'    {slot:<16}: ')
                vals.append(int(raw.strip()))
        except ValueError:
            print(red('  Invalid input — enter whole numbers only.\n'))
            continue
        except EOFError:
            print()
            return [2, 2, 3, 2]

        if any(v < 0 for v in vals):
            print(red('  No negative values allowed.\n'))
            continue
        if sum(vals) != TOTAL_DICE:
            print(red(f'  Dice sum to {sum(vals)}, must equal {TOTAL_DICE}. Try again.\n'))
            continue
        return vals


# ---------------------------------------------------------------------------
# Dice rolling
# ---------------------------------------------------------------------------

# Roll n D3 dice and return the individual rolls and their sum.
def roll_slot(n):
    """Roll n D3 dice. Returns (rolls_list, total)."""
    if n == 0:
        return [], 0
    rolls = [random.randint(1, 3) for _ in range(n)]
    return rolls, sum(rolls)


# Roll all four slots for both the player and CPU.
def roll_all(p_alloc, c_alloc):
    return (
        [roll_slot(n) for n in p_alloc],
        [roll_slot(n) for n in c_alloc],
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# Apply the scoring formula: hits minus opponent's prevention, floored at 0 per phase.
def compute_score(p_rolls, c_rolls):
    p_hvsp,  p_hvrp  = p_rolls[0][1], p_rolls[1][1]
    p_spprev, p_rpprev = p_rolls[2][1], p_rolls[3][1]
    c_hvsp,  c_hvrp  = c_rolls[0][1], c_rolls[1][1]
    c_spprev, c_rpprev = c_rolls[2][1], c_rolls[3][1]

    p_runs = max(0, p_hvsp - c_spprev) + max(0, p_hvrp - c_rpprev)
    c_runs = max(0, c_hvsp - p_spprev) + max(0, c_hvrp - p_rpprev)
    return p_runs, c_runs


# Generate a plausible hit total from a run total.
def gen_hits(runs):
    if runs == 0:
        # No-hitters are rare (~3%); usually strand 1-6 runners
        return 0 if random.random() < 0.03 else random.randint(1, 6)
    return int(runs * random.uniform(1.0, 2.0))


# Generate a random error count weighted heavily toward zero.
def gen_errors():
    r = random.random()
    if r < 0.88:
        return 0
    elif r < 0.98:
        return 1
    return random.randint(1, 3)


# Randomly scatter runs across innings for a realistic-looking box score line.
def _spread_runs(runs, num_innings):
    """Randomly distribute runs across num_innings innings."""
    innings = [0] * num_innings
    for _ in range(runs):
        innings[random.randint(0, num_innings - 1)] += 1
    return innings


# Generate a quick CPU vs CPU result for the other division game (no ties allowed).
def simulate_game():
    """Random runs for a CPU vs CPU game. Re-rolls on tie."""
    r1 = random.randint(0, 10)
    r2 = random.randint(0, 10)
    while r1 == r2:
        r2 = random.randint(0, 10)
    return r1, r2


# ---------------------------------------------------------------------------
# Start screen art
# ---------------------------------------------------------------------------

_TITLE_ART = r"""
  ____   _____     ____    _    ____  _____ ____    _    _     _
 |  _ \ |___ /    | __ )  / \  / ___|| ____| __ )  / \  | |   | |
 | | | |  |_ \    | |_) |/ _ \ \___ \|  _| |  _ \ / _ \ | |   | |
 | |_| | ___) |   |  _ </ ___ \ ___) | |___| |_) / ___ \| |___| |___
 |____/ |____/    |_| \_/_/   \_\____/|_____|____/_/   \_\_____|_____|
"""

_DIAMOND_ART = r"""
                                       2B
                                      /  \
                                     /    \
                                   3B      1B
                                     \    /
                                      \  /
                                       HP
"""


# Display the title art and diamond, then wait for the player to start.
def show_start_screen():
    clear()
    hr()
    print(bold(cyan(_TITLE_ART)))
    print(dim(_DIAMOND_ART))
    print(dim('                     5-game season  |  9 dice  |  D3 only'))
    print()
    hr()
    pause('Press ENTER to play ...')


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

# Print the persistent top bar showing game number, matchup, record, and conditions.
def show_header(game_num, record, player_team='', opponent='', conditions=''):
    clear()
    hr()
    w, l = record
    if player_team and opponent:
        print(bold(cyan(
            f'  D3 BASEBALL  |  Game {game_num}  |  {player_team} vs {opponent}  |  {w}W-{l}L'
        )))
    else:
        print(bold(cyan(f'  D3 BASEBALL  |  Game {game_num} of {SEASON_GAMES}  |  {w}W-{l}L')))
    if conditions:
        print(dim(f'  {conditions}'))
    hr()


# Show the dice allocations for both sides side by side.
def show_reveal(p_alloc, c_alloc, p_label='You', c_label='CPU'):
    print(bold('\n  LINEUP CARD'))
    hr()
    print(f'  {"Slot":<16}  {p_label:>6}  {c_label:>6}')
    hr()
    for i, slot in enumerate(SLOTS):
        print(f'  {slot:<16}  {p_alloc[i]:>6}  {c_alloc[i]:>6}')
    hr()


# Display each slot's dice count and resulting roll total for both sides.
def show_rolls(p_alloc, c_alloc, p_rolls, c_rolls, p_label='You', c_label='CPU'):
    print(bold('\n  ROLLS'))
    hr()
    print(f'  {"Slot":<16}  {p_label:>10}  {c_label:>10}')
    hr()
    for i, slot in enumerate(SLOTS):
        _, pt = p_rolls[i]
        _, ct = c_rolls[i]
        pd, cd = p_alloc[i], c_alloc[i]
        p_str = f'{pd}d -> {pt:2}' if pd else ' 0d ->  0'
        c_str = f'{cd}d -> {ct:2}' if cd else ' 0d ->  0'
        print(f'  {slot:<16}  {p_str:>10}  {c_str:>10}')
    hr()


# Render the 9-inning grid with R/H/E totals and the win/loss result line.
def show_boxscore(p_sp, p_rp, c_sp, c_rp, p_runs, c_runs,
                  p_hits, c_hits, p_err, c_err, p_label='You', c_label='CPU'):
    # SP runs land in innings 1-6, RP runs in innings 7-9
    p_innings = _spread_runs(p_sp, 6) + _spread_runs(p_rp, 3)
    c_innings = _spread_runs(c_sp, 6) + _spread_runs(c_rp, 3)

    print(bold('\n  FINAL'))
    hr()
    inning_hdr = ''.join(f'{i:>3}' for i in range(1, 10))
    print(f'  {"":6}{inning_hdr}    {"R":>3}  {"H":>3}  {"E":>3}')
    hr()
    p_row = ''.join(f'{n:>3}' for n in p_innings)
    c_row = ''.join(f'{n:>3}' for n in c_innings)
    print(f'  {p_label:<6}{p_row}    {p_runs:>3}  {p_hits:>3}  {p_err:>3}')
    print(f'  {c_label:<6}{c_row}    {c_runs:>3}  {c_hits:>3}  {c_err:>3}')
    hr()

    if p_runs > c_runs:
        print(bold(green(f'\n  {p_label} WINS  {p_runs}-{c_runs}')))
    elif c_runs > p_runs:
        print(bold(red(f'\n  {c_label} WINS  {c_runs}-{p_runs}')))
    else:
        print(bold(cyan(f'\n  TIE GAME  {p_runs}-{c_runs}')))
    print()
    hr()


# ---------------------------------------------------------------------------
# Tiebreaker
# ---------------------------------------------------------------------------

# Roll one D3 per side, re-rolling until there's a winner.
def run_tiebreaker():
    """Roll 1D3 each side until different. Returns ('player'|'cpu', p_roll, c_roll)."""
    while True:
        p = random.randint(1, 3)
        c = random.randint(1, 3)
        if p != c:
            winner = 'player' if p > c else 'cpu'
            return winner, p, c


# Display the tiebreaker rolls and declare the winner.
def show_tiebreaker(game_num, record, p_roll, c_roll, winner,
                    player_team='', opponent='', conditions='',
                    p_label='You', c_label='CPU'):
    show_header(game_num, record, player_team, opponent, conditions)
    print(bold('\n  TIEBREAKER  —  sudden death D3 roll\n'))
    hr()
    print(f'  {p_label}:  {bold(str(p_roll))}')
    print(f'  {c_label}:  {bold(str(c_roll))}')
    hr()
    if winner == 'player':
        print(bold(green(f'\n  {p_label} WINS THE TIEBREAKER')))
    else:
        print(bold(red(f'\n  {c_label} WINS THE TIEBREAKER')))
    print()
    hr()


_FLAVOR = [
    (5, 'Undefeated. A legendary season.'),
    (4, 'Division champs! Strong finish.'),
    (3, 'Made the playoffs on the final day.'),
    (2, 'Just missed the cut. Close but no cigar.'),
    (1, 'Rough season. The rebuilding begins.'),
    (0, 'Last place. Historic collapse.'),
]


# Show final standings, player stats, and a flavor line based on win total.
def show_season_summary(record, p_total, c_total, standings, player_team):
    clear()
    hr()
    print(bold(cyan('\n  SEASON COMPLETE\n')))
    hr()
    show_standings(standings, player_team)
    w, l = record
    diff = p_total - c_total
    sign = '+' if diff >= 0 else ''
    print(bold(f'\n  Your season  ({player_team}):'))
    hr()
    print(f'  Record:         {bold(str(w))}W - {bold(str(l))}L')
    print(f'  Runs scored:    {bold(str(p_total))}')
    print(f'  Runs allowed:   {bold(str(c_total))}')
    print(f'  Run diff:       {bold(sign + str(diff))}')

    for wins_needed, msg in _FLAVOR:
        if w >= wins_needed:
            print(f'\n  {cyan(msg)}\n')
            break

    hr()
    print()


# Print the simulated game score and the team on bye for this round.
def show_other_results(sim_t1, sim_r1, sim_t2, sim_r2, bye_team):
    print(bold('\n  OTHER RESULTS'))
    hr()
    print(f'  {sim_t1}  {sim_r1}  —  {sim_r2}  {sim_t2}')
    print(dim(f'  {bye_team}  (bye)'))
    hr()


# Render the division table sorted by wins then run differential, with GB column.
def show_standings(standings, player_team):
    sorted_teams = sorted(
        TEAMS,
        key=lambda t: (-standings[t]['w'], -(standings[t]['rs'] - standings[t]['ra']))
    )
    leader = sorted_teams[0]
    lw = standings[leader]['w']
    ll = standings[leader]['l']

    print(bold('\n  DIVISION STANDINGS'))
    hr()
    print(f'  {"":3}  {"TEAM":<5}  {"W":>3}  {"L":>3}  {"GB":>5}  {"RS":>4}  {"RA":>4}')
    hr()
    for team in sorted_teams:
        s = standings[team]
        w, l = s['w'], s['l']
        if team == leader:
            gb_str = ' --'
        else:
            gb = ((lw - w) + (l - ll)) / 2
            gb_str = f'{gb:.1f}'
        marker = bold(cyan('*')) if team == player_team else ' '
        print(f'  {marker}  {team:<5}  {w:>3}  {l:>3}  {gb_str:>5}  {s["rs"]:>4}  {s["ra"]:>4}')
    hr()


# ---------------------------------------------------------------------------
# Game and season loops
# ---------------------------------------------------------------------------

# Run one full game: allocate → reveal → roll → score → box score → optional tiebreaker.
def play_game(game_num, record, player_team, opponent):
    cond = gen_conditions()
    pl, cl = player_team, opponent

    show_header(game_num, record, pl, cl, cond)
    p_alloc = player_allocate()
    c_alloc, _ = cpu_allocate()

    show_header(game_num, record, pl, cl, cond)
    show_reveal(p_alloc, c_alloc, pl, cl)
    pause()

    p_rolls, c_rolls = roll_all(p_alloc, c_alloc)

    show_header(game_num, record, pl, cl, cond)
    show_reveal(p_alloc, c_alloc, pl, cl)
    show_rolls(p_alloc, c_alloc, p_rolls, c_rolls, pl, cl)
    pause()

    p_runs, c_runs = compute_score(p_rolls, c_rolls)
    p_sp = max(0, p_rolls[0][1] - c_rolls[2][1])
    p_rp = max(0, p_rolls[1][1] - c_rolls[3][1])
    c_sp = max(0, c_rolls[0][1] - p_rolls[2][1])
    c_rp = max(0, c_rolls[1][1] - p_rolls[3][1])
    p_hits, c_hits = gen_hits(p_runs), gen_hits(c_runs)
    p_err,  c_err  = gen_errors(), gen_errors()

    show_header(game_num, record, pl, cl, cond)
    show_reveal(p_alloc, c_alloc, pl, cl)
    show_rolls(p_alloc, c_alloc, p_rolls, c_rolls, pl, cl)
    show_boxscore(p_sp, p_rp, c_sp, c_rp, p_runs, c_runs,
                  p_hits, c_hits, p_err, c_err, pl, cl)
    pause()

    if p_runs == c_runs:
        winner, p_tb, c_tb = run_tiebreaker()
        show_tiebreaker(game_num, record, p_tb, c_tb, winner, pl, cl, cond, pl, cl)
        pause()
    else:
        winner = 'player' if p_runs > c_runs else 'cpu'

    return p_runs, c_runs, winner


# Loop through 5 games, simulate division results after each, then show the summary.
def play_season(player_team):
    standings = {t: {'w': 0, 'l': 0, 'rs': 0, 'ra': 0} for t in TEAMS}
    p_total = 0
    c_total = 0

    for game_num in range(1, SEASON_GAMES + 1):
        others  = [t for t in TEAMS if t != player_team]
        opponent = random.choice(others)
        record   = [standings[player_team]['w'], standings[player_team]['l']]

        p_runs, c_runs, winner = play_game(game_num, record, player_team, opponent)
        p_total += p_runs
        c_total += c_runs

        # Update player and opponent
        standings[player_team]['rs'] += p_runs
        standings[player_team]['ra'] += c_runs
        standings[opponent]['rs']    += c_runs
        standings[opponent]['ra']    += p_runs
        if winner == 'player':
            standings[player_team]['w'] += 1
            standings[opponent]['l']    += 1
        else:
            standings[player_team]['l'] += 1
            standings[opponent]['w']    += 1

        # Simulate 1 game among the other 3 teams (1 gets a bye)
        rest = [t for t in TEAMS if t != player_team and t != opponent]
        random.shuffle(rest)
        sim_t1, sim_t2, bye_team = rest[0], rest[1], rest[2]
        sim_r1, sim_r2 = simulate_game()
        standings[sim_t1]['rs'] += sim_r1
        standings[sim_t1]['ra'] += sim_r2
        standings[sim_t2]['rs'] += sim_r2
        standings[sim_t2]['ra'] += sim_r1
        if sim_r1 > sim_r2:
            standings[sim_t1]['w'] += 1
            standings[sim_t2]['l'] += 1
        else:
            standings[sim_t1]['l'] += 1
            standings[sim_t2]['w'] += 1

        # Standings screen after each game
        clear()
        hr()
        print(bold(cyan(f'  DIVISION  |  After Game {game_num}')))
        hr()
        show_other_results(sim_t1, sim_r1, sim_t2, sim_r2, bye_team)
        show_standings(standings, player_team)
        pause()

    final_record = [standings[player_team]['w'], standings[player_team]['l']]
    show_season_summary(final_record, p_total, c_total, standings, player_team)


# Entry point: start screen → team pick → season loop → play again prompt.
def main():
    try:
        show_start_screen()
        while True:
            player_team = pick_player_team()
            play_season(player_team)
            try:
                again = input('  Play another season? (y/n): ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                again = 'n'
            if again != 'y':
                print('\n  See you next season.\n')
                break
    except KeyboardInterrupt:
        print('\n\n  Game interrupted. See you next season.\n')


if __name__ == '__main__':
    main()
