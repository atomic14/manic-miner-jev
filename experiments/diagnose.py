"""Show why a recorded run ended: the map, the last positions, the last state.

Run:  uv run python -m experiments.diagnose runs/<folder>/<file>.jsonl
"""

import json
import sys
from collections import Counter

from jevmanic import describe
from jevmanic.game import Game


def main(path):
    records = [json.loads(line) for line in open(path)]
    header, end = records[0], records[-1]
    decisions = [r for r in records if r["type"] == "decision"]
    game = Game(cavern=header.get("cavern", 0))
    for r in decisions[:-1]:
        game.run_macro(r["macro"])
    snap = game.snapshot()
    print(f"{header.get('cavern_name')} | {end.get('outcome')} | keys {end.get('keys_collected')} | decisions {len(decisions)}")
    print("map before the last decision (W Willy, G guardian, K key, P portal, T target):")
    grid = [row for row in describe.ascii_full(snap, spaced=False)["map"]]
    tx, ty = decisions[-1]["target_cell"]
    grid[ty] = grid[ty][:tx] + "T" + grid[ty][tx + 1:]
    for y, row in enumerate(grid):
        print(f"  {y:2} {row}")
    places = Counter(tuple(r["result"]["willy"]) for r in decisions[-30:])
    print("positions in the last 30 decisions:", places.most_common(5))
    last = decisions[-1]
    state = last["state"]
    print("last macro:", last["macro"], "| confidence", round(last["confidence"], 2))
    print("target:", json.dumps(state.get("target")))
    print("measure:", state.get("progress_measures"))
    if isinstance(state.get("moves"), dict):
        for name, move in state["moves"].items():
            print(f"   {name:11} {move}")
    print("removed:", last.get("removed"))


if __name__ == "__main__":
    main(sys.argv[1])
