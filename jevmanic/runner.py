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
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from . import describe
from .brain import Brain, move_questions, questions_as_json, target_question
from .game import MACROS, Game

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
# Recorded runs that are in git. Use them for a demonstration without jev calls.
DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
MAX_DECISIONS = 400
# End the run if Willy visits no new position and collects no key in this
# number of decisions. This prevents cost for a run that goes nowhere.
STUCK_DECISIONS = 30
USD_PER_TOKEN = 0.042 / 1_000_000  # jev-1.13 price for input tokens


def list_runs() -> list[dict]:
    """The header and end record of each log file, newest first."""
    runs = []
    paths = sorted(DEMO_DIR.glob("*.jsonl")) + sorted(RUNS_DIR.glob("*.jsonl"), reverse=True)
    for path in paths:
        lines = path.read_text().splitlines()
        if len(lines) < 2:
            continue
        header, end = json.loads(lines[0]), json.loads(lines[-1])
        if end.get("type") != "end":
            end = {"outcome": "incomplete", "decisions": len(lines) - 1}
        runs.append(
            {
                "file": path.name,
                "cavern": header.get("cavern", 0),
                "encoder": header.get("encoder"),
                "look_ahead": header.get("look_ahead", False),
                "outcome": end.get("outcome"),
                "decisions": end.get("decisions"),
                "keys_collected": end.get("keys_collected"),
                "cost_usd": end.get("cost_usd"),
            }
        )
    return runs


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


RETARGET_DECISIONS = 12  # select a different key after this number of decisions with no new place


async def play_live(game: Game, brain: Brain, encoder: str, look_ahead: bool = False, cavern: int = 0):
    encode = describe.ENCODERS[encoder]
    RUNS_DIR.mkdir(exist_ok=True)
    mode_name = "lookahead" if look_ahead else "rules"
    game.select_cavern(cavern)
    # Example: 20260919-151227-cavern-01-central-cavern-words-lookahead.jsonl
    cavern_slug = re.sub(r"[^a-z0-9]+", "-", game.snapshot().cavern_name.lower()).strip("-")
    path = RUNS_DIR / (
        f"{datetime.now():%Y%m%d-%H%M%S}-cavern-{cavern + 1:02d}-{cavern_slug}-{encoder}-{mode_name}.jsonl"
    )
    first = game.snapshot()
    keys_at_start = len(first.keys)
    # Each key keeps one name for the full run.
    key_names = {cell: f"key_{i + 1}" for i, cell in enumerate(first.keys)}
    header = {
        "type": "header",
        "mode": "live",
        "file": path.name,
        "cavern": cavern,
        "cavern_name": game.snapshot().cavern_name,
        "encoder": encoder,
        "look_ahead": look_ahead,
        "questions": questions_as_json(move_questions(encoder, look_ahead)),
        "target_questions": questions_as_json(target_question(list(key_names.values()))),
        "started": time.time(),
    }
    tokens = 0
    n = 0
    result = {}
    target = None
    skipped = set()  # keys that Willy could not get to
    since_new_place = 0
    with path.open("w") as log:

        def write(record):
            log.write(json.dumps(record) + "\n")
            log.flush()

        write(header)
        yield "event", header
        yield "frame", game
        seen = set()  # (position, keys collected) that Willy reached
        visited = {(first.willy_x, first.willy_y)}
        tried = set()  # (position, macro) that Willy selected before
        idle = 0
        while (outcome := _outcome(game, n, idle)) is None:
            snap = game.snapshot()

            # 1. Target. Jev selects the key.
            if target is not None and since_new_place >= RETARGET_DECISIONS:
                skipped.add(target)
                target = None
            if snap.keys and target not in snap.keys:
                candidates = [k for k in snap.keys if k not in skipped] or list(snap.keys)
                record = {"type": "target", "n": n, "cells": {key_names[k]: list(k) for k in candidates}}
                if len(candidates) == 1:
                    target = candidates[0]
                    record.update(forced=True, choice=key_names[target])
                else:
                    names = [key_names[k] for k in candidates]
                    state = describe.keys_state(replace(snap, keys=candidates), key_names)
                    answer = await brain.ask(state, target_question(names), "target")
                    tokens += answer.input_tokens
                    target = next(k for k in candidates if key_names[k] == answer.choice)
                    record.update(answer.to_json())
                record["target_cell"] = list(target)
                since_new_place = 0
                write(record)
                yield "event", record

            # 2. Move. Jev selects the macro.
            state = encode(snap, target)
            offered, removed = list(MACROS), {}
            if look_ahead:
                extra = describe.moves_state(snap, game.look_ahead(), target, visited, tried)
                safe = list(extra["moves"])
                removed = extra["moves_that_kill_willy"]
                removed = {} if removed == "none" else removed
                if safe:
                    offered = safe
                else:
                    # All macros kill Willy. Jev gets all of them, because a
                    # Choice needs options. The log keeps the causes.
                    extra["moves"] = "none: all moves kill Willy"
                state = {**state, **extra}
            record = {
                "type": "decision",
                "n": n,
                "tick": game.tick_count,
                "offered": offered,
                "removed": removed,
                "no_safe_move": look_ahead and len(removed) == len(MACROS),
                "target_cell": list(describe.target_cell(snap, target)),
            }
            if len(offered) == 1:
                # Only one macro is safe. A jev call is not necessary.
                record.update(forced=True, macro=offered[0], probabilities={offered[0]: 1.0},
                              confidence=1.0, latency_ms=0, input_tokens=0, model="none",
                              nouls={}, scores={}, state=state)
            else:
                answer = await brain.ask(state, move_questions(encoder, look_ahead, offered), "move")
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
            place = tuple(result["willy"])
            since_new_place = 0 if place not in visited else since_new_place + 1
            visited.add(place)
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
    name = Path(file).name
    path = DEMO_DIR / name if (DEMO_DIR / name).exists() else RUNS_DIR / name
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
        if record["type"] == "target":
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

