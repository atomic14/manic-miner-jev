"""Live runs and replays.

A live run asks the decision maker (jev, a rule, or another model) for each
decision and writes a log file in `runs/`. A replay reads a log file and plays
the same moves again. The emulator is deterministic, so a replay shows the
same game and makes no jev request.

`play_live` and `play_replay` are async generators. They give a sequence of:
    ("frame", Game)      the screen changed (one game tick)
    ("event", dict)      data for the viewer: header, target, decision, result, end

Log file format: JSON Lines. Line 1 is the header. Then one line for each
decision: a "target" record for a key decision, or a "decision" record for a
move decision, with its result. Forced decisions also get a line. The last
line is the end record.
"""

import json
import random
import re
import time
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from . import describe
from .brain import key_question, move_question, questions_as_json
from .game import ALL_MOVES, MACROS, Game
from .graph import Routes
from .key_orders import OPTIMUM, OPTIMUM_KEY_ORDER
from .settings import Settings

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
# Recorded runs that are in git. A demonstration with them makes no jev request.
DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
USD_PER_TOKEN = 0.042 / 1_000_000  # jev-1.13 price for input tokens

MAX_DECISIONS = 400
# Version 2 of the moves: a fall onto a conveyor, and a wait on one, hold
# against the conveyor.
MACROS_VERSION = 2
# End the run ("stuck: no progress") if Willy visits no new place and collects
# no key in this many decisions, so that a run that goes nowhere stops costing.
STUCK_DECISIONS = 30
# The key decision without the map comes again after this many decisions with
# no new place, and after a change of floor level (if at least
# FLOOR_CHANGE_MIN_GAP decisions have passed since the last one).
GIVE_UP_DECISIONS = 12
FLOOR_CHANGE_MIN_GAP = 4


def is_current(header: dict) -> bool:
    """Is this log file from the present version? The viewer skips older log files,
    because their moves were different (the replay would not match) or their
    settings had older names."""
    return header.get("macros", 1) == MACROS_VERSION and "instructions" in header.get("settings", {})


# -- The list of recorded runs ---------------------------------------------------------

EXAMPLES_GROUP = "examples"
LIVE_GROUP = "live"


def list_runs() -> list[dict]:
    """A summary of each current log file: the examples first, then the others, newest first.

    Each run is in one group: the saved examples (folder demo/), the live
    runs (folder runs/), or one measurement (a folder below runs/).
    """
    runs = []
    paths = sorted(DEMO_DIR.glob("*.jsonl")) + sorted(RUNS_DIR.rglob("*.jsonl"), reverse=True)
    for path in paths:
        lines = path.read_text().splitlines()
        if len(lines) < 2:
            continue
        try:
            header, end = json.loads(lines[0]), json.loads(lines[-1])
        except json.JSONDecodeError:
            continue  # a run that is still writing its last line, or a damaged file
        if not is_current(header):
            continue
        if end.get("type") != "end":
            end = {"outcome": "incomplete", "decisions": len(lines) - 1}
        if path.parent == DEMO_DIR:
            group, file = EXAMPLES_GROUP, path.name
        else:
            file = str(path.relative_to(RUNS_DIR))
            group = LIVE_GROUP if path.parent == RUNS_DIR else str(path.parent.relative_to(RUNS_DIR))
        cavern = header.get("cavern", 0)
        settings = header["settings"]
        runs.append(
            {
                "file": file,
                "group": group,
                "cavern": cavern,
                "cavern_name": header.get("cavern_name", "Central Cavern"),
                "mode": run_mode(header),
                "started": header.get("started"),
                "outcome": end.get("outcome"),
                "decisions": end.get("decisions"),
                "keys_collected": end.get("keys_collected"),
                "keys_total": len(OPTIMUM_KEY_ORDER.get(cavern, "")),
                "cost_usd": end.get("cost_usd"),
                "dead_end_check": settings["survival_depth"],
                "key_map": settings["map_key_decision"],
                "key_order": settings["forced_key_order"],
            }
        )
    return runs


def run_path(file: str) -> Path:
    """The path of a log file: a saved example (demo/) or a file below runs/."""
    path = DEMO_DIR / Path(file).name
    if path.exists():
        return path
    path = (RUNS_DIR / file).resolve()
    if RUNS_DIR.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"not a run file: {file}")
    return path


def read_run(file: str) -> list[dict]:
    """All records of a log file: the header, the decision records, and the end record."""
    return [json.loads(line) for line in run_path(file).read_text().splitlines()]


def run_mode(header: dict) -> str:
    """The run's decision maker, as the viewer shows it (for jev: the instruction set)."""
    settings = header["settings"]
    maker = header.get("decision_maker", "jev")
    if maker != "jev":
        return maker
    if settings.get("random_moves"):
        return "random moves"
    keys = f", key rule: {settings['key_rule']}" if settings.get("key_rule") else ""
    keys += ", no guardian facts" if settings.get("guardian_facts") is False else ""
    if settings.get("rule"):
        return f"rule: {settings['rule']}{keys}"
    return settings["instructions"] + (" sampled" if settings.get("sample_moves") else "") + keys


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


