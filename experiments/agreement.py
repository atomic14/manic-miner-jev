"""How often does jev select a move that the rule `nearer` would also select?

For each move decision with a jev request, the script checks if jev's move is
one of the moves that the rule `nearer` can select. It also gives the chance
level: the probability that a uniformly random valid move is one of them.

Run:  uv run python -m experiments.agreement runs/defaults-all-caverns
"""

import argparse
import json
from pathlib import Path

from jevmanic.runner import rule_moves


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="a measurement folder with jev log files")
    folder = parser.parse_args().folder
    decisions = agree = 0
    chance = 0.0
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r.get("type") != "decision" or r.get("forced") or not isinstance(r["state"].get("moves"), dict):
                continue
            allowed = rule_moves("nearer", r["offered"], r["state"]["moves"])
            decisions += 1
            agree += r.get("jev_choice", r["macro"]) in allowed
            chance += len(allowed) / len(r["offered"])
    print(f"{decisions} move decisions with a jev request")
    print(f"jev selects a move that the rule can select: {agree} ({100 * agree / decisions:.1f} %)")
    print(f"a random valid move would do this: {100 * chance / decisions:.1f} %")


if __name__ == "__main__":
    main()
