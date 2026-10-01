"""The request checks: tests of what jev gets. The tests and the measurement tool run them.

1. A text names only fields that its state has. In the texts, a name in back
   quotes is a state field (for example `moves` or `target.height`). A text
   that names a missing field gives jev wrong information.
2. Each move's facts agree with the game after the move. The look-ahead plays
   each move in the emulator and keeps the snapshot at its end, so the facts
   must match that snapshot.
3. The move filter and the navigation facts agree with the look-ahead: a
   move is removed only for its stated cause, two offered moves never give
   the same game, and a target on "the same level" is within jump reach.

The checks use real situations: they replay recorded runs, and at each
decision they build the states with the same functions and settings as a
live run. They also replay recorded failure states from each cavern
(`tests/fixtures/`), because the complete runs reach only the places where
the harness works.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache

from . import describe
from .brain import instruction_sets, key_instructions, move_instructions
from .game import ALL_MOVES, HALF_STEPS, MACROS, SURVIVAL_DEPTH, Game, Snapshot
from .runner import DEMO_DIR
from .settings import Settings

# promptC is the set for Laya. Laya gets sentences (laya_brain.py), not the JSON state.
NOT_FOR_JEV_STATE = ("promptC",)

# The recorded runs that the checks replay: complete runs of three caverns.
CHECK_RUNS = ("cavern-01-central-cavern-promptA.jsonl", "cavern-02-the-cold-room-promptA.jsonl",
              "cavern-03-the-menagerie-promptA.jsonl")
# Single states from failed runs: each has the moves up to one decision, and its target.
STATES_DIR = DEMO_DIR.parent / "tests" / "fixtures"
STATE_FILES = ("review_states.json", "failure_states.json")


@dataclass
class Situation:
    """One move decision from a recorded run: the game before the move, and the look-ahead."""

    snap: Snapshot
    outcomes: dict
    target: tuple | None
    visited: Counter
    tried: set


def _replay(cavern: int, moves: list, targets: list, last_only: bool, survival_depth: int,
            half_steps: bool = False) -> list[Situation]:
    """Play `moves`, and keep a Situation before each move (or only after the last move).

    `targets` has the target cell of each decision, and one more for the last situation.
    """
    game = Game()
    game.select_cavern(cavern)
    visited, tried, found = Counter(), set(), []
    move_set = ALL_MOVES if half_steps else MACROS

    def situation(cell):
        snap = game.snapshot()
        target = tuple(cell) if tuple(cell) in snap.keys + snap.switches else None
        return Situation(snap, game.look_ahead(survival_depth, move_set), target, Counter(visited), set(tried))

    for macro, cell in zip(moves, targets):
        snap = game.snapshot()
        if not last_only:
            found.append(situation(cell))
        tried.add((snap.willy_x, snap.willy_y, macro))
        game.run_macro(macro)
        after = game.snapshot()
        visited[(after.willy_x, after.willy_y)] += 1
    if last_only:
        found.append(situation(targets[-1]))
    return found


def replay_situations(file: str, survival_depth: int = SURVIVAL_DEPTH, half_steps: bool = False) -> list[Situation]:
    """Replay a recorded run from demo/, and keep a Situation for each move decision."""
    records = [json.loads(line) for line in (DEMO_DIR / file).read_text().splitlines()]
    decisions = [r for r in records[1:] if r["type"] == "decision"]
    return _replay(records[0].get("cavern", 0), [d["macro"] for d in decisions],
                   [d["target_cell"] for d in decisions], False, survival_depth, half_steps)


def state_situations(file: str, survival_depth: int = SURVIVAL_DEPTH, half_steps: bool = False) -> list[Situation]:
    """The recorded states in one file of STATES_DIR: one Situation for each."""
    found = []
    for state in json.loads((STATES_DIR / file).read_text()):
        # The replay has no target for the earlier moves, so each one uses the last target.
        targets = [state["target"]] * (len(state["moves"]) + 1)
        found += _replay(state["cavern"], state["moves"], targets, True, survival_depth, half_steps)
    return found


@cache
def check_situations(survival_depth: int = SURVIVAL_DEPTH, half_steps: bool = False) -> tuple[Situation, ...]:
    """The situations from all CHECK_RUNS and STATE_FILES. Cached, because the replay takes a few seconds."""
    runs = [s for file in CHECK_RUNS for s in replay_situations(file, survival_depth, half_steps)]
    states = [s for file in STATE_FILES for s in state_situations(file, survival_depth, half_steps)]
    return tuple(runs + states)


def situations_for(settings: Settings) -> tuple[Situation, ...]:
    """The situations, with the look-ahead that a run with these settings uses.

    The route facts of the movement graph (`graph_facts`) are not in these
    states: a graph takes seconds for each situation. tests/test_graph.py checks them.
    """
    return check_situations(settings.survival_depth, settings.half_steps)


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


def text_problems(settings: Settings, situations=None) -> list[str]:
    """One message for each text of a run that names fields that its states never have.

    The states come from the run's settings, so a setting that removes a field
    (for example `--no-progress-facts`) makes a text that names it fail.
    """
    instructions = settings.instructions
    if instructions in NOT_FOR_JEV_STATE:
        return []
    situations = situations_for(settings) if situations is None else situations
    move_fields, key_fields = set(), set()
    for s in situations:
        move_fields |= state_fields(describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried,
                                                                settings))
        if s.snap.keys:
            names = describe.key_names(s.snap)
            # A memory that makes the key state have every optional field.
            first = s.snap.keys[0]
            memory = {"current": first, "used": {first: 3}, "gave_up": {first: 1}}
            key_fields |= state_fields(describe.key_request_state(s.snap, names, memory, settings))
    with_map = settings.map_key_decision
    problems = []
    for what, text, fields in (
        ("move text", move_instructions(instructions), move_fields),
        (f"key text ({'with the map' if with_map else 'facts only'})", key_instructions(instructions, with_map),
         key_fields),
    ):
        missing = sorted(named_fields(text) - fields)
        if missing:
            problems.append(f"{instructions}: the {what} names fields that the state does not have: "
                            + ", ".join(missing))
    return problems


# -- 2. The facts of each move come from the game after the move -------------------------


def after_move_problems(situations=None, settings: Settings | None = None) -> list[str]:
    """One message for each move fact that does not match the game at the end of the move."""
    settings = settings or Settings()
    situations = situations_for(settings) if situations is None else situations
    problems = []
    for i, s in enumerate(situations):
        state = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried, settings)
        if not isinstance(state["moves"], dict):
            continue
        for name, facts in state["moves"].items():
            after = s.outcomes[name].snapshot
            where = f"situation {i}, {name}"
            half = s.outcomes[name].dx_pixels if name in HALF_STEPS else None
            expected = describe.movement_words(after.willy_x - s.snap.willy_x, s.snap.willy_y - after.willy_y, half)
            if facts["movement"] != expected:
                problems.append(f"{where}: movement is '{facts['movement']}', the game after the move gives '{expected}'")
            if ("collects_key" in facts) != (len(after.keys) < len(s.snap.keys)):
                problems.append(f"{where}: collects_key does not agree with the keys after the move")
    return problems


# -- 3. The move filter and the navigation facts agree with the look-ahead ------------------


def filter_problems(situations=None, settings: Settings | None = None) -> list[str]:
    """One message for each removed move, offered move, or target height that the look-ahead contradicts."""
    settings = settings or Settings()
    situations = situations_for(settings) if situations is None else situations
    problems = []
    for i, s in enumerate(situations):
        state = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried, settings)
        offered = list(state["moves"]) if isinstance(state["moves"], dict) else []
        removed = state["moves_not_offered"] if isinstance(state["moves_not_offered"], dict) else {}
        for name, reason in removed.items():
            o = s.outcomes[name]
            if reason.startswith("kills Willy") and not o.dead:
                problems.append(f"situation {i}, {name}: removed as deadly, but Willy is alive after it")
            if reason.startswith("no effect"):
                other = reason.rsplit(" ", 1)[-1]
                if other not in offered or not o.same_result(s.outcomes[other]):
                    problems.append(f"situation {i}, {name}: removed with '{reason}', but that is not true")
        for n, a in enumerate(offered):
            for b in offered[n + 1:]:
                if s.outcomes[a].same_result(s.outcomes[b]):
                    problems.append(f"situation {i}: {a} and {b} are both offered, but give the same game")
        target = state["target"]
        if target.get("height") == "same level" and not s.snap.airborne:
            x, y = describe.target_cell(s.snap, s.target)
            bottom = y + (0 if s.snap.keys else 1)
            if bottom < s.snap.willy_y - describe.MAX_JUMP_REACH_ROWS:
                problems.append(f"situation {i}: the target is on the same level, but a jump does not reach it")
    return problems


def measurement_problems(settings: Settings) -> list[str]:
    """The problems that the request checks find for a measurement with these settings.

    A rule and random moves do not use the texts, so the text check does not apply to them.
    """
    problems = (after_move_problems(settings=settings) + filter_problems(settings=settings))[:10]
    if not (settings.rule or settings.random_moves):
        problems = text_problems(settings) + problems
    return problems


def all_text_problems() -> list[str]:
    """The text check for each instruction set, with the key decision with and without the map."""
    return [p for name in instruction_sets() for with_map in (True, False)
            for p in text_problems(Settings(instructions=name, map_key_decision=with_map))]


if __name__ == "__main__":
    for problem in all_text_problems() + after_move_problems()[:10] + filter_problems()[:10]:
        print(problem)
    print("done")