def _goal(f):
    return f.get("completes_cavern") or f.get("collects_key")


def _nearer(f):
    return f.get("progress") == "nearer"


# The rules. Each rule is a sequence of tests. The rule finds the first test
# that at least one move passes, and selects at random from those moves. If no
# move passes a test, it selects at random from all valid moves. The rules use
# only facts that jev also gets.
def _untried(f):
    return f.get("tried_from_here") == "no"


def _nearer_untried(f):
    return _nearer(f) and _untried(f)


RULES = {
    # A move that completes the cavern or collects a key, else a move that goes nearer.
    "nearer": (_goal, _nearer),
    # The same, but it also reads the memory facts: it prefers a move that Willy
    # did not try from this place before.
    "nearer-memory": (_goal, _nearer_untried, _nearer, _untried),
}


def _nearest_key(snap, goals):
    """The key or switch with the smallest distance in cells (across plus up or down) from Willy."""
    return min(goals, key=lambda k: abs(k[0] - snap.willy_x) + abs(k[1] - snap.willy_y))


# Simple key rules for comparison. Each one returns the next target from `goals`.
KEY_RULES = {"nearest": _nearest_key}


def rule_moves(rule: str, offered: list[str], facts: dict) -> list[str]:
    """The moves that a rule from RULES can select."""
    for test in RULES[rule]:
        found = [m for m in offered if isinstance(facts, dict) and test(facts.get(m, {}))]
        if found:
            return found
    return offered


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
        # After the portal, the game can already show the next cavern and its keys.
        "keys_collected": keys_at_start if game.is_complete() else keys_at_start - len(snap.keys),
        "air": round(snap.air, 2),
        "score": snap.score,
    }


def _log_path(folder: str, cavern: int, cavern_name: str, mode: str) -> Path:
    """Example: runs/20260919-151227-cavern-01-central-cavern-promptD.jsonl"""
    runs_dir = RUNS_DIR / folder
    runs_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", cavern_name.lower()).strip("-")
    stem = f"{datetime.now():%Y%m%d-%H%M%S}-cavern-{cavern + 1:02d}-{slug}-{mode}"
    number = 1
    while True:
        # Two runs can start in the same second, also in two processes. The mode "x"
        # creates the file only if it does not exist, so each run gets its own file.
        path = runs_dir / (f"{stem}.jsonl" if number == 1 else f"{stem}-{number}.jsonl")
        try:
            path.open("x").close()
            return path
        except FileExistsError:
            number += 1


