"""Test: can jev select a good next key? This test plays no game.

Reference: the script replays each complete recorded run in the emulator and
records the order in which Willy collected the keys. For a situation (a set
of collected keys), the good next keys are the keys that a complete run
collected next from that same set.

Test: for each situation, the script asks jev "which key next?" with
different inputs, and measures the probability that jev gives to the good
keys.

Inputs:
    facts        the present target state (facts relative to Willy)
    map          the full map with its legend
    map+facts    the two together
    map, letters in a different sequence    to see if a letter has an influence

Run:  uv run python -m experiments.probe_key_order [caverns=1,2,3,4]
"""

import glob
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace

from dotenv import load_dotenv
from typesafe_sdk import Choice, TypeSafeClient

from jevmanic import brain, describe
from jevmanic.game import Game

MAP_INSTRUCTIONS = (
    "Willy is a miner in a platform game. The map shows the cavern, and "
    "`map_legend` tells what each symbol means. Willy must collect all keys and "
    "then go into the exit portal. Willy can climb only 2 rows with one jump. He "
    "can fall to a lower floor, but after a long fall he cannot climb back. A "
    "crumbling floor breaks when Willy uses it, thus a way that goes across a "
    "crumbling floor can be open only one time. Select the key that Willy gets "
    "next, in an order that lets him get all keys."
)


def complete_runs():
    for path in glob.glob("runs/**/*.jsonl", recursive=True) + glob.glob("demo/*.jsonl"):
        lines = open(path).read().splitlines()
        if len(lines) > 2 and json.loads(lines[-1]).get("outcome") == "cavern complete":
            records = [json.loads(line) for line in lines]
            yield records[0].get("cavern", 0), [r["macro"] for r in records if r["type"] == "decision"]


def key_orders(game: Game, caverns):
    """The key order of each complete run, and the game situations of the shortest run."""
    orders = defaultdict(list)
    shortest = {}
    for cavern, macros in complete_runs():
        if cavern not in caverns:
            continue
        game.select_cavern(cavern)
        order, left = [], list(game.snapshot().keys)
        for macro in macros:
            game.run_macro(macro)
            now = game.snapshot().keys
            order += [k for k in left if k not in now]
            left = list(now)
        orders[cavern].append(order)
        if cavern not in shortest or len(macros) < len(shortest[cavern]):
            shortest[cavern] = macros
    return orders, shortest


def situations(game: Game, cavern: int, macros):
    """The snapshot at the start, and after each key, while 2 or more keys are left."""
    game.select_cavern(cavern)
    snap = game.snapshot()
    out = [snap]
    left = len(snap.keys)
    for macro in macros:
        game.run_macro(macro)
        snap = game.snapshot()
        if len(snap.keys) < left and not snap.airborne:
            left = len(snap.keys)
            if left >= 2:
                out.append(snap)
    return out


def ask(client, state, instructions, letters):
    criteria = {f"key_{letter}": f"Key {letter}." for letter in letters}
    answer = client.system_one(state, {"next": Choice(instructions=instructions, criteria=criteria)})
    choice = answer.choices["next"]
    return choice.choice.removeprefix("key_"), {k.removeprefix("key_"): v for k, v in choice.probabilities.items()}


def main():
    load_dotenv(".env")
    caverns = [0, 1, 2, 3]
    for arg in sys.argv[1:]:
        if arg.startswith("caverns="):
            caverns = [int(c) - 1 for c in arg.split("=")[1].split(",")]
    client = TypeSafeClient()
    game = Game()
    orders, shortest = key_orders(game, caverns)
    totals = defaultdict(list)
    for cavern in caverns:
        if cavern not in orders:
            print(f"cavern {cavern + 1}: no complete run is recorded")
            continue
        game.select_cavern(cavern)
        first = game.snapshot()
        letters = first.key_letters
        as_letters = [[letters[k] for k in order] for order in orders[cavern]]
        print(f"\n=== {cavern + 1}. {first.cavern_name}: {len(as_letters)} complete runs")
        print("   key orders:", dict(Counter("".join(o) for o in as_letters).most_common(6)))
        good_next = defaultdict(Counter)
        for order in as_letters:
            for i, key in enumerate(order):
                good_next[frozenset(order[:i])][key] += 1
        for row in describe.ascii_full(first, spaced=False)["map"]:
            print("   " + row)
        for snap in situations(game, cavern, shortest[cavern]):
            left = [letters[k] for k in snap.keys]
            collected = frozenset(set(letters.values()) - set(left))
            good = set(good_next.get(collected, {}))
            if not good or len(good) == len(left):
                continue  # each key that is left is good: the question tells us nothing
            names = {k: f"key_{letters[k]}" for k in snap.keys}
            full_map = describe.ascii_full(snap, spaced=False)
            # The same map with the letters in the opposite sequence.
            swap = dict(zip(sorted(left), sorted(left, reverse=True)))
            swapped = replace(snap, key_letters={k: swap[letters[k]] for k in snap.keys})
            inputs = {
                "facts": (describe.keys_state(snap, names), brain.FREE_TARGET_INSTRUCTIONS, None),
                "map": (full_map, MAP_INSTRUCTIONS, None),
                "map+facts": ({**full_map, **describe.keys_state(snap, names)}, MAP_INSTRUCTIONS, None),
                "map, other letters": (describe.ascii_full(swapped, spaced=False), MAP_INSTRUCTIONS, swap),
            }
            print(f"   collected {''.join(sorted(collected)) or '-':5} good next: {''.join(sorted(good)):4}", end="")
            for name, (state, instructions, mapping) in inputs.items():
                choice, probs = ask(client, state, instructions, sorted(left))
                if mapping:  # change the answer back to the normal letters
                    back = {v: k for k, v in mapping.items()}
                    choice, probs = back[choice], {back[k]: v for k, v in probs.items()}
                mass = sum(v for k, v in probs.items() if k in good)
                totals[name].append(mass)
                print(f" | {name}: {choice} {'ok ' if choice in good else 'BAD'} {mass:.2f}", end="")
            print()
    print("\nmean probability on a good next key (1.00 is the best):")
    chance = "the value for a random choice is approximately 0.3 to 0.5"
    for name, values in totals.items():
        print(f"   {name:22} {sum(values) / len(values):.2f}   ({len(values)} situations)")
    print("   " + chance)


if __name__ == "__main__":
    main()
