"""Tests that need no jev calls."""

import asyncio
import json
from collections import Counter
from dataclasses import fields, replace
from pathlib import Path

from jevmanic import brain, describe, runner
from jevmanic.game import DEAD_END_CAUSE, MACROS, SURVIVAL_BUDGET, SURVIVAL_DEPTH, Game, Outcome
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


def test_the_paths_for_the_viewer_do_not_change_the_game():
    game = Game()
    before, ticks = game.snapshot(), game.tick_count
    paths = game.macro_paths()
    assert game.snapshot() == before and game.tick_count == ticks
    assert set(paths) == set(MACROS)
    assert paths["walk_right"]["points"][0] == [16, 104]  # Willy at column 2, row 13
    assert paths["walk_right"]["points"][-1] == [24, 104]  # 1 cell to the right
    assert not paths["walk_right"]["dead"]


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


def test_a_search_that_runs_out_of_budget_proves_nothing():
    game = Game()
    assert game._can_survive(SURVIVAL_DEPTH, [0]) is None
    assert game._can_survive(SURVIVAL_DEPTH, [SURVIVAL_BUDGET]) is True
    # A proof still needs the whole search: jump_right from here is a proven death
    # (see test_a_move_that_kills_willy_is_not_offered), so Willy is dead at depth 0.
    for name in ["jump_right", "walk_right", "walk_right", "walk_right", "jump_right"]:
        game.run_macro(name)
    assert game.is_dead() and game._can_survive(SURVIVAL_DEPTH, [0]) is False


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


def _review_state(index: int, moves: int | None = None):
    """A game from tests/fixtures/review_states.json: a recorded run, played up to one decision."""
    fixture = json.loads((Path(__file__).parent / "fixtures" / "review_states.json").read_text())[index]
    game = Game(cavern=fixture["cavern"])
    for name in fixture["moves"][:moves]:
        game.run_macro(name)
    return game, tuple(fixture["target"])


def test_a_move_with_the_same_result_as_another_move_is_not_offered():
    # Central Cavern, on a conveyor: walk_left and walk_right give the same game.
    game, target = _review_state(0)
    state = _moves(game.snapshot(), game.look_ahead(), target)
    assert state["moves_not_offered"]["walk_right"] == "no effect: the same result as walk_left"
    # wait ends in the same cell, but the guardian then moves the other way.
    assert {"walk_left", "wait"} <= set(state["moves"])


def test_a_move_in_the_same_cell_stays_when_it_changes_a_crumbling_floor():
    game, target = _review_state(0, moves=13)  # Willy stands on a crumbling floor
    outcomes = game.look_ahead()
    assert (outcomes["jump_up"].dx, outcomes["jump_up"].dy) == (0, 0)
    assert outcomes["jump_up"].snapshot.crumbled != outcomes["wait"].snapshot.crumbled
    assert {"jump_up", "wait"} <= set(_moves(game.snapshot(), outcomes, target)["moves"])


def test_in_the_air_only_the_moves_that_change_the_landing_stay():
    game = Game()
    game.run_macro("jump_right")
    for _ in game.macro_ticks("jump_right"):
        if game.is_airborne():
            break
    state = _moves(game.snapshot(), game.look_ahead())
    # jump_left turns Willy when he lands, and jump_right carries him 2 pixels on.
    assert list(state["moves"]) == ["jump_left", "jump_right", "wait"]
    for name in ("walk_left", "walk_right", "jump_up"):
        assert state["moves_not_offered"][name] == "no effect: the same result as wait"


def test_a_key_beyond_the_jump_reach_is_higher_even_on_the_same_floor():
    # Abandoned Uranium Workings: the key hangs 7 rows above Willy's head.
    game, target = _review_state(1)
    snap = game.snapshot()
    state = describe.move_request_state(snap, game.look_ahead(), target, Counter(), set())
    assert state["target"]["height"] == "higher" and state["target"]["floor_rows_apart"] == 0
    assert state["progress_measures"] == "distance to the way up"
    assert state["moves"]["jump_right"]["progress"] == "nearer"  # the jump onto the higher platform


