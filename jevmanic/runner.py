"""Live runs and replays.

A live run asks the decision maker (jev, or an LLM for comparison) for each
decision and writes a log file in `runs/`. A replay reads a log file and runs
the same macros again. The emulator is deterministic, thus a replay shows the
same game and needs no jev calls.

`play_live` and `play_replay` are async generators. They give a sequence of:
    ("frame", Game)      the screen changed (one game tick)
    ("event", dict)      data for the viewer: header, target, decision, result, end

Log file format: JSON Lines. Line 1 is the header. Then one line for each
request: a "target" record (the key decision) or a "decision" record (the move
decision, with its result). The last line is the end record.
"""

import json
import random
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from . import describe
from .brain import DEFAULT_INSTRUCTIONS, key_question, move_question, questions_as_json
from .game import MACROS, SURVIVAL_DEPTH, Game
from .key_orders import OPTIMUM, OPTIMUM_KEY_ORDER

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
# Recorded runs that are in git. Use them for a demonstration without jev calls.
DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
USD_PER_TOKEN = 0.042 / 1_000_000  # jev-1.13 price for input tokens

MAX_DECISIONS = 400
MACROS_VERSION = 2  # 2: a fall onto a conveyor and a wait on it hold against the conveyor
# End the run if Willy visits no new position and collects no key in this
# number of decisions. This prevents cost for a run that goes nowhere.
STUCK_DECISIONS = 30
# The key decision with the facts only: jev gets it again after this number of
# decisions with no new place, and after a change of floor level (with this
# number of decisions or more between two requests).
GIVE_UP_DECISIONS = 12
FLOOR_CHANGE_MIN_GAP = 4


@dataclass
class Settings:
    """The configuration of a live run. The defaults are the normal configuration."""

    # The set of instruction texts: a folder in `jevmanic/instructions/`.
    # "free" (the default): the decisions come from jev. "rules": the texts are
    # lists of rules that we wrote (for comparison). The instructions are the
    # only difference: the state and the schedule of the requests are the same.
    instructions: str = DEFAULT_INSTRUCTIONS
    # The key decision uses the map of the cavern. Jev gets it at the start,
    # when Willy collects a key, and again after `key_decision_every`
    # decisions (0 = no repeat). False = the key decision with the facts only.
    map_key_decision: bool = True
    key_decision_every: int = 25
    # The number of moves that the dead end check looks ahead. 0 = off.
    survival_depth: int = SURVIVAL_DEPTH
    # Research tools. They make no key request or no move request.
    forced_key_order: str = ""  # the code sets the key order, for example "EACDB"
    random_moves: bool = False  # a random choice from the valid moves

    @property
    def uses_map(self) -> bool:
        return self.map_key_decision


# -- The list of recorded runs ---------------------------------------------------------

EXAMPLES_GROUP = "examples"
LIVE_GROUP = "live"


def list_runs() -> list[dict]:
    """The header and end record of each log file, newest first.

    Each run is in one group: the saved examples (folder demo/), the live
    runs (folder runs/), or one measurement (a folder below runs/).
    """
    runs = []
    paths = sorted(DEMO_DIR.glob("*.jsonl")) + sorted(RUNS_DIR.rglob("*.jsonl"), reverse=True)
    for path in paths:
        lines = path.read_text().splitlines()
        if len(lines) < 2:
            continue
        header, end = json.loads(lines[0]), json.loads(lines[-1])
        if end.get("type") != "end":
            end = {"outcome": "incomplete", "decisions": len(lines) - 1}
        if path.parent == DEMO_DIR:
            group, file = EXAMPLES_GROUP, path.name
        else:
            file = str(path.relative_to(RUNS_DIR))
            group = LIVE_GROUP if path.parent == RUNS_DIR else str(path.parent.relative_to(RUNS_DIR))
        runs.append(
            {
                "file": file,
                "group": group,
                "cavern": header.get("cavern", 0),
                "cavern_name": header.get("cavern_name", "Central Cavern"),
                "mode": run_mode(header),
                "started": header.get("started"),
                "outcome": end.get("outcome"),
                "decisions": end.get("decisions"),
                "keys_collected": end.get("keys_collected"),
                "cost_usd": end.get("cost_usd"),
            }
        )
    return runs


def run_mode(header: dict) -> str:
    """The mode of a run in words, also for a log file of an older version."""
    settings = header.get("settings", {})
    maker = header.get("decision_maker", "jev")
    if maker != "jev":
        return maker
    if settings.get("random_moves"):
        return "random moves"
    if "instructions" in settings:
        return f"{settings['instructions']} mode"
    if "rules_mode" in settings:  # a log file from before the instruction files
        return "rules mode" if settings["rules_mode"] else "free mode"
    return "free mode" if settings.get("free_move") else "rules mode"


