"""Tests of the requests to jev (jevmanic/checks.py).

Each check has a test that it finds a known problem. A check that finds
nothing is useful only if it can find a problem.
"""

import dataclasses

import pytest

from jevmanic import brain, checks, describe


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


def test_each_text_set_has_its_state_settings():
    # A new text set with a smaller state must be in TEXT_STATE, or the check uses the full state.
    for name in brain.instruction_sets():
        if name.startswith("promptM-") or name.endswith(("-plain", "-no-progress")):
            assert name in checks.TEXT_STATE, name


def test_the_text_check_finds_a_field_that_the_state_does_not_have(situations, monkeypatch):
    # promptA names `progress` and `progress_measures`. A state with no direction facts does not have them.
    monkeypatch.setitem(checks.TEXT_STATE, "promptA", ("none", "full"))
    problems = checks.text_problems("promptA", situations)
    assert len(problems) == 1 and "progress" in problems[0] and "progress_measures" in problems[0]


def test_the_facts_of_each_move_come_from_the_game_after_the_move(situations):
    assert checks.after_move_problems("full", situations) == []
    assert checks.after_move_problems("maps", situations) == []


def test_the_move_check_finds_guardians_from_before_the_move(situations, monkeypatch):
    # The first map test drew the guardians where they were before the move. Build the maps
    # in that way again: the check must report it.
    real = describe.move_request_state

    def guardians_from_before(snap, outcomes, *args):
        old = {name: dataclasses.replace(o, snapshot=dataclasses.replace(o.snapshot, guardians=snap.guardians))
               for name, o in outcomes.items()}
        return real(snap, old, *args)

    monkeypatch.setattr(describe, "move_request_state", guardians_from_before)
    problems = checks.after_move_problems("maps", situations)
    assert any("guardian" in p for p in problems)


def test_the_move_check_finds_a_map_with_no_erosion(situations, monkeypatch):
    # A map that shows each crumbling tile as new must be reported.
    real_grid = describe._grid
    monkeypatch.setattr(describe, "_grid", lambda snap, erosion=False: real_grid(snap, False))
    problems = checks.after_move_problems("maps", situations)
    assert any("crumbling tile" in p for p in problems)


def test_named_fields():
    assert checks.named_fields("`moves` gives `target.way_up` and `ticket.messages[0].text`.") == {
        "moves", "target", "way_up", "ticket", "messages", "text"}


def test_the_measurement_check_uses_the_settings_of_the_measurement(situations):
    from jevmanic.runner import Settings

    assert checks.measurement_problems(Settings()) == []
    # promptA names `progress`: a measurement with plain distances must not start with it.
    problems = checks.measurement_problems(Settings(progress_facts="plain"))
    assert any("progress" in p for p in problems)
    # A rule does not use the move text.
    assert checks.measurement_problems(Settings(progress_facts="plain", rule="plain")) == []
