"""Can identical inputs require different first moves to collect a key?

Run: uv run python -m experiments.probe_key_reachability --near-keys runs/depth-4

Search all six moves after each offered first move. Success means collecting
any remaining key while alive at a move boundary, or completing the cavern.
Results apply only to the chosen move horizon. No model requests are made.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from experiments.probe_identical_inputs import candidates, reset, restore
from jevmanic.game import ADDR_ITEMS, MACROS

SEARCH_SLOT = 1000


def near_key_pairs(folder, horizon, per_cavern, min_distance=1):
    """Select groups with a recorded, living key collection within the horizon.

    This is a deliberately enriched sample, not a population estimate.
    Keep the qualifying history and the other history farthest away in time.
    The minimum distance applies after the selection in each cavern, so a
    shorter horizon cannot already decide the rows that remain.
    """
    qualifying = {}
    for path in sorted(folder.glob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text().splitlines()]
        decisions = [r for r in records if r["type"] == "decision"]
        previous = 0
        for i, record in enumerate(decisions):
            result = record["result"]
            count = result["keys_collected"]
            if count > previous and not result["dead"]:
                for j in range(max(0, i - horizon + 1), i + 1):
                    qualifying.setdefault((str(path), decisions[j]["n"]), i - j + 1)
            previous = count
    _, _, groups = candidates(folder)
    selected = defaultdict(list)
    for key, entries in groups:
        eligible = [e for e in entries if (e["file"], e["n"]) in qualifying]
        if not eligible:
            continue
        first = min(eligible, key=lambda e: qualifying[e["file"], e["n"]])
        other = max((e for e in entries if e != first), key=lambda e: abs(e["tick"] - first["tick"]))
        selected[key[0]].append({"cavern": key[0] + 1, "examples": [first, other],
                                 "input": json.loads(key[1]),
                                 "recorded_key_distance": qualifying[first["file"], first["n"]]})
    # Spread selection across collection distances, with stable ordering.
    rows = []
    for cavern in sorted(selected):
        ordered = sorted(selected[cavern], key=lambda r: r["recorded_key_distance"])
        if len(ordered) <= per_cavern:
            rows.extend(ordered)
        else:
            rows.extend(ordered[i * (len(ordered) - 1) // max(1, per_cavern - 1)] for i in range(per_cavern))
    selection = "recorded living key collection within the horizon"
    if min_distance > 1:
        rows = [r for r in rows if r["recorded_key_distance"] >= min_distance]
        selection += f"; retain selected pairs whose first recorded collection is at least {min_distance} moves away"
    return {"selection": selection, "folder": str(folder), "horizon": horizon,
            "eligible_groups": sum(map(len, selected.values())), "rows": rows}


def remaining_keys(game):
    count = 0
    for attr in game.emu.peek_range(ADDR_ITEMS, 25)[::5]:
        if attr == 255:
            break
        count += attr != 0
    return count


def find_key(game, keys_before, depth, budget):
    """Return (status, witness). A failure is exhaustive; budget exhaustion is unknown.

    Do not merge nodes by Python snapshot: identical snapshots can hide
    guardian phases. Every branch restores the emulator's full saved state.
    """
    if game.is_dead():
        return "unreachable", None
    if game.is_complete() or remaining_keys(game) < keys_before:
        return "reachable", []
    if depth == 0:
        return "unreachable", None
    slot, tick = SEARCH_SLOT + depth, game.tick_count
    game.emu.save_state(slot)
    unknown = False
    for move in MACROS:
        if budget[0] <= 0:
            return "unknown", None
        budget[0] -= 1
        game.run_macro(move)
        status, path = find_key(game, keys_before, depth - 1, budget)
        game.emu.load_state(slot)
        game.emu.set_joystick(0)
        game.tick_count = tick
        if status == "reachable":
            return status, [move, *path]
        unknown |= status == "unknown"
    return ("unknown" if unknown else "unreachable"), None


def profile(game, record, horizon, budget):
    keys_before = remaining_keys(game)
    if keys_before == 0:
        return None
    found = {}
    for first in record["offered"]:
        reset(game, record["tick"])
        game.run_macro(first)
        remaining = [budget]
        status, path = find_key(game, keys_before, horizon - 1, remaining)
        witness = [first, *path] if path is not None else None
        if witness is not None:
            # Verify every positive result by replaying its complete witness.
            reset(game, record["tick"])
            for move in witness:
                game.run_macro(move)
                assert not game.is_dead()
            assert game.is_complete() or remaining_keys(game) < keys_before
        found[first] = {"status": status, "witness": witness, "searched_moves": budget - remaining[0]}
    reset(game, record["tick"])
    return found


def compare(profiles):
    good = [{m for m, p in profile.items() if p["status"] == "reachable"} for profile in profiles]
    possible = [{m for m, p in profile.items() if p["status"] != "unreachable"} for profile in profiles]
    # Unknown branches cannot support a claim that the first moves conflict.
    conflict = all(good) and not (possible[0] & possible[1])
    differences = [m for m in profiles[0]
                   if {p[m]["status"] for p in profiles} == {"reachable", "unreachable"}]
    return {"different_moves": differences, "conflicting_first_moves": bool(conflict),
            "common_proven_moves": sorted(good[0] & good[1])}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=Path("experiments/results/identical-inputs.json"))
    parser.add_argument("--horizon", type=int, default=4)
    parser.add_argument("--budget", type=int, default=10000)
    parser.add_argument("--rows", help="comma-separated source row indices; default: all")
    parser.add_argument("--near-keys", type=Path, help="build a source sample from this run folder")
    parser.add_argument("--per-cavern", type=int, default=3)
    parser.add_argument("--min-distance", type=int, default=1,
                        help="with --near-keys, keep pairs whose recorded collection is at least this many moves away")
    parser.add_argument("--output", type=Path, default=Path("experiments/results/key-reachability-4.json"))
    args = parser.parse_args()
    if not 1 <= args.horizon <= 20 or args.budget < 1 or args.per_cavern < 1:
        parser.error("horizon must be 1 to 20 and budget must be positive")
    if args.near_keys:
        args.source = args.output.with_name(args.output.stem + "-source.json")
        args.source.parent.mkdir(parents=True, exist_ok=True)
        args.source.write_text(json.dumps(near_key_pairs(args.near_keys, args.horizon, args.per_cavern, args.min_distance), indent=2) + "\n")
    source = json.loads(args.source.read_text())
    indices = list(range(len(source["rows"]))) if args.rows is None else [int(i) for i in args.rows.split(",")]
    rows = []
    for index in indices:
        pair = source["rows"][index]
        restored = [restore(e) for e in pair["examples"]]
        profiles = [profile(g, r, args.horizon, args.budget) for g, r, *_ in restored]
        if any(p is None for p in profiles):
            rows.append({"source_row": index, "cavern": pair["cavern"], "skipped": "no keys remain"})
            continue
        row = {"source_row": index, "cavern": pair["cavern"],
               "prefixes": [p for _, _, p, _ in restored],
               "profiles": profiles, **compare(profiles)}
        rows.append(row)
        print(f"row {index}, cavern {pair['cavern']}: different={row['different_moves']}, "
              f"conflict={row['conflicting_first_moves']}", flush=True)
        # Preserve completed work if a later search is interrupted.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"source": str(args.source), "horizon": args.horizon,
                                          "budget_per_first_move": args.budget, "rows": rows}, indent=2) + "\n")
    checked = [r for r in rows if "profiles" in r]
    summary = {"pairs_tested": len(checked), "pairs_skipped": len(rows) - len(checked),
               "pairs_with_reachable_key": sum(any(p["status"] == "reachable" for profile in r["profiles"]
                                                   for p in profile.values()) for r in checked),
               "pairs_with_different_moves": sum(bool(r["different_moves"]) for r in checked),
               "pairs_with_conflicting_first_moves": sum(r["conflicting_first_moves"] for r in checked),
               "unknown_results": sum(p["status"] == "unknown" for r in checked
                                      for profile in r["profiles"] for p in profile.values())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source": str(args.source), "horizon": args.horizon,
                                      "budget_per_first_move": args.budget, "summary": summary,
                                      "rows": rows}, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