class _LiveRun:
    """One live run: its memory, and its key and move decisions."""

    def __init__(self, game: Game, brain, settings: Settings):
        self.game, self.brain, self.settings = game, brain, settings
        first = game.snapshot()
        self.keys_at_start = len(first.keys)
        self.names = describe.key_names(first)
        self.tokens = 0
        self.target = None
        # Willy's memory: the places, and the moves that he made from each one.
        self.visited = Counter({(first.willy_x, first.willy_y): 1})
        self.tried = set()
        # For STUCK_DECISIONS: each (place, keys collected) that Willy reached.
        self.seen = set()
        self.idle = 0
        self.since_new_place = 0
        # The key decision's memory.
        self.used_for = Counter()  # decisions that Willy used on each key as the target
        self.gave_up = Counter()  # times that Willy made no progress toward each key
        self.goals_at_request, self.floor_at_request, self.n_at_request = -1, -1, 0
        # The moves of this run, and its movement graph for the route facts.
        self.moves = ALL_MOVES if settings.half_steps else MACROS
        self.routes = Routes(game, self.moves) if settings.graph_facts else None

    # -- the key decision --

    def _key_decision_is_due(self, snap, goals, n: int) -> bool:
        if not snap.keys:
            return False  # the target is the portal
        if self.target not in goals or len(goals) != self.goals_at_request:
            return True  # the start, or Willy collected a key or flipped a switch
        if self.settings.map_key_decision:
            repeat = self.settings.key_decision_every
            return repeat > 0 and n - self.n_at_request >= repeat
        # Without the map: also after no new place, and after a change of floor level.
        if self.since_new_place >= GIVE_UP_DECISIONS:
            self.gave_up[self.target] += 1
            return True
        floor_changed = snap.willy_y + 2 != self.floor_at_request
        return floor_changed and n - self.n_at_request >= FLOOR_CHANGE_MIN_GAP

    async def key_decision(self, snap, n: int) -> dict | None:
        """Select the target, if a key decision is due. Returns the log record, or None."""
        goals = snap.keys + snap.switches
        options = goals
        if self.settings.forced_key_order:
            by_letter = {snap.key_letters[k]: k for k in snap.keys}
            wanted = next((by_letter[c] for c in self.settings.forced_key_order if c in by_letter), None)
            if wanted is None or wanted == self.target:
                return None
            self.target = wanted
            record = {"type": "target", "n": n, "forced": True, "choice": self.names[wanted],
                      "forced_reason": "the code sets the key order (a test)"}
        else:
            due = self._key_decision_is_due(snap, goals, n)
            if self.settings.no_way_back and snap.keys:
                # The options leave out each goal that is out of reach, and each key
                # that leaves another key out of reach. A target that is out of reach
                # now needs a new key decision, but only if another goal is in reach:
                # else the decision would come again at each move.
                if not due and not self.routes.reachable(snap, self.target):
                    due = any(self.routes.reachable(snap, g) for g in goals)
                options = self.routes.valid_goals(snap, goals) if due else goals
            if not due:
                return None
            if len(options) == 1 or self.settings.key_rule:
                if len(options) == 1:
                    wanted = options[0]
                    reason = "only one key is left" if len(goals) == 1 else "only one key or switch is valid"
                else:
                    wanted = KEY_RULES[self.settings.key_rule](snap, options)
                    reason = f"key rule: {self.settings.key_rule}"
                self.target = wanted
                record = {"type": "target", "n": n, "forced": True, "choice": self.names[wanted],
                          "forced_reason": reason}
            else:
                memory = {"current": self.target, "used": self.used_for, "gave_up": self.gave_up}
                state = describe.key_request_state(snap, self.names, memory, self.settings,
                                                   None if options == goals else options)
                names = [self.names[k] for k in options]
                question = key_question(names, self.settings.instructions, self.settings.map_key_decision)
                answer = await self.brain.ask(state, question, "key")
                self.tokens += answer.input_tokens
                previous = self.target
                self.target = next(k for k in options if self.names[k] == answer.choice)
                record = {"type": "target", "n": n, **answer.to_json(), "kept_target": previous == self.target}
        record["cells"] = {self.names[k]: list(k) for k in options}
        record["target_cell"] = list(self.target)
        self.since_new_place = 0
        self.goals_at_request, self.floor_at_request, self.n_at_request = len(goals), snap.willy_y + 2, n
        return record

    # -- the move decision --

    async def move_decision(self, snap, n: int) -> dict:
        """Select one of the valid moves. Returns the log record."""
        outcomes = self.game.look_ahead(self.settings.survival_depth, self.moves)
        route = None
        if self.routes:
            cell = describe.target_cell(snap, self.target)
            goal = cell if cell in snap.keys + snap.switches else None
            route = self.routes.move_facts(snap, outcomes, goal, self.settings.no_way_back)
        state = describe.move_request_state(snap, outcomes, self.target, self.visited, self.tried, self.settings,
                                            route)
        removed = {} if state["moves_not_offered"] == "none" else state["moves_not_offered"]
        offered = list(state["moves"])
        if not offered:
            # Each move kills Willy. Jev gets all of them, because a Choice
            # question needs options. The log file keeps the causes.
            offered = list(self.moves)
            state["moves"] = "none: no move is safe"
        record = {
            "type": "decision",
            "n": n,
            "tick": self.game.tick_count,
            "offered": offered,
            "removed": removed,
            "no_safe_move": len(removed) == len(self.moves),
            "target_cell": list(describe.target_cell(snap, self.target)),
        }
        if route is not None:
            # For the analysis, not for jev: the moves from Willy's place to the target.
            record["moves_to_target"] = route.now
        if len(offered) == 1:
            # A forced decision. The other moves kill Willy, or give the same
            # game as this move (for example when Willy is in the air).
            macro = offered[0]
            same = any(reason.startswith("no effect") for reason in removed.values())
            reason = "all valid moves have the same result" if same else "only one move is valid"
            record.update(macro=macro, probabilities={macro: 1.0}, confidence=1.0, latency_ms=0,
                          input_tokens=0, model="none", state=state, forced=True, forced_reason=reason)
        elif self.settings.random_moves:
            share = 1 / len(offered)
            record.update(macro=random.choice(offered), probabilities={m: share for m in offered},
                          confidence=0.0, latency_ms=0, input_tokens=0, model="random", state=state)
        elif self.settings.rule:
            best = rule_moves(self.settings.rule, offered, state["moves"])
            share = 1 / len(best)
            record.update(macro=random.choice(best), probabilities={m: share for m in best},
                          confidence=0.0, latency_ms=0, input_tokens=0, model=f"rule-{self.settings.rule}", state=state)
        else:
            question = move_question(offered, self.settings.instructions)
            answer = await self.brain.ask(state, question, "move")
            self.tokens += answer.input_tokens
            data = answer.to_json()
            choice = data.pop("choice")
            if self.settings.sample_moves:
                # Keep jev's own choice in the log, and play a move drawn from its probabilities.
                names = list(data["probabilities"])
                record["jev_choice"] = choice
                choice = random.choices(names, weights=[data["probabilities"][m] for m in names])[0]
            record.update(macro=choice, **data)
        self.tried.add((snap.willy_x, snap.willy_y, record["macro"]))
        if self.target is not None:
            self.used_for[self.target] += 1
        return record

    def remember(self, result: dict):
        """Add the result of a move to Willy's memory."""
        place = tuple(result["willy"])
        self.since_new_place = 0 if place not in self.visited else self.since_new_place + 1
        self.visited[place] += 1
        progress = (*place, result["keys_collected"])
        self.idle = 0 if progress not in self.seen else self.idle + 1
        self.seen.add(progress)