def list_run_groups(runs: list[dict]) -> list[dict]:
    """The groups of the run list, with a name and an explanation for the viewer."""
    groups = [
        {
            "id": EXAMPLES_GROUP,
            "label": "Saved example runs",
            "description": "Complete runs that are part of the project (folder demo/). "
            "Use them for a demonstration. A replay makes no jev calls.",
        },
        {
            "id": LIVE_GROUP,
            "label": "Your live runs",
            "description": "Runs that you started with 'Start live run' or from the terminal "
            "(folder runs/). Each live run is saved here.",
        },
    ]
    for name in sorted({r["group"] for r in runs} - {EXAMPLES_GROUP, LIVE_GROUP}):
        members = [r for r in runs if r["group"] == name]
        complete = sum(1 for r in members if r["outcome"] == "cavern complete")
        caverns = sorted({r["cavern"] + 1 for r in members})
        groups.append(
            {
                "id": name,
                "label": f"Measurement: {name}",
                "description": f"{len(members)} live runs from the measurement tool, caverns "
                f"{', '.join(map(str, caverns))}. {complete} of {len(members)} are complete "
                f"(folder runs/{name}/). A failed run shows where and why jev failed.",
            }
        )
    for group in groups:
        members = [r for r in runs if r["group"] == group["id"]]
        group["runs"] = len(members)
        group["complete"] = sum(1 for r in members if r["outcome"] == "cavern complete")
    return groups


# -- A live run ------------------------------------------------------------------------


def _outcome(game: Game, decisions: int, idle: int) -> str | None:
    if game.is_complete():
        return "cavern complete"
    if game.is_dead():
        return "Willy died"
    if idle >= STUCK_DECISIONS:
        return "stuck: no progress"
    if decisions >= MAX_DECISIONS:
        return "decision limit"
    return None


def _result(game: Game, n: int, ticks: int, keys_at_start: int) -> dict:
    snap = game.snapshot()
    return {
        "type": "result",
        "n": n,
        "ticks": ticks,
        "willy": [snap.willy_x, snap.willy_y],
        "dead": game.is_dead(),
        "complete": game.is_complete(),
        "keys_collected": keys_at_start - len(snap.keys),
        "air": round(snap.air, 2),
        "score": snap.score,
    }


def _log_path(folder: str, cavern: int, cavern_name: str, mode: str) -> Path:
    """Example: runs/20260919-151227-cavern-01-central-cavern-free.jsonl"""
    runs_dir = RUNS_DIR / folder
    runs_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", cavern_name.lower()).strip("-")
    stem = f"{datetime.now():%Y%m%d-%H%M%S}-cavern-{cavern + 1:02d}-{slug}-{mode}"
    path = runs_dir / f"{stem}.jsonl"
    number = 2
    while path.exists():  # two runs can start in the same second
        path = runs_dir / f"{stem}-{number}.jsonl"
        number += 1
    path.touch()
    return path


