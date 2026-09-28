"""Checks of the requests to jev. The tests and the measurement tool use them.

1. A text names only fields that its state has. In the texts, a name in back
   quotes is a field of the state (for example `moves` or `target.height`).
   A text that names a field that is not there gives jev wrong information.
2. The facts of each move come from the game after the move. The look-ahead
   plays each move in the emulator and keeps the snapshot at its end, thus
   these facts must agree with that snapshot.

The checks use real situations: the code replays recorded runs, and at each
decision it builds the request states with the same functions as a live run.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from . import describe
from .brain import DEFAULT_INSTRUCTIONS, instruction_sets, key_instructions, move_instructions
from .game import COLS, ROWS, Game, Snapshot
from .runner import DEMO_DIR

# The state settings that each text set needs: (progress_facts, move_facts). A set that is
# not in this table needs the normal state ("route", "full").
TEXT_STATE = {
    "promptA-no-progress": ("none", "full"),
    "promptD-plain": ("plain", "full"),
    "promptM-progress": ("route", "progress"),
    "promptM-progress-goal": ("route", "progress-goal"),
    "promptM-progress-goal-memory": ("route", "progress-goal-memory"),
    "promptM-progress-goal-memory-loop": ("route", "progress-goal-memory"),
    "promptM-pgm-target": ("route", "pgm-target"),
    "promptM-pgm-target-sides": ("route", "pgm-target-sides"),
    "promptM-pgm-target-sides-result": ("route", "pgm-target-sides-result"),
    "promptM-no-guardians": ("route", "no-guardians"),
    "promptM-no-guardians-no-knowledge": ("route", "no-guardians"),
    "promptM-no-guardians-crumbling": ("route", "no-guardians"),
    "promptM-no-guardians-loop": ("route", "no-guardians"),
    "promptM-maps": ("route", "maps"),
    "promptM-maps-progress": ("route", "maps-progress"),
}
# promptC is the text for Laya, which gets its own text form (laya_brain.py), not the JSON state.
NOT_FOR_JEV_STATE = ("promptC",)

# The recorded runs that the checks replay: complete runs of three caverns.
CHECK_RUNS = ("cavern-01-central-cavern-promptA.jsonl", "cavern-02-the-cold-room-promptA.jsonl",
              "cavern-03-the-menagerie-promptA.jsonl")


@dataclass
class Situation:
    """One decision of a recorded run: the game before the move, and the look-ahead."""

    snap: Snapshot
    outcomes: dict
    target: tuple | None
    visited: Counter
    tried: set


def replay_situations(file: str, survival_depth: int = 4) -> list[Situation]:
    """Replay a recorded run. At each move decision, keep the game and the look-ahead."""
    records = [json.loads(line) for line in (DEMO_DIR / file).read_text().splitlines()]
    game = Game()
    game.hold_against_conveyor = records[0].get("macros", 1) >= 2
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
    """The situations of all check runs (the replay takes a few seconds)."""
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


def _key_names(snap: Snapshot) -> dict:
    names = {cell: f"key_{snap.key_letters[cell]}" for cell in snap.keys}
    names.update({cell: f"switch_{i + 1}" for i, cell in enumerate(snap.switches)})
    return names


def text_problems(instructions: str, situations=None, settings: tuple | None = None) -> list[str]:
    """The fields that the texts of a set name, and that its states never have.

    `settings` is (progress_facts, move_facts) of a measurement. If it is not given,
    the check uses the settings of the set in TEXT_STATE.
    """
    if instructions in NOT_FOR_JEV_STATE:
        return []
    progress_facts, move_facts = settings or TEXT_STATE.get(instructions, ("route", "full"))
    situations = check_situations() if situations is None else situations
    move_fields, map_fields, facts_fields = set(), set(), set()
    for s in situations:
        state, _ = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried,
                                               progress_facts, move_facts)
        move_fields |= state_fields(state)
        if s.snap.keys:
            names = _key_names(s.snap)
            # A memory with each field that the key state can have.
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


def _cells(x: int, y: int, size: int = 2):
    return {(x + dx, y + dy) for dx in range(size) for dy in range(size)
            if 0 <= x + dx < COLS and 0 <= y + dy < ROWS}


def after_move_problems(move_facts: str = "full", situations=None) -> list[str]:
    """The facts of a move that do not agree with the game at the end of that move."""
    situations = check_situations() if situations is None else situations
    problems = []
    for i, s in enumerate(situations):
        state, moves = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried,
                                                   "route", move_facts)
        if not isinstance(moves["moves"], dict):
            continue
        for name, facts in moves["moves"].items():
            after = s.outcomes[name].snapshot
            where = f"situation {i}, {name}"
            expected = describe.movement_words(after.willy_x - s.snap.willy_x, s.snap.willy_y - after.willy_y)
            if facts["movement"] != expected:
                problems.append(f"{where}: movement is '{facts['movement']}', the game after the move gives '{expected}'")
            if ("collects_key" in facts) != (len(after.keys) < len(s.snap.keys)):
                problems.append(f"{where}: collects_key does not agree with the keys after the move")
            if not move_facts.startswith("maps"):
                continue
            rows = state["moves"][name]["map_after"]
            willy = _cells(after.willy_x, after.willy_y)
            if any(rows[y][x] != "W" for x, y in willy):
                problems.append(f"{where}: the map does not show Willy where he is after the move")
            covered = set(willy) | _cells(*after.portal)
            for g in after.guardians:
                shown = _cells(g.x, g.y) - covered
                if shown and all(rows[y][x] != "G" for x, y in shown):
                    problems.append(f"{where}: the map does not show a guardian where it is after the move")
            for cell in s.snap.keys:
                x, y = cell
                if cell not in after.keys and rows[y][x] == s.snap.key_letters[cell]:
                    problems.append(f"{where}: the map shows key {s.snap.key_letters[cell]}, which the move collects")
            for (x, y), rows_gone in after.crumbled.items():
                symbol = rows[y][x]
                if symbol in "~-_" and symbol != ("~" if not rows_gone else "_" if rows_gone >= describe.ALMOST_GONE_ROWS else "-"):
                    problems.append(f"{where}: the map shows the wrong condition of the crumbling tile at {x}, {y}")
    return problems


def measurement_problems(settings) -> list[str]:
    """All problems of the requests of a measurement with these Settings (runner.Settings).

    The text check uses the real settings of the measurement. It is not necessary for a
    rule or a random player, because they do not use the move text.
    """
    problems = after_move_problems(settings.move_facts)[:10]
    if not (settings.rule or settings.random_moves):
        problems = text_problems(settings.instructions, None,
                                 (settings.progress_facts, settings.move_facts)) + problems
    return problems


def all_text_problems() -> list[str]:
    return [p for name in instruction_sets() for p in text_problems(name)]


if __name__ == "__main__":
    for problem in all_text_problems() + after_move_problems("full")[:10] + after_move_problems("maps")[:10]:
        print(problem)
    print("done")
