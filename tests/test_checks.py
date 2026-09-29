"""Tests of the request checks (jevmanic/checks.py).

Each check has a test that proves it finds a known problem. A check that
finds nothing is useful only if it can find a problem.
"""

import dataclasses

import pytest

from jevmanic import brain, checks, describe
from jevmanic.settings import Settings


@pytest.fixture(scope="module")
def situations():
    return checks.check_situations()


def test_the_replay_gives_many_situations(situations):
    assert len(situations) > 200
    caverns = {s.snap.cavern_name for s in situations}
    assert len(caverns) == 20  # the recorded failure states add each cavern
    assert any(s.target is None for s in situations)  # the portal is the target at the end
    assert all(o.snapshot is not None for s in situations for o in s.outcomes.values())


def test_each_text_names_only_fields_of_its_state(situations):
    problems = [p for name in brain.instruction_sets() for with_map in (True, False)
                for p in checks.text_problems(Settings(instructions=name, map_key_decision=with_map), situations)]
    assert problems == []


def test_the_text_check_uses_the_settings_of_the_run(situations):
    # Without the progress facts, a text that names `progress` gives jev wrong information.
    problems = checks.text_problems(Settings(progress_facts=False), situations)
    assert len(problems) == 1 and "progress" in problems[0]


def test_the_text_check_finds_a_field_that_the_state_does_not_have(situations, monkeypatch):
    text = brain.move_instructions() + " `to_way_down` tells if a move gets nearer to the way down."
    monkeypatch.setattr(checks, "move_instructions", lambda name: text)
    problems = checks.text_problems(Settings(), situations)
    assert len(problems) == 1 and "to_way_down" in problems[0]


def test_the_facts_of_each_move_come_from_the_game_after_the_move(situations):
    assert checks.after_move_problems(situations) == []


def test_the_move_check_finds_a_movement_that_the_game_does_not_give(situations):
    # Make the look-ahead give one cell too many to the right: the check must report it.
    wrong = [dataclasses.replace(s, outcomes={name: dataclasses.replace(o, dx=o.dx + 1)
                                              for name, o in s.outcomes.items()})
             for s in situations[:20]]
    assert any("movement" in p for p in checks.after_move_problems(wrong))


def test_the_move_filter_agrees_with_the_look_ahead(situations):
    assert checks.filter_problems(situations) == []


def test_the_filter_check_finds_a_wrong_filter(situations, monkeypatch):
    # A filter that offers a move with no effect, and removes a move that has one.
    s = next(s for s in situations if s.snap.keys and not s.snap.airborne
             and any(r.startswith("no effect") for r in _removed(s).values()))
    duplicate = next(n for n, r in _removed(s).items() if r.startswith("no effect"))
    real = describe.move_request_state

    def wrong(snap, outcomes, target, visited, tried, settings=None):
        state = real(snap, outcomes, target, visited, tried, settings)
        moves = dict(state["moves"])
        state["moves"] = {**moves, duplicate: {}}
        offered = next(n for n in moves if n != "wait")
        state["moves_not_offered"] = {offered: "no effect: the same result as wait"}
        return state

    monkeypatch.setattr(describe, "move_request_state", wrong)
    problems = checks.filter_problems([s])
    assert any("give the same game" in p for p in problems)
    assert any("that is not true" in p for p in problems)


def _removed(s):
    removed = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried)["moves_not_offered"]
    return removed if isinstance(removed, dict) else {}


def test_the_filter_check_finds_a_target_out_of_reach(situations, monkeypatch):
    s = next(s for s in situations if s.snap.keys and not s.snap.airborne)
    monkeypatch.setattr(describe, "_target_relative", lambda snap, x, y, size=1: {"height": "same level"})
    target = (s.snap.willy_x, s.snap.willy_y - 6)
    wrong = dataclasses.replace(s, snap=dataclasses.replace(s.snap, keys=[target]), target=target)
    assert any("jump does not reach" in p for p in checks.filter_problems([wrong]))


def test_named_fields():
    assert checks.named_fields("`moves` gives `target.way_up` and `ticket.messages[0].text`.") == {
        "moves", "target", "way_up", "ticket", "messages", "text"}


def test_the_measurement_check_uses_the_settings_of_the_measurement(monkeypatch):
    assert checks.measurement_problems(Settings()) == []
    monkeypatch.setattr(checks, "text_problems", lambda settings: [f"{settings.instructions}: a problem"])
    assert checks.measurement_problems(Settings()) == ["promptD: a problem"]
    # A rule does not use the texts.
    assert checks.measurement_problems(Settings(rule="nearer")) == []


def test_the_ladder_setting_belongs_to_each_state_and_not_to_the_module():
    # Ore Refinery: only the ladder setting finds a way up. Before the fix, a
    # run's setting was a module variable, so a concurrent run could change it.
    s = checks.state_situations("failure_states.json")[11]
    assert s.snap.cavern_name == "Ore Refinery"

    def way_up(settings):
        state = describe.move_request_state(s.snap, s.outcomes, s.target, s.visited, s.tried, settings)
        return state["target"]["way_up"]

    alone = way_up(Settings()), way_up(Settings(ladder_fix=True))
    interleaved = [way_up(Settings(ladder_fix=fix)) for fix in (False, True, False, True)]
    assert alone[0] == "none on this level" and isinstance(alone[1], dict)
    assert interleaved == [alone[0], alone[1], alone[0], alone[1]]
    assert not hasattr(describe, "LADDER_FIX")