class _LiveRun:
    """The memory of one live run, and its two types of decision."""

    def __init__(self, game: Game, brain, settings: Settings):
        self.game, self.brain, self.settings = game, brain, settings
        first = game.snapshot()
        self.keys_at_start = len(first.keys)
        # The name of a key has the letter that the key has on the map.
        self.names = {cell: f"key_{first.key_letters[cell]}" for cell in first.keys}
        self.names.update({cell: f"switch_{i + 1}" for i, cell in enumerate(first.switches)})
        self.tokens = 0
        self.target = None
        # The memory of Willy: the places, and the moves that he tried there.
        self.visited = Counter({(first.willy_x, first.willy_y): 1})
        self.tried = set()
        # For the "no progress" rule: (place, keys collected) that Willy reached.
        self.seen = set()
        self.idle = 0
        self.since_new_place = 0
        # The memory of the key decision.
        self.used_for = Counter()  # decisions that Willy used for each key as the target
        self.gave_up = Counter()  # times that Willy made no progress toward each key
        self.goals_at_request, self.floor_at_request, self.n_at_request = -1, -1, 0

    # -- the key decision --

    def _key_decision_is_due(self, snap, goals, n: int) -> bool:
        if not snap.keys:
            return False  # the target is the portal
        if self.target not in goals or len(goals) != self.goals_at_request:
            return True  # the start, or Willy collected a key or flipped a switch
        if self.settings.uses_map:
            repeat = self.settings.key_decision_every
            return repeat > 0 and n - self.n_at_request >= repeat
        # The facts only: also after no progress, and after a change of floor level.
        if self.since_new_place >= GIVE_UP_DECISIONS:
            self.gave_up[self.target] += 1
            return True
        floor_changed = snap.willy_y + 2 != self.floor_at_request
        return floor_changed and n - self.n_at_request >= FLOOR_CHANGE_MIN_GAP

    async def key_decision(self, snap, n: int) -> dict | None:
        """Select the key that Willy goes to next. Gives the log record, or None."""
        goals = snap.keys + snap.switches
        if self.settings.forced_key_order:
            by_letter = {snap.key_letters[k]: k for k in snap.keys}
            wanted = next((by_letter[c] for c in self.settings.forced_key_order if c in by_letter), None)
            if wanted is None or wanted == self.target:
                return None
            self.target = wanted
            record = {"type": "target", "n": n, "forced": True, "choice": self.names[wanted],
                      "forced_reason": "the code sets the key order (a test)"}
        elif not self._key_decision_is_due(snap, goals, n):
            return None
        elif len(goals) == 1:
            self.target = goals[0]
            record = {"type": "target", "n": n, "forced": True, "choice": self.names[goals[0]],
                      "forced_reason": "only one key is left"}
        else:
            memory = {"current": self.target, "used": self.used_for, "gave_up": self.gave_up}
            state = describe.keys_state(snap, self.names, memory)
            if self.settings.uses_map:
                state = {**describe.cavern_map(snap), **state}
            names = [self.names[k] for k in goals]
            question = key_question(names, self.settings.instructions, self.settings.uses_map)
            answer = await self.brain.ask(state, question, "key")
            self.tokens += answer.input_tokens
            previous = self.target
            self.target = next(k for k in goals if self.names[k] == answer.choice)
            record = {"type": "target", "n": n, **answer.to_json(), "kept_target": previous == self.target}
        record["cells"] = {self.names[k]: list(k) for k in goals}
        record["target_cell"] = list(self.target)
        self.since_new_place = 0
        self.goals_at_request, self.floor_at_request, self.n_at_request = len(goals), snap.willy_y + 2, n
        return record

    # -- the move decision --

    async def move_decision(self, snap, n: int) -> dict:
        """Select one macro from the valid moves. Gives the log record."""
        outcomes = self.game.look_ahead(self.settings.survival_depth)
        moves = describe.moves_state(snap, outcomes, self.target, self.visited, self.tried)
        state = {**describe.words(snap, self.target), **moves}
        removed = {} if moves["moves_not_offered"] == "none" else moves["moves_not_offered"]
        offered = list(moves["moves"])
        if not offered:
            # Each macro kills Willy. Jev gets all of them, because a Choice
            # needs options. The log keeps the causes.
            offered = list(MACROS)
            state["moves"] = "none: no move is safe"
        record = {
            "type": "decision",
            "n": n,
            "tick": self.game.tick_count,
            "offered": offered,
            "removed": removed,
            "no_safe_move": len(removed) == len(MACROS),
            "target_cell": list(describe.target_cell(snap, self.target)),
        }
        same_result = len(offered) > 1 and len(
            {(o.x, o.y, o.keys_collected, o.complete) for m, o in outcomes.items() if m in offered}
        ) == 1
        if len(offered) == 1 or same_result:
            # There is no decision to make: only one macro is valid, or all
            # valid macros have the same result (Willy is in the air).
            macro = "wait" if same_result and "wait" in offered else offered[0]
            reason = "all valid moves have the same result" if same_result else "only one move is valid"
            record.update(macro=macro, probabilities={macro: 1.0}, confidence=1.0, latency_ms=0,
                          input_tokens=0, model="none", state=state, forced=True, forced_reason=reason)
        elif self.settings.random_moves:
            share = 1 / len(offered)
            record.update(macro=random.choice(offered), probabilities={m: share for m in offered},
                          confidence=0.0, latency_ms=0, input_tokens=0, model="random", state=state)
        else:
            question = move_question(offered, self.settings.instructions)
            answer = await self.brain.ask(state, question, "move")
            self.tokens += answer.input_tokens
            data = answer.to_json()
            record.update(macro=data.pop("choice"), **data)
        self.tried.add((snap.willy_x, snap.willy_y, record["macro"]))
        if self.target is not None:
            self.used_for[self.target] += 1
        return record

    def remember(self, result: dict):
        """Update the memory of Willy with the result of a move."""
        place = tuple(result["willy"])
        self.since_new_place = 0 if place not in self.visited else self.since_new_place + 1
        self.visited[place] += 1
        progress = (*place, result["keys_collected"])
        self.idle = 0 if progress not in self.seen else self.idle + 1
        self.seen.add(progress)


