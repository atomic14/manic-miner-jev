"""The complete runs and the most keys in each cavern, over every log file in runs/.

This counts all decision makers and all settings together: jev, the rules,
random moves, and the other models. A cavern with no complete run in
thousands of runs points at a limit of the harness, not of one decision maker.

Run:  uv run python -m experiments.all_runs --before 2026-09-30
"""

import argparse
import json
from collections import Counter
from datetime import datetime

from jevmanic.game import Game
from jevmanic.runner import RUNS_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", help="count only the runs that started before this date, for example 2026-09-30")
    args = parser.parse_args()
    before = datetime.fromisoformat(args.before).timestamp() if args.before else float("inf")
    runs, complete, most = Counter(), Counter(), Counter()
    for path in RUNS_DIR.rglob("*.jsonl"):
        lines = path.read_text().splitlines()
        if len(lines) < 2:
            continue
        try:
            header, end = json.loads(lines[0]), json.loads(lines[-1])
        except json.JSONDecodeError:
            continue  # a live run that is still writing its log file
        if header.get("type") != "header" or end.get("type") != "end" or header.get("started", 0) >= before:
            continue
        cavern = header.get("cavern", 0)
        runs[cavern] += 1
        complete[cavern] += end["outcome"] == "cavern complete"
        most[cavern] = max(most[cavern], end.get("keys_collected") or 0)
    names = Game().cavern_names()
    for cavern in range(20):
        print(f"{cavern + 1:2} {names[cavern][:30]:30} runs {runs[cavern]:5}  complete {complete[cavern]:5}  "
              f"most keys {most[cavern]}")
    print(f"all: {sum(runs.values())} runs, {sum(complete.values())} complete")


if __name__ == "__main__":
    main()
