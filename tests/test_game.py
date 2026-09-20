"""Tests that need no jev calls."""

import asyncio
import json
from collections import Counter
from dataclasses import fields, replace

from jevmanic import brain, describe, runner
from jevmanic.game import DEAD_END_CAUSE, MACROS, Game, Outcome
from jevmanic.llm_brain import build_prompt, parse_choice
from jevmanic.runner import Settings

# -- The game layer -----------------------------------------------------------------------


def test_start_of_central_cavern():
    snap = Game().snapshot()
    assert snap.cavern_name == "Central Cavern"
    assert (snap.willy_x, snap.willy_y) == (2, 13)
    assert len(snap.keys) == 5
    assert len(snap.guardians) == 1


def test_cavern_names_come_from_the_game_memory():
    names = Game().cavern_names()
    assert len(names) == 20
    assert names[0] == "Central Cavern"
    assert names[1] == "The Cold Room"


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


def test_switches_vertical_guardians_and_the_extra_floor_tile():
    game = Game(cavern=7)  # Miner Willy meets the Kong Beast
    assert game.snapshot().switches == [(6, 0), (18, 0)]
    game.select_cavern(8)  # Wacky Amoebatrons
    snap = game.snapshot()
    assert len([g for g in snap.guardians if g.axis == "vertical"]) == 4
    # The facts describe the horizontal guardians only (see describe._horizontal_guardians).
    assert len(describe.words(snap, snap.keys[0])["guardians"]) == 2
    game.select_cavern(9)  # The Endorian Forest: the extra tile is a floor
    assert set(game.snapshot().tiles[15]) == {"="}


def test_the_look_ahead_does_not_write_over_the_start_of_a_cavern():
    from jevmanic.game import CAVERN_SLOT_BASE, DEAD_END_SLOT, LOOK_AHEAD_SLOT, SURVIVAL_DEPTH

    assert max(LOOK_AHEAD_SLOT, DEAD_END_SLOT + 20) < CAVERN_SLOT_BASE  # 20 = the largest depth of the viewer
    game = Game()
    start = game.snapshot()
    for name in ["jump_right", "walk_right", "walk_right"]:
        game.run_macro(name)
        game.look_ahead(SURVIVAL_DEPTH)
    game.restart()
    assert game.snapshot() == start


def test_willy_stands_still_on_a_conveyor_after_a_drop_with_the_hold():
    from jevmanic.game import JOY_LEFT, JOY_RIGHT

    def drop_onto_the_conveyor(game):
        # Central Cavern: to the top of the wall that is above the conveyor.
        route = (  # from a recorded run
            ["jump_right"] * 2 + ["walk_left"] * 1 + ["jump_right"] * 1 + ["walk_right"] * 5 + ["jump_right"] * 1 + ["walk_right"] * 2 + ["jump_right"] * 3 + ["jump_left"] * 1 + ["wait"] * 2 + ["jump_left"] * 1 + ["wait"] * 1
        )
        for name in route:
            game.run_macro(name)
        assert game.snapshot().willy_y == 6  # on top of the wall
        while game.snapshot().willy_y != 7 and not game.is_dead():
            game.run_macro("walk_left")
        x = game.snapshot().willy_x
        game.run_macro("wait")
        return x - game.snapshot().willy_x

    assert JOY_LEFT != JOY_RIGHT
    game = Game()
    assert drop_onto_the_conveyor(game) == 0  # the wait holds against the conveyor
    game = Game()
    game.hold_against_conveyor = False  # the macros of the old log files
    assert drop_onto_the_conveyor(game) == 1  # the conveyor carries Willy


# -- The state ----------------------------------------------------------------------------


def test_the_map_has_key_letters_conveyor_direction_and_a_legend():
    game = Game()  # Central Cavern: 5 keys, and a conveyor that moves Willy to the left
    snap = game.snapshot()
    full = describe.cavern_map(snap)
    text = "".join(full["map"])
    assert all(letter in text for letter in "ABCDE") and "K" not in text
    assert "<" in text and ">" not in text and "c" not in text
    assert set(full["map_legend"]) == set(text)  # one legend entry for each symbol on the map
    game.select_cavern(1)  # The Cold Room: the conveyor moves Willy to the right
    assert ">" in "".join(describe.cavern_map(game.snapshot())["map"])


