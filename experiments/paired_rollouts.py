"""Are jev's moves better than the rule's where the two disagree?

The script reads the log files of a jev measurement and finds the move
decisions where jev selected a move that the rule `nearer` would not select.
At each of these decisions it replays the run up to that point, and then it
plays two branches from the same game state:

    jev    jev's recorded move
    rule   a move that the rule `nearer` selects

After that first move, the rule plays both branches for HORIZON decisions,
with the same target (and the nearest key after the target is collected).
Each branch is played ROLLOUTS times, because the rule breaks ties at random.
The result is the mean number of keys collected, and the share of branches in
which Willy died or completed the cavern. The script makes no jev requests.

Run:  uv run python -m experiments.paired_rollouts runs/defaults-all-caverns --states 120
"""

import argparse
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from jevmanic import describe
from jevmanic.game import MACROS, SURVIVAL_DEPTH, Game
from jevmanic.runner import rule_moves

BRANCH_SLOT = 50  # emulator save slot for the branch point; the look-ahead uses slots 1 to 6
HORIZON = 60
ROLLOUTS = 6


def disagreements(folder: Path) -> list[tuple[Path, int]]:
    """(log file, decision number) for each non-forced jev move outside the rule's choices."""
    found = []
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r.get("type") != "decision" or r.get("forced") or not isinstance(r["state"].get("moves"), dict):
                continue
            if r["macro"] not in rule_moves("nearer", r["offered"], r["state"]["moves"]):
                found.append((path, r["n"]))
    return found


def replay_to(game: Game, records: list[dict], n: int):
    """Play the logged moves before decision `n`. Returns the target at decision `n`."""
    game.select_cavern(records[0].get("cavern", 0))
    target = None
    for r in records[1:]:
        if r["type"] == "target" and r["n"] <= n:
            target = tuple(r["target_cell"])
        if r["type"] == "decision":
            if r["n"] == n:
                return target, r
            game.run_macro(r["macro"])
    raise ValueError(f"decision {n} is not in the log")


def rule_step(game: Game, target, rng: random.Random) -> str:
    """The rule's move in the present game state, from the same facts that jev gets."""
    snap = game.snapshot()
    outcomes = game.look_ahead(SURVIVAL_DEPTH)
    state = describe.move_request_state(snap, outcomes, target, Counter(), set())
    facts = state["moves"] if isinstance(state["moves"], dict) else {}
    # As in a live run: when no move is valid, all moves are offered.
    offered = list(facts) or list(MACROS)
    return rng.choice(rule_moves("nearer", offered, facts))


def play_branch(game: Game, first_move: str, target, keys_before: int, rng: random.Random) -> dict:
    """Play `first_move`, then the rule for HORIZON decisions. Returns the outcome."""
    game.run_macro(first_move)
    # Count the keys while Willy is alive: after a death, the game restarts the cavern with all keys.
    keys = 0
    for _ in range(HORIZON):
        if game.is_dead() or game.is_complete():
            break
        snap = game.snapshot()
        keys = max(keys, keys_before - len(snap.keys))
        if target is not None and tuple(target) not in snap.keys + snap.switches:
            goals = snap.keys + snap.switches
            target = min(goals, key=lambda k: abs(k[0] - snap.willy_x) + abs(k[1] - snap.willy_y)) if goals else None
        game.run_macro(rule_step(game, target, rng))
    if game.is_complete():
        keys = keys_before
    elif not game.is_dead():
        keys = max(keys, keys_before - len(game.snapshot().keys))
    return {"keys": keys, "dead": game.is_dead(), "complete": game.is_complete()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="a measurement folder with jev log files")
    parser.add_argument("--states", type=int, default=120, help="number of disagreement states to test")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    found = disagreements(args.folder)
    sample = rng.sample(found, min(args.states, len(found)))
    print(f"{len(found)} disagreements in {args.folder}; testing {len(sample)}, "
          f"{ROLLOUTS} rollouts per branch, horizon {HORIZON} decisions")
    game = Game()
    rows = []
    for i, (path, n) in enumerate(sample):
        records = [json.loads(line) for line in path.read_text().splitlines()]
        target, record = replay_to(game, records, n)
        keys_before = len(game.snapshot().keys)
        game.emu.save_state(BRANCH_SLOT)
        ticks = game.tick_count
        result = {"file": path.name, "n": n, "jev_move": record["macro"]}
        for branch in ("jev", "rule"):
            outs = []
            for _ in range(ROLLOUTS):
                game.emu.load_state(BRANCH_SLOT)
                game.emu.set_joystick(0)
                game.tick_count = ticks
                first = record["macro"] if branch == "jev" else rng.choice(
                    rule_moves("nearer", record["offered"], record["state"]["moves"]))
                outs.append(play_branch(game, first, target, keys_before, rng))
            result[branch] = {
                "keys": statistics.mean(o["keys"] for o in outs),
                "dead": statistics.mean(o["dead"] for o in outs),
                "complete": statistics.mean(o["complete"] for o in outs),
            }
        rows.append(result)
        print(f"{i + 1:4}/{len(sample)} {path.name[:60]} n={n}: keys jev {result['jev']['keys']:.2f} "
              f"rule {result['rule']['keys']:.2f}", flush=True)

    def mean(branch, what):
        return statistics.mean(r[branch][what] for r in rows)

    diffs = [r["jev"]["keys"] - r["rule"]["keys"] for r in rows]
    print(f"\nstates: {len(rows)}")
    for what in ("keys", "dead", "complete"):
        print(f"{what:9} jev branch {mean('jev', what):.3f}   rule branch {mean('rule', what):.3f}")
    print(f"keys, jev minus rule: mean {statistics.mean(diffs):+.3f}, "
          f"better {sum(d > 0 for d in diffs)}, worse {sum(d < 0 for d in diffs)}, same {sum(d == 0 for d in diffs)}")
    out = args.folder / "paired-rollouts.json"
    out.write_text(json.dumps({"horizon": HORIZON, "rollouts": ROLLOUTS, "rows": rows}, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
