"""Tests of the request checks (jevmanic/checks.py).

Each check has a test that proves it finds a known problem. A check that
finds nothing is useful only if it can find a problem.
"""

import dataclasses

import pytest

from jevmanic import brain, checks


@pytest.fixture(scope="module")
def situations():
    return checks.check_situations()


def test_the_replay_gives_many_situations(situations):
    assert len(situations) > 200
    assert any(s.target is None for s in situations)  # the portal is the target at the end
    assert all(o.snapshot is not None for s in situations for o in s.outcomes.values())


def test_each_text_names_only_fields_of_its_state(situations):
    problems = [p for name in brain.instruction_sets() for p in checks.text_problems(name, situations)]
    assert problems == []


def test_the_text_check_finds_a_field_that_the_state_does_not_have(situations, monkeypatch):
    text = brain.move_instructions() + " `to_way_down` tells if a move gets nearer to the way down."
    monkeypatch.setattr(checks, "move_instructions", lambda name: text)
    problems = checks.text_problems(brain.DEFAULT_INSTRUCTIONS, situations)
    assert len(problems) == 1 and "to_way_down" in problems[0]


def test_the_facts_of_each_move_come_from_the_game_after_the_move(situations):
    assert checks.after_move_problems(situations) == []


def test_the_move_check_finds_a_movement_that_the_game_does_not_give(situations):
    # Make the look-ahead give one cell too many to the right: the check must report it.
    wrong = [dataclasses.replace(s, outcomes={name: dataclasses.replace(o, dx=o.dx + 1)
                                              for name, o in s.outcomes.items()})
             for s in situations[:20]]
    assert any("movement" in p for p in checks.after_move_problems(wrong))


def test_named_fields():
    assert checks.named_fields("`moves` gives `target.way_up` and `ticket.messages[0].text`.") == {
        "moves", "target", "way_up", "ticket", "messages", "text"}


def test_the_measurement_check_uses_the_settings_of_the_measurement(monkeypatch):
    from jevmanic.runner import Settings

    assert checks.measurement_problems(Settings()) == []
    monkeypatch.setattr(checks, "text_problems", lambda name: [f"{name}: a problem"])
    assert checks.measurement_problems(Settings()) == ["promptD: a problem"]
    # A rule does not use the texts.
    assert checks.measurement_problems(Settings(rule="nearer")) == []