async def play_live(game: Game, brain, cavern: int = 0, settings: Settings | None = None, folder: str = "",
                    show_paths: bool = False):
    """Play one live game. `folder` is a folder below `runs/` for the log file.

    `show_paths` is for the viewer: before each decision, an event gives the
    path of Willy for each macro. The paths do not go to jev or to the log file.
    """
    settings = settings or Settings()
    if settings.forced_key_order == OPTIMUM:
        settings = replace(settings, forced_key_order=OPTIMUM_KEY_ORDER[cavern])
    game.hold_against_conveyor = True
    game.select_cavern(cavern)
    run = _LiveRun(game, brain, settings)
    maker = f"claude {brain.model}" if getattr(brain, "model", None) else "jev"
    if settings.random_moves:
        mode = "random"
    elif maker != "jev":
        mode = "llm"
    else:
        mode = settings.instructions
    cavern_name = game.snapshot().cavern_name
    path = _log_path(folder, cavern, cavern_name, mode)
    header = {
        "type": "header",
        "mode": "live",
        "macros": MACROS_VERSION,
        "file": str(path.relative_to(RUNS_DIR)),
        "settings": asdict(settings),
        "decision_maker": maker,
        "cavern": cavern,
        "cavern_name": cavern_name,
        "questions": questions_as_json(move_question(instructions=settings.instructions)),
        "target_questions": questions_as_json(
            key_question(list(run.names.values()), settings.instructions, settings.uses_map)
        ),
        "started": time.time(),
    }
    n, result = 0, {}
    with path.open("w") as log:

        def write(record):
            log.write(json.dumps(record) + "\n")
            log.flush()

        write(header)
        yield "event", header
        yield "frame", game
        while (outcome := _outcome(game, n, run.idle)) is None:
            snap = game.snapshot()
            key_record = await run.key_decision(snap, n)
            if key_record:
                write(key_record)
                yield "event", key_record
            if show_paths:
                yield "event", {"type": "paths", "n": n, "paths": game.macro_paths()}
            record = await run.move_decision(snap, n)
            yield "event", record
            start = game.tick_count
            for _ in game.macro_ticks(record["macro"]):
                yield "frame", game
            result = _result(game, n, game.tick_count - start, run.keys_at_start)
            yield "event", result
            run.remember(result)
            write({**record, "result": result})  # one log line has the decision and its result
            n += 1
        end = {
            "type": "end",
            "outcome": outcome,
            "decisions": n,
            "keys_collected": result.get("keys_collected", 0),
            "input_tokens": run.tokens,
            # An LLM decision maker counts its own cost. For jev, the cost comes
            # from the input tokens.
            "cost_usd": round(getattr(brain, "total_cost", None) or run.tokens * USD_PER_TOKEN, 6),
        }
        write(end)
        yield "event", end


# -- A replay --------------------------------------------------------------------------


async def play_replay(game: Game, file: str, show_paths: bool = False):
    path = DEMO_DIR / Path(file).name
    if not path.exists():
        path = (RUNS_DIR / file).resolve()
        if RUNS_DIR.resolve() not in path.parents:
            raise ValueError(f"not a run file: {file}")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    header = {**records[0], "mode": "replay"}
    # Version 2: a fall onto a conveyor and a wait on it hold against the conveyor.
    game.hold_against_conveyor = header.get("macros", 1) >= 2
    game.select_cavern(header.get("cavern", 0))
    keys_at_start = len(game.snapshot().keys)
    yield "event", header
    yield "frame", game
    for record in records[1:]:
        if record["type"] == "end":
            yield "event", record
            return
        if record["type"] != "decision":  # a target record has no macro
            yield "event", record
            continue
        logged = record.pop("result", None)
        if show_paths:
            yield "event", {"type": "paths", "n": record["n"], "paths": game.macro_paths()}
        yield "event", record
        start = game.tick_count
        for _ in game.macro_ticks(record["macro"]):
            yield "frame", game
        result = _result(game, record["n"], game.tick_count - start, keys_at_start)
        if logged and logged["willy"] != result["willy"]:
            # The replay must give the same game as the live run.
            result["replay_mismatch"] = True
        yield "event", result
    yield "event", {"type": "end", "outcome": "incomplete log", "decisions": len(records) - 1}