def test_key_facts_have_a_short_memory():
    snap = Game().snapshot()
    names = {k: f"key_{snap.key_letters[k]}" for k in snap.keys}
    memory = {"current": snap.keys[0], "used": {snap.keys[0]: 25}, "gave_up": {snap.keys[0]: 2}}
    keys = describe.keys_state(snap, names, memory)["keys"]
    assert keys["key_A"]["current_target"] == "yes"
    assert keys["key_A"]["decisions_used_for_it"] == "many"
    assert keys["key_A"]["gave_up_on_it"] == "2 times"
    assert "current_target" not in keys["key_B"]
    assert keys["key_B"]["decisions_used_for_it"] == "none"
    assert json.dumps(describe.words(snap, snap.keys[0]))


def _moves(snap, outcomes, target=None):
    return describe.moves_state(snap, outcomes, target if target else snap.keys[0], Counter())


def test_a_move_that_kills_willy_is_not_offered():
    game = Game()
    for name in ["jump_right", "walk_right", "walk_right", "walk_right"]:
        game.run_macro(name)
    snap = game.snapshot()
    state = _moves(snap, game.look_ahead())
    assert "jump_right" not in state["moves"]
    assert state["moves_not_offered"]["jump_right"].startswith("kills Willy")


def test_a_move_with_no_effect_is_not_offered():
    game = Game()  # at the start, Willy is next to the left wall and no guardian is near
    snap = game.snapshot()
    state = _moves(snap, game.look_ahead())
    assert state["moves_not_offered"]["jump_up"].startswith("no effect")
    assert state["moves_not_offered"]["wait"].startswith("no effect")
    assert "walk_right" in state["moves"]


def test_harmless_moves_stay_when_all_other_moves_kill_willy():
    snap = Game().snapshot()
    dead = Outcome(True, "nasty", False, 1, 0, 0, 4, snap.willy_x + 1, snap.willy_y)
    still = Outcome(False, "", False, 0, 0, 0, 4, snap.willy_x, snap.willy_y)
    state = _moves(snap, {name: (still if name in ("wait", "jump_up") else dead) for name in MACROS})
    assert set(state["moves"]) == {"wait", "jump_up"}
    assert all(v.startswith("kills Willy") for v in state["moves_not_offered"].values())


def test_dead_end_moves_stay_when_no_move_is_safe():
    snap = Game().snapshot()
    kills = Outcome(True, "guardian", False, 1, 0, 0, 4, snap.willy_x + 1, snap.willy_y)
    dead_end = Outcome(True, DEAD_END_CAUSE, False, -1, 0, 0, 4, snap.willy_x - 1, snap.willy_y)
    state = _moves(snap, {name: (dead_end if name == "walk_left" else kills) for name in MACROS})
    assert set(state["moves"]) == {"walk_left"}
    assert "dead end" in state["moves"]["walk_left"]["warning"]


def test_the_state_and_the_progress_measure_use_the_same_way():
    base = Game(cavern=5).snapshot()  # Processing Plant: the first key is directly below the start
    target = (15, 6)
    for x in (15, 16):  # one step of Willy must not make the two disagree
        snap = replace(base, willy_x=x)
        way = describe.words(snap, target)["target"]["way_down"]
        reference, name = describe._progress_reference(snap, target)
        assert name.endswith("way down") and way["side"] in ("left", "right")
        assert ("left" if reference[0] < snap.willy_x else "right") == way["side"]


def test_on_a_crumbling_floor_the_way_down_is_the_safe_fall_nearest_to_the_target():
    top = replace(Game().snapshot(), willy_y=3, keys=[])  # Central Cavern, all keys collected
    # Only column 19 is safe: a nasty is below columns 20 and 21.
    assert describe._way_down(replace(top, willy_x=19), "right", 29)["side"] == "Willy stands on it"
    assert describe._progress_reference(replace(top, willy_x=19), None)[0] == (19, 3)
    assert describe._way_down(replace(top, willy_x=18), "right", 29)["cell"] == (19, 3)
    # The Menagerie: the long crumbling floor, and the last key below its right end.
    floor = replace(Game(cavern=2).snapshot(), willy_x=29, willy_y=3, keys=[(30, 6)])
    assert describe._way_down(floor, "right", 30)["side"] == "Willy stands on it"
    assert describe._way_down(replace(floor, willy_x=28), "right", 30)["cell"] == (29, 3)


def test_a_way_down_is_not_a_drop_that_kills_willy():
    snap = Game(cavern=5).snapshot()  # the start platform of Processing Plant is 5 rows above the floor
    assert not describe._fall_is_safe(snap, 13, snap.willy_y + 2)


