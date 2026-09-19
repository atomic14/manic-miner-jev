"""Test: can jev read an ASCII map?

The script makes many game situations. For each situation it asks jev
questions that have a known answer. The code calculates the correct answer.
The script does this for each state encoder, and prints the accuracy.

Run:  uv run python -m experiments.probe_encodings
"""

import asyncio
import random
from collections import defaultdict
from dataclasses import replace

from dotenv import load_dotenv
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

from jevmanic import describe
from jevmanic.game import Game

SITUATIONS = 40
SEED = 7

QUESTIONS = {
    "key_side": Choice(
        instructions="On which side of Willy is the nearest key?",
        criteria={
            "left": "The nearest key is to the left of Willy.",
            "right": "The nearest key is to the right of Willy.",
            "same column": "The nearest key is directly above or below Willy.",
        },
    ),
    "standing_on": Choice(
        instructions="What is directly below the feet of Willy?",
        criteria={"floor": None, "crumbling floor": None, "conveyor": None},
    ),
    "right_first": Choice(
        instructions=(
            "Willy walks to the right on his level. What is the first thing "
            "that he meets in the next 6 cells?"
        ),
        criteria={
            "wall": "A wall blocks Willy.",
            "nasty": "A nasty is in the path of Willy.",
            "edge": "The floor ends and Willy falls.",
            "clear": "The floor continues and nothing is in the path.",
        },
    ),
    "guardian_level": Noul(
        instructions="Is a guardian on the same level as Willy?",
    ),
}

ENCODERS = {
    "words": lambda s: describe.words(s, nearest_key(s)),
    "ascii_local spaced": lambda s: describe.ascii_local(s, spaced=True),
    "ascii_local packed": lambda s: describe.ascii_local(s, spaced=False),
    "ascii_full spaced": lambda s: describe.ascii_full(s, spaced=True),
}


def nearest_key(snap):
    return min(snap.keys, key=lambda k: abs(k[0] - snap.willy_x) + abs(k[1] - snap.willy_y))


def truth(snap) -> dict:
    w = describe.words(snap, nearest_key(snap))
    first = w["to_the_right"]["first_thing"]
    if first.startswith("nasty"):
        first = "nasty"
    elif first.startswith("edge"):
        first = "edge"
    elif first.startswith("nothing"):
        first = "clear"
    return {
        "key_side": w["target"]["side"],
        "standing_on": w["willy"]["standing_on"],
        "right_first": first,
        "guardian_level": any(g["height"] == "same level" for g in w["guardians"]),
    }


def make_situations():
    """Put Willy at random standing positions across the full cavern.

    Random play stays near the start position, and then each question has
    the same answer in all situations. Thus we make each Snapshot directly.
    """
    rng = random.Random(SEED)
    base = Game().snapshot()
    solid = (describe.TILE_FLOOR, describe.TILE_CRUMBLING, describe.TILE_CONVEYOR)

    def tile(x, y):
        return base.tiles[y][x]

    places = [
        (x, y)
        for y in range(1, 14)
        for x in range(1, 30)
        if all(tile(x + dx, y + dy) == describe.TILE_EMPTY for dx in (0, 1) for dy in (0, 1))
        and any(tile(x + dx, y + 2) in solid for dx in (0, 1))
    ]
    out = []
    for x, y in rng.sample(places, SITUATIONS):
        guardian = base.guardians[0]
        guardian = replace(
            guardian,
            x=rng.randint(guardian.min_x, guardian.max_x),
            moving=rng.choice(["left", "right"]),
        )
        keys = rng.sample(base.keys, rng.randint(1, len(base.keys)))
        out.append(
            replace(base, willy_x=x, willy_y=y, keys=keys, guardians=[guardian],
                    willy_facing=rng.choice(["left", "right"]))
        )
    return out


async def main():
    load_dotenv(".env")
    snaps = make_situations()
    correct = defaultdict(lambda: defaultdict(int))
    tokens = defaultdict(int)
    limit = asyncio.Semaphore(4)

    async with AsyncTypeSafeClient() as client:

        async def ask(name, encode, snap):
            async with limit:
                result = await client.system_one(encode(snap), QUESTIONS)
            expected = truth(snap)
            tokens[name] += result.usage.input_tokens
            for q in ("key_side", "standing_on", "right_first"):
                correct[name][q] += result.choices[q].choice == expected[q]
            answer = result.nouls["guardian_level"].noul > 0.5
            correct[name]["guardian_level"] += answer == expected["guardian_level"]

        await asyncio.gather(
            *(ask(n, e, s) for n, e in ENCODERS.items() for s in snaps)
        )

    names = list(QUESTIONS)
    print(f"\nCorrect answers from {len(snaps)} situations\n")
    print(f"{'encoder':22}" + "".join(f"{q:>16}" for q in names) + f"{'tokens/call':>14}")
    for name in ENCODERS:
        row = "".join(f"{correct[name][q]:>16}" for q in names)
        print(f"{name:22}{row}{tokens[name] // len(snaps):>14}")


if __name__ == "__main__":
    asyncio.run(main())
