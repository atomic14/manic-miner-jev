"""Find identical Jev inputs and test their hidden differences without API calls.

Run: uv run python -m experiments.probe_identical_inputs runs/depth-4

Different continuations establish missing information, not different optimal
choices. Survival searches report unknown when their budget runs out.
"""

import argparse
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import fields
from pathlib import Path

from jevmanic import describe
from jevmanic.game import ADDR_HGUARDS, Game
from jevmanic.runner import _LiveRun
from jevmanic.settings import Settings

BRANCH_SLOT = 900


def packed(value):
    # Preserve field and option order, because order can affect Jev's answer.
    return json.dumps(value, separators=(",", ":"))


def candidates(folder):
    groups = defaultdict(dict)
    total = 0
    for path in sorted(folder.glob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text().splitlines()]
        header, history = records[0], []
        for record in records[1:]:
            if record["type"] != "decision":
                continue
            if (not record.get("forced") and record.get("model", "").startswith("jev")
                    and isinstance(record.get("state", {}).get("moves"), dict)):
                question = header["questions"]["move"]
                question = {**question, "criteria": {m: question["criteria"][m] for m in record["offered"]}}
                identity = packed([record["state"], question, record["model"]])
                key = (header["cavern"], identity)
                route = hashlib.sha256(packed(history).encode()).hexdigest()
                groups[key].setdefault(route, {
                    "file": str(path), "n": record["n"], "tick": record["tick"],
                })
                total += 1
            history.append(record["macro"])
    collisions = [(key, list(entries.values())) for key, entries in groups.items() if len(entries) > 1]
    return total, len(groups), collisions


def restore(entry):
    records = [json.loads(line) for line in Path(entry["file"]).read_text().splitlines()]
    header = records[0]
    game = Game(cavern=header["cavern"])
    settings = Settings(**header["settings"])
    run = _LiveRun(game, None, settings)
    decisions = [r for r in records if r["type"] == "decision"]
    prefix = []
    for record in decisions:
        snap = game.snapshot()
        if record["n"] == entry["n"]:
            target = tuple(record["target_cell"])
            target = target if target in snap.keys + snap.switches else None
            state = describe.move_request_state(snap, game.look_ahead(settings.survival_depth),
                                                target, run.visited, run.tried, settings)
            if packed(state) != packed(record["state"]) or game.tick_count != record["tick"]:
                raise ValueError(f"Current replay does not reproduce the input: {entry}")
            game.emu.save_state(BRANCH_SLOT)
            suffix = [r["macro"] for r in decisions if r["n"] >= entry["n"]]
            return game, record, prefix, suffix
        run.tried.add((snap.willy_x, snap.willy_y, record["macro"]))
        game.run_macro(record["macro"])
        after = game.snapshot()
        if [after.willy_x, after.willy_y] != record["result"]["willy"]:
            raise ValueError(f"Position mismatch before {entry}")
        run.remember(record["result"])
        prefix.append(record["macro"])
    raise ValueError(f"Decision absent: {entry}")


def reset(game, tick):
    game.emu.load_state(BRANCH_SLOT)
    game.emu.set_joystick(0)
    game.tick_count = tick


def survival(game, record, depth, budget):
    result = {}
    for move in record["offered"]:
        reset(game, record["tick"])
        game.run_macro(move)
        remaining = [budget]
        alive = game._can_survive(depth - 1, remaining)
        result[move] = "unknown" if alive is None else "survives" if alive else "dies"
    reset(game, record["tick"])
    return result


def continuation(game, tick, moves):
    reset(game, tick)
    keys_before = len(game.snapshot().keys)
    keys, played = 0, 0
    for move in moves:
        if game.is_dead() or game.is_complete():
            break
        game.run_macro(move)
        played += 1
        if game.is_complete():
            keys = keys_before
        elif not game.is_dead():
            keys = max(keys, keys_before - len(game.snapshot().keys))
    return {"dead": game.is_dead(), "complete": game.is_complete(), "keys": keys, "moves_played": played}


