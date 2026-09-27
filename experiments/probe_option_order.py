"""Test: does the order of the options change the answer of jev?

The script takes move decisions that jev made in recorded runs. It asks jev
each question again, in four forms:

    same       the same order again (this measures how much jev changes its
               answer when nothing changes)
    reversed   the options in the reverse order
    shuffled   the options in a random order
    reversed+  the options and the entries of `moves` in the state, both in
               the reverse order

The state and the text are the same in each form. If the order has no effect,
the three new orders agree with the recorded answer as often as `same` does.
The script also counts how often jev selects the first option.

One request costs approximately $0.00006. The default (200 decisions, 4 forms)
costs approximately $0.05.

Run:  uv run python -m experiments.probe_option_order --runs runs/defaults-all-caverns
"""

import argparse
import asyncio
import glob
import json
import random
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from jevmanic.brain import Brain, MOVE_CRITERIA, move_question

FORMS = ("same", "reversed", "shuffled", "reversed+")


def recorded_decisions(folder: str, minimum_options: int) -> list[dict]:
    """The move decisions that jev made (no forced decision), with enough options to test the order."""
    found = []
    for path in sorted(glob.glob(f"{folder}/*.jsonl")):
        header = None
        for line in open(path):
            record = json.loads(line)
            if record["type"] == "header":
                header = record
            elif (record["type"] == "decision" and not record.get("forced") and record.get("model", "").startswith("jev")
                  and len(record.get("offered", [])) >= minimum_options and isinstance(record["state"].get("moves"), dict)):
                found.append({**record, "instructions": header["settings"].get("instructions", "promptA"), "file": path})
    return found


def question_in_order(decision: dict, order: list[str]) -> dict:
    """The move question of the decision, with the options in `order`."""
    question = move_question(decision["offered"], decision["instructions"])
    question["move"].criteria = {name: MOVE_CRITERIA[name] for name in order}
    return question


async def ask(brain, decision, form, rng):
    offered = list(decision["offered"])
    order = {"same": offered, "reversed": offered[::-1], "reversed+": offered[::-1],
             "shuffled": rng.sample(offered, len(offered))}[form]
    state = decision["state"]
    if form == "reversed+":
        state = {**state, "moves": {name: state["moves"][name] for name in reversed(list(state["moves"]))}}
    answer = await brain.ask(state, question_in_order(decision, order), "move")
    return {"form": form, "order": order, "choice": answer.choice, "probabilities": answer.probabilities,
            "recorded": decision["macro"], "n": decision["n"], "file": decision["file"], "tokens": answer.input_tokens}


async def main():
    parser = argparse.ArgumentParser(description="Does the order of the options change the answer of jev?")
    parser.add_argument("--runs", default="runs/defaults-all-caverns", help="a folder of recorded runs")
    parser.add_argument("--decisions", type=int, default=200, help="the number of decisions to test (default 200)")
    parser.add_argument("--min-options", type=int, default=3, help="only decisions with this number of options or more")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", default="runs/probe-option-order.json")
    args = parser.parse_args()
    load_dotenv(".env")
    rng = random.Random(args.seed)
    pool = recorded_decisions(args.runs, args.min_options)
    sample = rng.sample(pool, min(args.decisions, len(pool)))
    print(f"{len(pool)} recorded decisions with {args.min_options} or more options; the test uses {len(sample)}.")
    brain, limit = Brain(), asyncio.Semaphore(10)

    async def one(decision, form):
        async with limit:
            return await ask(brain, decision, form, random.Random(f"{args.seed}-{decision['file']}-{decision['n']}"))

    results = await asyncio.gather(*(one(d, f) for d in sample for f in FORMS))
    await brain.close()
    Path(args.out).write_text(json.dumps(results, indent=1))

    print(f"\n{'form':10} {'agrees with the recorded answer':>32} {'selects the first option':>26} {'first option by chance':>24}")
    for form in FORMS:
        rows = [r for r in results if r["form"] == form]
        agree = sum(r["choice"] == r["recorded"] for r in rows)
        first = sum(r["choice"] == r["order"][0] for r in rows)
        chance = sum(1 / len(r["order"]) for r in rows)
        print(f"{form:10} {agree:>20} of {len(rows):<9} {first:>16} of {len(rows):<7} {chance:>18.0f} of {len(rows)}")
    # The mean change of the probability of the recorded answer, for each form against `same`.
    same = {(r["file"], r["n"]): r for r in results if r["form"] == "same"}
    for form in FORMS[1:]:
        diffs = [abs(r["probabilities"].get(r["recorded"], 0) - same[(r["file"], r["n"])]["probabilities"].get(r["recorded"], 0))
                 for r in results if r["form"] == form]
        print(f"mean change of the probability of the recorded answer, {form} against same: {sum(diffs) / len(diffs):.3f}")
    tokens = sum(r["tokens"] for r in results)
    print(f"\n{len(results)} requests, {tokens} input tokens, ${tokens * 0.042 / 1e6:.4f}. The answers are in {args.out}.")
    print("Recorded answers in the sample:", dict(Counter(d["macro"] for d in sample)))


if __name__ == "__main__":
    asyncio.run(main())
