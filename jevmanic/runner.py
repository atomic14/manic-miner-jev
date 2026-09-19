"""Live runs and replays.

A live run asks jev for each decision and writes a log file in `runs/`.
A replay reads a log file and runs the same macros again. The emulator is
deterministic, thus a replay shows the same game and needs no jev calls.

Both functions are async generators. They give a sequence of events:
    ("frame", Game)      the screen changed (one game tick)
    ("event", dict)      data for the viewer: header, decision, result, end

Log file format: JSON Lines. Line 1 is the header. Then one line for each
jev request: a "target" record or a "decision" record. The last line is the
end record.
"""

import json
import re
from collections import Counter
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from . import describe
from .brain import Brain, move_questions, questions_as_json, target_question
from .game import MACROS, SURVIVAL_DEPTH, Game

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
# Recorded runs that are in git. Use them for a demonstration without jev calls.
DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
MAX_DECISIONS = 400
# End the run if Willy visits no new position and collects no key in this
# number of decisions. This prevents cost for a run that goes nowhere.
STUCK_DECISIONS = 30
USD_PER_TOKEN = 0.042 / 1_000_000  # jev-1.13 price for input tokens


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
        # A log file with no settings is from before free mode.
        free_mode = header.get("settings", {}).get("free_move", False)
        runs.append(
            {
                "file": file,
                "group": group,
                "cavern": header.get("cavern", 0),
                "cavern_name": header.get("cavern_name", "Central Cavern"),
                "mode": "free mode" if free_mode else "rules mode",
                "started": header.get("started"),
                "encoder": header.get("encoder"),
                "look_ahead": header.get("look_ahead", False),
                "outcome": end.get("outcome"),
                "decisions": end.get("decisions"),
                "keys_collected": end.get("keys_collected"),
                "cost_usd": end.get("cost_usd"),
            }
        )
    return runs


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


def _outcome(game: Game, decisions: int, idle: int = 0) -> str | None:
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


@dataclass
class Settings:
    """Switches for experiments. The defaults are the normal configuration.

    The normal configuration is free mode: the decisions come from jev. The
    instructions give the goal, the meaning of the facts, and knowledge of the
    game. Rules mode is a decision procedure that we wrote. It is for
    comparison only.
    """

    extra_questions: bool = True  # danger_left, danger_right, threat
    memory: bool = True  # the facts `place` and `tried_from_here`
    survival_depth: int = SURVIVAL_DEPTH  # 0 = no dead end check
    free_target: bool = True  # False = the target question with our preference rules
    free_move: bool = True  # False = the move question with our decision procedure
    brief_text: bool = False  # the free mode text in short sentences (measured: worse)
    # The flexible target: jev gets the target question again when the situation
    # changes, it can keep or change the target, and each key has a short memory.
    flexible_target: bool = True
    # Short-term memory: the last moves and their results. It is off, because a
    # measurement showed that it makes the results worse (see the README).
    recent_moves: bool = False



RECENT_MOVES = 4  # the number of moves in the short-term memory
RETARGET_MIN_GAP = 4  # decisions between two target requests for a floor change
RETARGET_DECISIONS = 12  # select a different key after this number of decisions with no new place