def test_a_key_within_the_jump_reach_is_on_the_same_level():
    game = Game()
    snap = game.snapshot()
    highest_head_row = min(game._willy_pixel()[1] for _ in game.macro_ticks("jump_up")) // 8
    assert snap.willy_y - highest_head_row == describe.MAX_JUMP_REACH_ROWS
    for rows_above, height in ((3, "same level"), (4, "higher")):
        key = (snap.willy_x + 1, snap.willy_y - rows_above)  # no platform between the key and Willy's floor
        assert describe._target_relative(replace(snap, keys=[key]), *key)["height"] == height


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


def test_each_instruction_set_has_its_texts_in_files():
    sets = brain.instruction_sets()
    assert sets[0] == "promptD" and "promptA" in sets  # the default set is first
    for name in brain.instruction_sets():
        for which in ("move.txt", "key.txt", "key_facts_only.txt"):
            assert (brain.INSTRUCTIONS_DIR / name / which).read_text().strip(), (name, which)
    assert brain.move_question()["move"].instructions == brain.move_instructions("promptD")
    assert brain.move_question(instructions="promptA")["move"].instructions == brain.move_instructions("promptA")
    names = ["key_A", "key_B"]
    memory = " ".join((brain.INSTRUCTIONS_DIR / "key_memory.txt").read_text().split())
    for name in ("promptA", "promptD"):
        with_map = brain.key_question(names, name)["key"].instructions
        facts_only = brain.key_question(names, name, with_map=False)["key"].instructions
        # The text must name the map, or jev does not use it.
        assert "map" in with_map and "map" not in facts_only
        # A text explains a field only if its state can have that field:
        # `gave_up_on_it` is only in the key decision's state without the map.
        assert with_map.endswith(memory) and memory in facts_only
        assert "gave_up_on_it" not in with_map and "gave_up_on_it" in facts_only
        assert "\n" not in with_map and "  " not in with_map  # one paragraph
    # The move question offers only the valid moves.
    assert list(brain.move_question(["walk_left", "wait"])["move"].criteria) == ["walk_left", "wait"]


def test_the_default_text_gives_the_goal_and_no_rules():
    text = brain.move_instructions()
    assert "collect all keys" in text and "`collects_key`" in text
    assert "Rule 1" not in text
    # promptA says that each move in `moves` is safe. That is not always true.
    assert "safe and have an effect" in brain.move_instructions("promptA")
    assert "safe and have an effect" not in text


def test_the_instructions_are_the_only_difference_between_two_sets(tmp_path, monkeypatch):
    """The same game with the two sets: the same state, the same options, and the same key schedule."""
    from jevmanic.runner import _LiveRun

    game = Game()
    runs = {name: _LiveRun(game, None, Settings(instructions=name)) for name in brain.instruction_sets()}
    assert all(run.settings.map_key_decision for run in runs.values())
    snap = game.snapshot()
    goals = snap.keys + snap.switches
    for n in (0, 1, 24, 25, 26):
        due = set()
        for run in runs.values():
            run.target, run.goals_at_request, run.n_at_request = snap.keys[0], len(goals), 0
            due.add(run._key_decision_is_due(snap, goals, n))
        assert len(due) == 1, n


def test_default_settings():
    settings = Settings()
    assert settings.instructions == "promptD" and settings.map_key_decision
    assert settings.key_decision_every == 25 and settings.survival_depth == 4
    assert settings.forced_key_order == "" and not settings.random_moves
    assert Settings(instructions="promptA").map_key_decision  # each set gets the same state
    assert settings.rule == "" and settings.key_rule == "" and not settings.sample_moves
    assert settings.guardian_facts and not settings.move_map and settings.map_empty == "."
    assert not settings.ladder_fix and settings.progress_facts
    assert not settings.graph_facts and not settings.half_steps and not settings.no_way_back
    assert len(fields(Settings)) == 17  # a new setting needs a reason and a measurement


def test_nearer_rule():
    """The rule `nearer`: a key or the portal first, then a nearer move, then any valid move."""
    from jevmanic.runner import rule_moves
    facts = {"walk_left": {"progress": "farther", "place": "new place"},
             "walk_right": {"progress": "nearer", "place": "visited before"},
             "jump_right": {"progress": "nearer", "place": "new place", "collects_key": True},
             "wait": {"progress": "same", "place": "visited before"}}
    assert rule_moves("nearer", list(facts), facts) == ["jump_right"]
    del facts["jump_right"]["collects_key"]
    assert rule_moves("nearer", list(facts), facts) == ["walk_right", "jump_right"]
    assert rule_moves("nearer", ["walk_left", "wait"], facts) == ["walk_left", "wait"]


