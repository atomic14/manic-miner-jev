"""The request checks: tests of what jev gets. The tests and the measurement tool run them.

1. A text names only fields that its state has. In the texts, a name in back
   quotes is a state field (for example `moves` or `target.height`). A text
   that names a missing field gives jev wrong information.
2. Each move's facts agree with the game after the move. The look-ahead plays
   each move in the emulator and keeps the snapshot at its end, so the facts
   must match that snapshot.

The checks use real situations: they replay recorded runs, and at each
decision they build the states with the same functions as a live run.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache

from . import describe
from .brain import instruction_sets, key_instructions, move_instructions
from .game import Game, Snapshot
from .runner import DEMO_DIR

# promptC is the set for Laya. Laya gets sentences (laya_brain.py), not the JSON state.
NOT_FOR_JEV_STATE = ("promptC",)

# The recorded runs that the checks replay: complete runs of three caverns.
CHECK_RUNS = ("cavern-01-central-cavern-promptA.jsonl", "cavern-02-the-cold-room-promptA.jsonl",
              "cavern-03-the-menagerie-promptA.jsonl")


@dataclass
class Situation:
    """One move decision from a recorded run: the game before the move, and the look-ahead."""

    snap: Snapshot
    outcomes: dict
    target: tuple | None
    visited: Counter
    tried: set


def replay_situations(file: str, survival_depth: int = 4) -> list[Situation]:
    """Replay a recorded run from demo/, and keep a Situation for each move decision."""
    records = [json.loads(line) for line in (DEMO_DIR / file).read_text().splitlines()]
    game = Game()
    game.select_cavern(records[0].get("cavern", 0))
    visited, tried, found = Counter(), set(), []
    for record in records[1:]:
        if record["type"] != "decision":
            continue
        snap = game.snapshot()
        cell = tuple(record["target_cell"])
        target = cell if cell in snap.keys + snap.switches else None
        found.append(Situation(snap, game.look_ahead(survival_depth), target, Counter(visited), set(tried)))
        tried.add((snap.willy_x, snap.willy_y, record["macro"]))
        for _ in game.macro_ticks(record["macro"]):
            pass
        after = game.snapshot()
        visited[(after.willy_x, after.willy_y)] += 1
    return found


@cache
def check_situations() -> tuple[Situation, ...]:
    """The situations from all CHECK_RUNS. Cached, because the replay takes a few seconds."""
    return tuple(s for file in CHECK_RUNS for s in replay_situations(file))


# -- 1. A text names only fields that its state has --------------------------------------

BACK_QUOTES = re.compile(r"`([^`]+)`")


def named_fields(text: str) -> set[str]:
    """The field names in back quotes. `target.way_up` gives `target` and `way_up`."""
    names = set()
    for path in BACK_QUOTES.findall(text):
        for part in path.split("."):
            part = re.sub(r"\[\d+\]$", "", part).strip()
            if part and part != "*":
                names.add(part)
    return names


def state_fields(value, found: set | None = None) -> set[str]:
    """All keys of a JSON value, at each depth."""
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(key)
            state_fields(item, found)
    elif isinstance(value, list):
        for item in value:
            state_fields(item, found)
    return found


def text_problems(instructions: str, situations=None) -> list[str]:
    """One message for each text in a set that names fields that its states never have."""
    if instructions in NOT_FOR_JEV_STATE:
        return []
    situations = check_situations() if situations is None else situations
    move_fields, map_fields, facts_fields = set(), set(), set()
    for s in situations:
        move_fields |= state_fields(describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried))
        if s.snap.keys:
            names = describe.key_names(s.snap)
            # A memory that makes the key state have every optional field.
            first = s.snap.keys[0]
            memory = {"current": first, "used": {first: 3}, "gave_up": {first: 1}}
            map_fields |= state_fields(describe.key_request_state(s.snap, names, memory, True))
            facts_fields |= state_fields(describe.key_request_state(s.snap, names, memory, False))
    problems = []
    for what, text, fields in (
        ("move text", move_instructions(instructions), move_fields),
        ("key text (with the map)", key_instructions(instructions, True), map_fields),
        ("key text (facts only)", key_instructions(instructions, False), facts_fields),
    ):
        missing = sorted(named_fields(text) - fields)
        if missing:
            problems.append(f"{instructions}: the {what} names fields that the state does not have: "
                            + ", ".join(missing))
    return problems


# -- 2. The facts of each move come from the game after the move -------------------------


def after_move_problems(situations=None) -> list[str]:
    """One message for each move fact that does not match the game at the end of the move."""
    situations = check_situations() if situations is None else situations
    problems = []
    for i, s in enumerate(situations):
        state = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried)
        if not isinstance(state["moves"], dict):
            continue
        for name, facts in state["moves"].items():
            after = s.outcomes[name].snapshot
            where = f"situation {i}, {name}"
            expected = describe.movement_words(after.willy_x - s.snap.willy_x, s.snap.willy_y - after.willy_y)
            if facts["movement"] != expected:
                problems.append(f"{where}: movement is '{facts['movement']}', the game after the move gives '{expected}'")
            if ("collects_key" in facts) != (len(after.keys) < len(s.snap.keys)):
                problems.append(f"{where}: collects_key does not agree with the keys after the move")
    return problems


def measurement_problems(settings) -> list[str]:
    """The problems that the request checks find for a measurement with these runner.Settings.

    A rule and random moves do not use the texts, so the text check does not apply to them.
    """
    problems = after_move_problems()[:10]
    if not (settings.rule or settings.random_moves):
        problems = text_problems(settings.instructions) + problems
    return problems


def all_text_problems() -> list[str]:
    return [p for name in instruction_sets() for p in text_problems(name)]


if __name__ == "__main__":
    for problem in all_text_problems() + after_move_problems()[:10]:
        print(problem)
    print("done")
