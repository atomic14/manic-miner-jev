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
    assert state["moves_not_offered"]["jump_right"].startswith("kills Willy")


def test_cavern_names_come_from_the_game_memory():
    names = Game().cavern_names()
    assert len(names) == 20
    assert names[0] == "Central Cavern"
    assert names[1] == "The Cold Room"


def test_moves_with_no_effect_are_not_offered():
    game = Game()  # at the start, Willy is next to the left wall and no guardian is near
    snap = game.snapshot()
    state = describe.moves_state(snap, game.look_ahead(), snap.keys[0], set())
    assert state["moves_not_offered"]["jump_up"].startswith("no effect")
    assert state["moves_not_offered"]["wait"].startswith("no effect")
    assert "walk_right" in state["moves"]


def test_switches_and_vertical_guardians_are_in_the_snapshot():
    game = Game(cavern=7)  # Miner Willy meets the Kong Beast
    assert game.snapshot().switches == [(6, 0), (18, 0)]
    game.select_cavern(8)  # Wacky Amoebatrons
    vertical = [g for g in game.snapshot().guardians if g.axis == "vertical"]
    assert len(vertical) == 4
    state = describe.words(game.snapshot(), game.snapshot().keys[0])
    assert any("vertical guardian" in g.get("type", "") for g in state["guardians"])


def test_extra_tile_is_a_floor_in_the_endorian_forest():
    game = Game(cavern=9)
    assert set(game.snapshot().tiles[15]) == {"="}  # the full bottom row is floor


def test_harmless_moves_stay_when_all_other_moves_kill_willy():
    from jevmanic.game import MACROS, Outcome

    snap = Game().snapshot()
    dead = Outcome(True, "nasty", False, 1, 0, 0, 4, snap.willy_x + 1, snap.willy_y)
    still = Outcome(False, "", False, 0, 0, 0, 4, snap.willy_x, snap.willy_y)
    outcomes = {name: (still if name in ("wait", "jump_up") else dead) for name in MACROS}
    state = describe.moves_state(snap, outcomes, snap.keys[0], set())
    # Jev must get the 2 harmless moves, and no move that kills Willy.
    assert set(state["moves"]) == {"wait", "jump_up"}
    assert all(v.startswith("kills Willy") for v in state["moves_not_offered"].values())


def test_dead_end_moves_stay_when_no_move_is_safe():
    from jevmanic.game import DEAD_END_CAUSE, MACROS, Outcome

    snap = Game().snapshot()
    kills = Outcome(True, "guardian", False, 1, 0, 0, 4, snap.willy_x + 1, snap.willy_y)
    dead_end = Outcome(True, DEAD_END_CAUSE, False, -1, 0, 0, 4, snap.willy_x - 1, snap.willy_y)
    outcomes = {name: (dead_end if name == "walk_left" else kills) for name in MACROS}
    state = describe.moves_state(snap, outcomes, snap.keys[0], set())
    assert set(state["moves"]) == {"walk_left"}
    assert "dead end" in state["moves"]["walk_left"]["warning"]


def test_short_term_memory_in_words():
    history = [
        {"move": "jump_left", "dx": -1, "dy": 2, "collected_key": False},
        {"move": "jump_up", "dx": 0, "dy": 0, "collected_key": True},
    ]
    state = describe.recent_state(history)
    assert state["recent_moves"][0] == {
        "move": "jump_left", "result": "Willy moved 1 cells to the left and 2 rows higher"}
    assert state["recent_moves"][1]["result"] == "Willy stayed in the same place and collected a key"
    # Willy went left and up, thus he came from the right and from a lower place.
    assert state["came_from"] == {"side": "right", "height": "lower"}
    assert describe.recent_state([])["recent_moves"].startswith("none")


def test_target_state_has_a_short_memory_for_each_key():
    snap = Game().snapshot()
    names = {k: f"key_{i + 1}" for i, k in enumerate(snap.keys)}
    memory = {"current": snap.keys[0], "used": {snap.keys[0]: 25}, "gave_up": {snap.keys[0]: 2}}
    keys = describe.keys_state(snap, names, memory)["keys"]
    assert keys["key_1"]["current_target"] == "yes"
    assert keys["key_1"]["decisions_used_for_it"] == "many"
    assert keys["key_1"]["gave_up_on_it"] == "2 times"
    assert "current_target" not in keys["key_2"]
    assert keys["key_2"]["decisions_used_for_it"] == "none"


def test_the_normal_questions_use_the_long_free_mode_text():
    from jevmanic import brain

    move = brain.move_questions("words", True, free=True)["move"].instructions
    assert move == brain.FREE_MOVE_INSTRUCTIONS
    assert brain.move_questions("words", True, free=True, brief=True)["move"].instructions == (
        brain.BRIEF_FREE_MOVE_INSTRUCTIONS)
    target = brain.target_question(["key_1", "key_2"], free=True, memory=True)["target"].instructions
    assert target == brain.FREE_TARGET_INSTRUCTIONS + brain.TARGET_MEMORY_MEANING
    rules = brain.move_questions("words", True, free=False)["move"].instructions
    assert rules == brain.LOOK_AHEAD_INSTRUCTIONS