def test_each_cavern_has_an_optimum_key_order_with_all_its_keys():
    from jevmanic.key_orders import OPTIMUM_KEY_ORDER

    game = Game()
    for cavern in range(20):
        game.select_cavern(cavern)
        letters = game.snapshot().key_letters.values()
        assert sorted(OPTIMUM_KEY_ORDER[cavern]) == sorted(letters), cavern


def test_the_key_decision_lab_makes_the_request_of_a_live_run():
    from jevmanic import lab

    game = Game()
    # Central Cavern: key E is collected, and a click near the conveyor puts Willy on it.
    snap = lab.situation(game, 0, [27, 8], "E")
    assert (snap.willy_x, snap.willy_y) == (27, 7)
    assert [snap.key_letters[k] for k in snap.keys] == ["A", "B", "C", "D"]
    state, question = lab.request_for(snap)
    assert list(state["keys"]) == ["key_A", "key_B", "key_C", "key_D"]
    assert "E" not in "".join(state["map"]) and "W" in state["map"][7]
    assert question["key"].instructions == brain.key_instructions(brain.DEFAULT_INSTRUCTIONS, with_map=True)
    # A person can try a different instruction text: it replaces the text of the set.
    _, custom = lab.request_for(snap, custom_text="Select the key\n that is the nearest.  ")
    assert custom["key"].instructions == "Select the key that is the nearest."
    assert list(custom["key"].criteria) == list(question["key"].criteria)
    # A click in empty space goes to the nearest place where Willy can stand.
    assert lab.standing_place(game.snapshot(), 29, 1) == (29, 3)


def test_the_text_that_laya_gets_has_one_short_sentence_for_each_option():
    from jevmanic.laya_brain import option_sentences, state_as_text

    moves = {"walk_left": {"progress": "farther", "place": "visited before", "tried_from_here": "no"},
             "jump_right": {"progress": "nearer", "place": "new place", "tried_from_here": "no"},
             "jump_up": {"progress": "nearer", "place": "new place", "tried_from_here": "no", "collects_key": True}}
    assert option_sentences({"moves": moves}) == {
        "walk_left": "walk_left is farther.", "jump_right": "jump_right is nearer and new.",
        "jump_up": "jump_up is nearer and collects a key."}
    assert state_as_text({"moves": moves}, ["jump_up", "walk_left"]) == "jump_up is nearer and collects a key. walk_left is farther."
    # No move is safe: `moves` is a string instead of a dict.
    assert state_as_text({"moves": "none: no move is safe"}, ["wait"]) == "wait is not safe."


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
    assert brain.move_instructions() in prompt and "- walk_left:" in prompt
    assert "jump_up" not in prompt.split("OPTIONS")[1].split("STATE")[0]


# -- Live runs and replays ------------------------------------------------------------------


def _events(generator):
    async def collect():
        return [data async for kind, data in generator if kind == "event"]

    return asyncio.run(collect())


def test_a_live_run_with_no_jev_call_and_its_replay(tmp_path, monkeypatch):
    """Random moves with a fixed key order make no jev request, and the replay matches."""
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


def test_two_runs_that_start_in_the_same_second_get_two_log_files(tmp_path, monkeypatch):
    from concurrent.futures import ProcessPoolExecutor

    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    paths = [runner._log_path("same", 0, "Central Cavern", "promptD") for _ in range(3)]
    assert len(set(paths)) == 3 and all(p.exists() for p in paths)
    # Several processes at once: each file is new, so no two runs share one.
    with ProcessPoolExecutor(4) as pool:
        names = list(pool.map(_log_path_in_process, [str(tmp_path)] * 8))
    assert len(set(names)) == 8


def _log_path_in_process(folder):
    runner.RUNS_DIR = Path(folder)
    return str(runner._log_path("parallel", 0, "Central Cavern", "promptD"))
