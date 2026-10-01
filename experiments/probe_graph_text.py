"""Why does jev leave the "nearer" move with the route facts of the graph? A test of four forms.

The script takes move decisions from a measurement with `--graph` where a
"nearer" move was valid, but jev selected a different move. It asks jev each
question again, in four forms:

    recorded      the recorded state and text
    no loops      the text of promptD-graph: promptD without the sentence about loops
    way           the recorded state, with the target's `way_up` or `way_down` from the
                  tile map, as a run without `--graph` has it
    no loops+way  both changes

For each form it counts the decisions where jev selects a "nearer" move, and
the mean probability of the "nearer" moves. The recorded form measures how
much jev changes its answer when nothing changes.

One request costs about $0.00007. The default (60 decisions, 4 forms) costs about $0.02.

Run:  uv run python -m experiments.probe_graph_text runs/g-graph-jev-own
"""

import argparse
import asyncio
import copy
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

from jevmanic import describe
from jevmanic.brain import Brain, move_question
from jevmanic.game import Game

FORMS = ("recorded", "no loops", "way", "no loops+way")
NO_LOOPS = "promptD-graph"


def left_nearer(folder: Path, per_run: int) -> list[dict]:
    """Decisions where a "nearer" move was valid and jev selected another move: at most `per_run` from each run."""
    found = []
    for path in sorted(folder.glob("*.jsonl")):
        try:
            records = [json.loads(line) for line in path.read_text().splitlines()]
        except json.JSONDecodeError:
            continue  # a live run that is still writing its log file
        if records[-1].get("type") != "end":
            continue
        seen, picked = set(), []
        for r in records:
            moves = r.get("state", {}).get("moves") if r["type"] == "decision" else None
            if r["type"] != "decision" or r.get("forced") or not isinstance(moves, dict):
                continue
            nearer = [m for m, facts in moves.items() if facts.get("progress") == "nearer"]
            place = (tuple(r["result"]["willy"]), tuple(r["target_cell"]), r["macro"])
            if nearer and r["macro"] not in nearer and place not in seen:
                seen.add(place)
                picked.append({**r, "file": str(path), "cavern": records[0]["cavern"],
                               "instructions": records[0]["settings"]["instructions"]})
        found += picked[:per_run]
    return found


def with_the_way(decision: dict) -> dict:
    """The recorded state, with the target's way up or way down from the tile map."""
    records = [json.loads(line) for line in Path(decision["file"]).read_text().splitlines()]
    game = Game(cavern=decision["cavern"])
    for r in records:
        if r["type"] == "decision":
            if r["n"] == decision["n"]:
                break
            game.run_macro(r["macro"])
    snap = game.snapshot()
    cell = tuple(decision["target_cell"])
    target = cell if cell in snap.keys + snap.switches else None
    ways = describe.words(snap, target)["target"]
    state = copy.deepcopy(decision["state"])
    for name in ("way_up", "way_down"):
        if name in ways:
            state["target"][name] = ways[name]
    return state


async def ask(brain, decision, form, state_with_way):
    state = state_with_way if "way" in form else decision["state"]
    instructions = NO_LOOPS if "no loops" in form else decision["instructions"]
    answer = await brain.ask(state, move_question(decision["offered"], instructions), "move")
    nearer = [m for m, facts in decision["state"]["moves"].items() if facts.get("progress") == "nearer"]
    return {"form": form, "choice": answer.choice, "nearer": answer.choice in nearer,
            "p_nearer": sum(answer.probabilities.get(m, 0) for m in nearer), "tokens": answer.input_tokens}


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="a measurement folder with --graph")
    parser.add_argument("--decisions", type=int, default=60)
    parser.add_argument("--per-run", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("experiments/results/probe-graph-text.json"))
    args = parser.parse_args()
    load_dotenv(".env")
    found = left_nearer(args.folder, args.per_run)
    sample = random.Random(args.seed).sample(found, min(args.decisions, len(found)))
    print(f"{len(found)} decisions left a valid 'nearer' move; testing {len(sample)}", flush=True)
    brain = Brain()
    rows = []
    for decision in sample:
        state_with_way = with_the_way(decision)
        answers = await asyncio.gather(*[ask(brain, decision, form, state_with_way) for form in FORMS])
        rows.append({"file": decision["file"], "n": decision["n"], "cavern": decision["cavern"] + 1,
                     "recorded_choice": decision["macro"], "had_way": state_with_way != decision["state"],
                     "answers": answers})
    await brain.close()
    totals = defaultdict(Counter)
    for row in rows:
        for a in row["answers"]:
            totals[a["form"]]["nearer"] += a["nearer"]
            totals[a["form"]]["p"] += a["p_nearer"]
            totals[a["form"]]["tokens"] += a["tokens"]
    print(f"decisions: {len(rows)}, of them with a way up or down on the tile map: {sum(r['had_way'] for r in rows)}")
    summary = {}
    for form in FORMS:
        t = totals[form]
        summary[form] = {"selects_nearer": t["nearer"], "mean_p_nearer": round(t["p"] / max(1, len(rows)), 3)}
        print(f"{form:13} selects a 'nearer' move in {t['nearer']:3} of {len(rows)}; "
              f"mean probability of the 'nearer' moves {t['p'] / max(1, len(rows)):.2f}")
    args.output.write_text(json.dumps({"folder": str(args.folder), "summary": summary, "rows": rows}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