# -- The questions ------------------------------------------------------------------------


def test_each_mode_uses_its_text():
    assert brain.move_question()["move"].instructions == brain.FREE_MOVE_INSTRUCTIONS
    assert brain.move_question(rules_mode=True)["move"].instructions == brain.RULES_MOVE_INSTRUCTIONS
    names = ["key_A", "key_B"]
    memory = brain.KEY_MEMORY_MEANING
    assert brain.key_question(names)["key"].instructions == brain.MAP_KEY_INSTRUCTIONS + memory
    assert brain.key_question(names, with_map=False)["key"].instructions == brain.FACTS_KEY_INSTRUCTIONS + memory
    assert brain.key_question(names, rules_mode=True)["key"].instructions == brain.RULES_KEY_INSTRUCTIONS + memory
    # The move question offers only the valid moves.
    assert list(brain.move_question(["walk_left", "wait"])["move"].criteria) == ["walk_left", "wait"]


def test_the_free_mode_text_gives_the_goal_and_no_rules():
    text = brain.FREE_MOVE_INSTRUCTIONS
    assert "collect all keys" in text and "`collects_key`" in text
    assert "Rule 1" not in text
    # Rules mode is a strict prompt: it has no mark that the code selects.
    assert "Rule 1" in brain.RULES_MOVE_INSTRUCTIONS
    assert "least_visited" not in brain.RULES_MOVE_INSTRUCTIONS


def test_default_settings():
    settings = Settings()
    assert not settings.rules_mode and settings.map_key_decision and settings.uses_map
    assert settings.key_decision_every == 25 and settings.survival_depth == 4
    assert settings.forced_key_order == "" and not settings.random_moves
    assert not Settings(rules_mode=True).uses_map  # rules mode uses the key facts and no map
    assert len(fields(Settings)) == 6  # a new setting needs a reason and a measurement


def test_llm_answer_parser_and_prompt():
    options = ["walk_left", "walk_right", "jump_left", "jump_right", "jump_up", "wait"]
    assert parse_choice("jump_left", options) == "jump_left"
    assert parse_choice("`walk_right`.\n", options) == "walk_right"
    assert parse_choice("I select jump_up because the key is above.", options) == "jump_up"
    assert parse_choice("walk_left or walk_right", options) is None  # not one clear option
    assert parse_choice("go", options) is None
    question = brain.move_question(["walk_left", "wait"])["move"]
    prompt = build_prompt({"air": "plenty"}, question)
    # The LLM gets the same instructions and the same options as jev.
    assert brain.FREE_MOVE_INSTRUCTIONS in prompt and "- walk_left:" in prompt
    assert "jump_up" not in prompt.split("OPTIONS")[1].split("STATE")[0]


# -- Live runs and replays ------------------------------------------------------------------


def _events(generator):
    async def collect():
        return [data async for kind, data in generator if kind == "event"]

    return asyncio.run(collect())


def test_a_live_run_with_no_jev_call_and_its_replay(tmp_path, monkeypatch):
    """A random player with a key order from the code needs no decision maker."""
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "MAX_DECISIONS", 12)
    game = Game()
    settings = Settings(random_moves=True, forced_key_order="ABCDE")
    events = _events(runner.play_live(game, None, 0, settings))
    header, end = events[0], events[-1]
    assert header["type"] == "header" and header["settings"]["random_moves"]
    assert end["type"] == "end" and end["input_tokens"] == 0
    decisions = [e for e in events if e["type"] == "decision"]
    assert decisions and all(set(d["offered"]) <= set(MACROS) for d in decisions)
    assert [e for e in events if e["type"] == "target"][0]["choice"] == "key_A"
    # The replay gives the same positions as the live run.
    results = [e for e in _events(runner.play_replay(game, header["file"])) if e["type"] == "result"]
    assert len(results) == len(decisions)
    assert not any(r.get("replay_mismatch") for r in results)
    assert runner.list_runs()[-1]["mode"] == "random moves" or any(
        r["mode"] == "random moves" for r in runner.list_runs())


def test_the_saved_examples_replay_to_a_complete_cavern():
    game = Game()
    for run in [r for r in runner.list_runs() if r["group"] == runner.EXAMPLES_GROUP]:
        results = [e for e in _events(runner.play_replay(game, run["file"])) if e["type"] == "result"]
        assert results[-1]["complete"], run["file"]
        assert not any(r.get("replay_mismatch") for r in results), run["file"]
