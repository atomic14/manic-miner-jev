"""Tests that need no jev calls."""

import asyncio
import json

from jevmanic import describe, runner
from jevmanic.game import Game


def test_start_of_central_cavern():
    snap = Game().snapshot()
    assert snap.cavern_name == "Central Cavern"
    assert (snap.willy_x, snap.willy_y) == (2, 13)
    assert len(snap.keys) == 5
    assert len(snap.guardians) == 1


def test_macros_are_deterministic():
    game = Game()
    positions = []
    for _ in range(2):
        game.restart()
        for name in ["walk_right", "walk_right", "jump_right", "walk_left"]:
            game.run_macro(name)
        snap = game.snapshot()
        positions.append((snap.willy_x, snap.willy_y, snap.guardians[0].x))
    assert positions[0] == positions[1]


def test_all_encoders_give_json():
    snap = Game().snapshot()
    for encode in describe.ENCODERS.values():
        assert json.dumps(encode(snap))


def test_replay_gives_the_logged_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    game = Game()
    lines = [{"type": "header", "encoder": "words", "questions": {}}]
    for n, macro in enumerate(["walk_right", "jump_right"]):
        game.run_macro(macro)
        snap = game.snapshot()
        lines.append({"type": "decision", "n": n, "macro": macro,
                      "result": {"willy": [snap.willy_x, snap.willy_y]}})
    (tmp_path / "run.jsonl").write_text("\n".join(json.dumps(x) for x in lines))

    async def collect():
        return [d async for kind, d in runner.play_replay(game, "run.jsonl") if kind == "event"]

    results = [e for e in asyncio.run(collect()) if e["type"] == "result"]
    assert len(results) == 2
    assert not any(r.get("replay_mismatch") for r in results)


def test_look_ahead_does_not_change_the_game():
    game = Game()
    for name in ["jump_right", "walk_right", "walk_right", "walk_right"]:
        game.run_macro(name)
    before, ticks = game.snapshot(), game.tick_count
    outcomes = game.look_ahead()
    assert game.snapshot() == before
    assert game.tick_count == ticks
    # At this place, a jump to the right goes into the guardian above.
    assert outcomes["jump_right"].dead
    assert not outcomes["walk_left"].dead


def test_moves_state_removes_deadly_macros():
    game = Game()
    for name in ["jump_right", "walk_right", "walk_right", "walk_right"]:
        game.run_macro(name)
    snap = game.snapshot()
    state = describe.moves_state(snap, game.look_ahead(), snap.keys[0], set())
    assert "jump_right" not in state["moves"]
    assert state["moves_that_kill_willy"]["jump_right"].startswith("kills Willy")


def test_cavern_names_come_from_the_game_memory():
    names = Game().cavern_names()
    assert len(names) == 20
    assert names[0] == "Central Cavern"
    assert names[1] == "The Cold Room"