def probe(key, entries, depth, budget, horizon):
    # Widely separated game times are useful candidates for different guardian phases.
    entries = sorted(entries, key=lambda e: (e["tick"], e["file"], e["n"]))
    selected = [entries[0], entries[-1]]
    restored = [restore(entry) for entry in selected]
    games = [r[0] for r in restored]
    records = [r[1] for r in restored]
    snapshots = [g.snapshot() for g in games]
    hidden = {f.name: [repr(getattr(s, f.name)) for s in snapshots]
              for f in fields(snapshots[0]) if getattr(snapshots[0], f.name) != getattr(snapshots[1], f.name)}
    pixels = [g._willy_pixel() for g in games]
    if pixels[0] != pixels[1]:
        hidden["willy_pixel"] = pixels
    guardian_bytes = [list(g.emu.peek_range(ADDR_HGUARDS, 28)) for g in games]
    profiles = [survival(g, r, depth, budget) for g, r in zip(games, records)]
    different = [m for m in records[0]["offered"] if {p[m] for p in profiles} == {"survives", "dies"}]
    safe_sets = [{m for m, status in p.items() if status == "survives"} for p in profiles]
    conflict = (all(safe_sets) and not set.intersection(*safe_sets)
                and all("unknown" not in p.values() for p in profiles))
    witnesses = []
    sequences = {tuple(r[3][:horizon]) for r in restored}
    for sequence in sorted(sequences):
        outcomes = [continuation(g, r["tick"], sequence) for g, r in zip(games, records)]
        if any(outcomes[0][k] != outcomes[1][k] for k in ("dead", "complete", "keys")):
            witnesses.append({"moves": sequence, "outcomes": outcomes})
    return {"cavern": key[0] + 1, "occurrences": len(entries), "examples": selected,
            "prefixes": [r[2] for r in restored], "input": json.loads(key[1]),
            "hidden_snapshot_differences": hidden, "horizontal_guardian_bytes": guardian_bytes,
            "survival": profiles,
            "different_survival_moves": different, "disjoint_surviving_moves": bool(conflict),
            "continuation_witnesses": witnesses}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--per-cavern", type=int, default=3)
    parser.add_argument("--depth", type=int, default=8, choices=range(1, 21))
    parser.add_argument("--budget", type=int, default=600)
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("experiments/results/identical-inputs.json"))
    args = parser.parse_args()
    if min(args.per_cavern, args.budget, args.horizon) < 1:
        parser.error("per-cavern, budget, and horizon must be positive")
    total, distinct, collisions = candidates(args.folder)
    by_cavern = defaultdict(list)
    for key, entries in collisions:
        by_cavern[key[0]].append((key, entries))
    rng = random.Random(args.seed)
    sample = [pair for cavern in sorted(by_cavern)
              for pair in rng.sample(by_cavern[cavern], min(args.per_cavern, len(by_cavern[cavern])))]
    print(f"{total} decisions, {distinct} inputs, {len(collisions)} groups with different histories; "
          f"testing {len(sample)} pairs", flush=True)
    rows = []
    for key, entries in sample:
        row = probe(key, entries, args.depth, args.budget, args.horizon)
        rows.append(row)
        print(f"{len(rows)}/{len(sample)} cavern {row['cavern']}: "
              f"survival differences={row['different_survival_moves']}, "
              f"continuation witnesses={len(row['continuation_witnesses'])}", flush=True)
    summary = {"decisions": total, "distinct_inputs": distinct, "collision_groups": len(collisions),
               "pairs_tested": len(rows),
               "pairs_with_survival_difference": sum(bool(r["different_survival_moves"]) for r in rows),
               "pairs_with_disjoint_surviving_moves": sum(r["disjoint_surviving_moves"] for r in rows),
               "unknown_survival_results": sum(v == "unknown" for r in rows
                                               for p in r["survival"] for v in p.values()),
               "pairs_with_continuation_difference": sum(bool(r["continuation_witnesses"]) for r in rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"settings": {k: str(v) if isinstance(v, Path) else v
                                                   for k, v in vars(args).items()},
                                      "summary": summary, "rows": rows}, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