async def play_live(
    game: Game,
    brain: Brain,
    encoder: str,
    look_ahead: bool = False,
    cavern: int = 0,
    settings: Settings | None = None,
    folder: str = "",
):
    """Play one live game. `folder` is a folder below `runs/` for the log file."""
    settings = settings or Settings()
    encode = describe.ENCODERS[encoder]
    runs_dir = RUNS_DIR / folder
    runs_dir.mkdir(parents=True, exist_ok=True)
    mode_name = "lookahead" if look_ahead else "rules"
    game.select_cavern(cavern)
    # Example: 20260919-151227-cavern-01-central-cavern-words-lookahead.jsonl
    cavern_slug = re.sub(r"[^a-z0-9]+", "-", game.snapshot().cavern_name.lower()).strip("-")
    stem = f"{datetime.now():%Y%m%d-%H%M%S}-cavern-{cavern + 1:02d}-{cavern_slug}-{encoder}-{mode_name}"
    path = runs_dir / f"{stem}.jsonl"
    number = 2
    while path.exists():  # two runs can start in the same second
        path = runs_dir / f"{stem}-{number}.jsonl"
        number += 1
    path.touch()
    first = game.snapshot()
    keys_at_start = len(first.keys)
    # Each key keeps one name for the full run.
    key_names = {cell: f"key_{i + 1}" for i, cell in enumerate(first.keys)}
    # A switch is also a target that jev can select.
    key_names.update({cell: f"switch_{i + 1}" for i, cell in enumerate(first.switches)})
    header = {
        "type": "header",
        "mode": "live",
        "file": str(path.relative_to(RUNS_DIR)),
        "settings": asdict(settings),
        "cavern": cavern,
        "cavern_name": game.snapshot().cavern_name,
        "encoder": encoder,
        "look_ahead": look_ahead,
        "questions": questions_as_json(
            move_questions(
                encoder, look_ahead, extras=settings.extra_questions, free=settings.free_move,
                recent=settings.recent_moves, brief=settings.brief_text,
            )
        ),
        "target_questions": questions_as_json(
            target_question(
                list(key_names.values()), settings.free_target, settings.flexible_target, settings.brief_text
            )
        ),
        "started": time.time(),
    }
    tokens = 0
    n = 0
    result = {}
    target = None
    skipped = set()  # keys that Willy could not get to (rigid target only)
    used_for = Counter()  # decisions that Willy used for each key as the target
    gave_up_count = Counter()  # times that Willy made no progress toward each key
    goals_at_request, floor_at_request, n_at_request = -1, -1, 0
    since_new_place = 0
    with path.open("w") as log:

        def write(record):
            log.write(json.dumps(record) + "\n")
            log.flush()

        write(header)
        yield "event", header
        yield "frame", game
        seen = set()  # (position, keys collected) that Willy reached
        # The number of visits of each place. This is the memory of Willy.
        visited = Counter({(first.willy_x, first.willy_y): 1})
        tried = set()  # (position, macro) that Willy selected before
        history = []  # the last moves, for the short-term memory
        idle = 0
        while (outcome := _outcome(game, n, idle)) is None:
            snap = game.snapshot()

            # 1. Target. Jev selects the key.
            goals = snap.keys + snap.switches
            floor_row = snap.willy_y + 2
            gave_up = target is not None and since_new_place >= RETARGET_DECISIONS
            if settings.flexible_target:
                if gave_up and target in goals:
                    gave_up_count[target] += 1
                changed = (
                    len(goals) != goals_at_request  # Willy collected a key or flipped a switch
                    or (floor_row != floor_at_request and n - n_at_request >= RETARGET_MIN_GAP)
                )
                ask = bool(snap.keys) and (target not in goals or gave_up or changed)
                candidates = list(goals)
            else:
                if gave_up:
                    skipped.add(target)
                    target = None
                ask = bool(snap.keys) and target not in goals
                candidates = [k for k in goals if k not in skipped] or list(goals)
            if ask:
                record = {"type": "target", "n": n, "cells": {key_names[k]: list(k) for k in candidates}}
                if len(candidates) == 1:
                    target = candidates[0]
                    record.update(forced=True, choice=key_names[target])
                else:
                    names = [key_names[k] for k in candidates]
                    memory = (
                        {"current": target, "used": used_for, "gave_up": gave_up_count}
                        if settings.flexible_target else None
                    )
                    state = describe.keys_state(
                        replace(
                            snap,
                            keys=[c for c in candidates if c in snap.keys],
                            switches=[c for c in candidates if c in snap.switches],
                        ),
                        key_names,
                        memory,
                    )
                    question = target_question(
                        names, settings.free_target, settings.flexible_target, settings.brief_text
                    )
                    answer = await brain.ask(state, question, "target")
                    tokens += answer.input_tokens
                    previous = target
                    target = next(k for k in candidates if key_names[k] == answer.choice)
                    record.update(answer.to_json())
                    record["kept_target"] = previous == target
                record["target_cell"] = list(target)
                since_new_place = 0
                goals_at_request, floor_at_request, n_at_request = len(goals), floor_row, n
                write(record)
                yield "event", record
            if target is not None:
                used_for[target] += 1

            # 2. Move. Jev selects the macro.
            state = encode(snap, target)
            if settings.recent_moves:
                state = {**state, **describe.recent_state(history)}
            offered, removed = list(MACROS), {}
            if look_ahead:
                outcomes = game.look_ahead(settings.survival_depth)
                extra = describe.moves_state(
                    snap, outcomes, target, visited, tried, settings.memory, not settings.free_move
                )
                safe = list(extra["moves"])
                removed = extra["moves_not_offered"]
                removed = {} if removed == "none" else removed
                if safe:
                    offered = safe
                else:
                    # All macros kill Willy. Jev gets all of them, because a
                    # Choice needs options. The log keeps the causes.
                    extra["moves"] = "none: no move is safe"
                state = {**state, **extra}
            record = {
                "type": "decision",
                "n": n,
                "tick": game.tick_count,
                "offered": offered,
                "removed": removed,
                "no_safe_move": look_ahead and offered == list(MACROS) and len(removed) == len(MACROS),
                "target_cell": list(describe.target_cell(snap, target)),
            }
            same_result = look_ahead and len(offered) > 1 and len(
                {(o.x, o.y, o.keys_collected, o.complete) for m, o in outcomes.items() if m in offered}
            ) == 1
            if len(offered) == 1 or same_result:
                # There is no decision to make: only one macro is valid, or all
                # valid macros have the same result (Willy is in the air).
                macro = "wait" if same_result and "wait" in offered else offered[0]
                record.update(forced=True, macro=macro, probabilities={macro: 1.0},
                              confidence=1.0, latency_ms=0, input_tokens=0, model="none",
                              nouls={}, scores={}, state=state,
                              forced_reason="all valid moves have the same result" if same_result
                              else "only one move is valid")
            else:
                questions = move_questions(
                    encoder, look_ahead, offered, settings.extra_questions, settings.free_move,
                    settings.recent_moves, settings.brief_text,
                )
                answer = await brain.ask(state, questions, "move")
                tokens += answer.input_tokens
                data = answer.to_json()
                record.update(macro=data.pop("choice"), **data)
            yield "event", record
            tried.add((snap.willy_x, snap.willy_y, record["macro"]))
            start = game.tick_count
            for _ in game.macro_ticks(record["macro"]):
                yield "frame", game
            result = _result(game, n, game.tick_count - start, keys_at_start)
            yield "event", result
            history.append(
                {
                    "move": record["macro"],
                    "dx": result["willy"][0] - snap.willy_x,
                    "dy": snap.willy_y - result["willy"][1],
                    "collected_key": result["keys_collected"] > keys_at_start - len(snap.keys),
                }
            )
            del history[:-RECENT_MOVES]
            place = tuple(result["willy"])
            since_new_place = 0 if place not in visited else since_new_place + 1
            visited[place] += 1
            progress = (*place, result["keys_collected"])
            idle = 0 if progress not in seen else idle + 1
            seen.add(progress)
            # One log line has the decision and its result.
            write({**record, "result": result})
            n += 1
        end = {
            "type": "end",
            "outcome": outcome,
            "decisions": n,
            "keys_collected": result.get("keys_collected", 0),
            "input_tokens": tokens,
            "cost_usd": round(tokens * USD_PER_TOKEN, 6),
        }
        write(end)
        yield "event", end


async def play_replay(game: Game, file: str):
    path = DEMO_DIR / Path(file).name
    if not path.exists():
        path = (RUNS_DIR / file).resolve()
        if RUNS_DIR.resolve() not in path.parents:
            raise ValueError(f"not a run file: {file}")
    lines = path.read_text().splitlines()
    records = [json.loads(line) for line in lines]
    header = {**records[0], "mode": "replay"}
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

