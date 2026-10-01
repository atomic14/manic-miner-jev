"""How do the failed runs of a measurement end?

For each failed run, the script looks at its last 30 decisions and puts the
run in one class:

    died              Willy died.
    no nearer move    a "nearer" move was valid in at most a third of the decisions.
    loop of nearer    the decision maker took a "nearer" move in at least a third
                      of the decisions, and Willy still made no progress.
    ignored nearer    a "nearer" move was valid, but the decision maker mostly took
                      a different move.

The first two classes of "stuck" runs point at the route facts: there was no
"nearer" move, or the "nearer" moves went round in a loop. The last class
points at the decision maker.

Run:  uv run python -m experiments.failure_ends runs/depth-4
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

LAST = 30
SHARE = 1 / 3


def classify(records: list[dict]) -> str:
    if records[-1]["outcome"] == "Willy died":
        return "died"
    decisions = [r for r in records if r["type"] == "decision" and isinstance(r["state"].get("moves"), dict)][-LAST:]
    offered = taken = 0
    for r in decisions:
        nearer = [m for m, facts in r["state"]["moves"].items() if facts.get("progress") == "nearer"]
        offered += bool(nearer)
        taken += r["macro"] in nearer
    if offered <= SHARE * len(decisions):
        return "no nearer move"
    if taken >= SHARE * len(decisions):
        return "loop of nearer"
    return "ignored nearer"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="a measurement folder in runs/")
    folder = parser.parse_args().folder
    classes = defaultdict(Counter)
    for path in sorted(folder.glob("*.jsonl")):
        try:
            records = [json.loads(line) for line in path.read_text().splitlines()]
        except json.JSONDecodeError:
            continue  # a live run that is still writing its log file
        if records[-1].get("type") != "end" or records[-1]["outcome"] == "cavern complete":
            continue
        classes[records[0]["cavern"]][classify(records)] += 1
    total = Counter()
    for cavern in sorted(classes):
        total.update(classes[cavern])
        print(f"cavern {cavern + 1:2}: " + ", ".join(f"{k} {v}" for k, v in sorted(classes[cavern].items())))
    print(f"all {sum(total.values())} failed runs: " + ", ".join(f"{k} {v}" for k, v in total.most_common()))


if __name__ == "__main__":
    main()