async def play_live(game: Game, brain, cavern: int = 0, settings: Settings | None = None, folder: str = "",
                    show_paths: bool = False):
    """Play one live game. `folder` is a folder below `runs/` for the log file.

    `show_paths` is for the viewer: before each decision, an event gives
    Willy's path for each move. The paths do not go to jev or to the log file.
    """
    settings = settings or Settings()
    if settings.no_way_back and not settings.graph_facts:
        raise ValueError("no_way_back needs graph_facts: the movement graph finds the moves with no way back")
    if settings.forced_key_order == OPTIMUM:
        settings = replace(settings, forced_key_order=OPTIMUM_KEY_ORDER[cavern])
    game.select_cavern(cavern)
    run = _LiveRun(game, brain, settings)
    # A decision maker other than jev has a name (`maker`) and a word for the file name (`mode`).
    maker = getattr(brain, "maker", "jev")
    if settings.random_moves:
        mode = "random"
    elif settings.rule:
        mode = f"rule-{settings.rule}"
    elif maker != "jev":
        mode = brain.mode
    else:
        mode = settings.instructions + ("-sampled" if settings.sample_moves else "")
    if settings.key_rule:
        mode += f"-keys-{settings.key_rule}"
    if not settings.guardian_facts:
        mode += "-no-guardians"
    if settings.move_map:
        mode += "-move-map"
    if settings.ladder_fix:
        mode += "-ladder"
    if not settings.progress_facts:
        mode += "-no-progress"
    if settings.graph_facts:
        mode += "-graph"
    if settings.half_steps:
        mode += "-half-steps"
    if settings.no_way_back:
        mode += "-no-way-back"
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
            key_question(list(run.names.values()), settings.instructions, settings.map_key_decision)
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
                yield "event", {"type": "paths", "n": n, "paths": game.macro_paths(run.moves)}
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
            # The other models count their own cost. Jev's cost comes from the
            # input tokens.
            "cost_usd": round(brain.total_cost if hasattr(brain, "total_cost") else run.tokens * USD_PER_TOKEN, 6),
        }
        if run.routes:
            end["graph_explorations"] = run.routes.explorations
        write(end)
        yield "event", end


# -- A replay --------------------------------------------------------------------------


async def play_replay(game: Game, file: str, show_paths: bool = False, start: int = 0):
    """Replay a log file. `start` is the first decision to show.

    The decisions before `start` play with no frames and no events. The
    emulator is fast, so the viewer can jump to any decision in a run.
    """
    records = read_run(file)
    header = {**records[0], "mode": "replay", "start": start}
    if not is_current(header):
        raise ValueError(f"{file} is a log file of an earlier version")
    game.select_cavern(header.get("cavern", 0))
    keys_at_start = len(game.snapshot().keys)
    moves = ALL_MOVES if header["settings"].get("half_steps") else MACROS
    yield "event", header
    for record in records[1:]:
        if record["type"] == "decision" and record["n"] < start:
            for _ in game.macro_ticks(record["macro"]):
                pass
            continue
        if record["type"] == "end":
            yield "event", record
            return
        if record["type"] != "decision":  # a target record has no macro
            if record.get("n", 0) >= start:
                yield "event", record
            continue
        if record["n"] == start:
            yield "frame", game  # the screen at the first decision that the viewer shows
        logged = record.pop("result", None)
        if show_paths:
            yield "event", {"type": "paths", "n": record["n"], "paths": game.macro_paths(moves)}
        yield "event", record
        first_tick = game.tick_count
        for _ in game.macro_ticks(record["macro"]):
            yield "frame", game
        result = _result(game, record["n"], game.tick_count - first_tick, keys_at_start)
        if logged and logged["willy"] != result["willy"]:
            # The replay did not give the same game as the live run.
            result["replay_mismatch"] = True
        yield "event", result
    yield "event", {"type": "end", "outcome": "incomplete log", "decisions": len(records) - 1}
