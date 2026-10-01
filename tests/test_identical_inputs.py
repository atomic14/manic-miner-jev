"""A recorded example where identical observations hide different futures."""

import json
from pathlib import Path

from experiments.probe_identical_inputs import BRANCH_SLOT, continuation, packed
from jevmanic import describe
from jevmanic.game import ADDR_HGUARDS, Game
from jevmanic.runner import _LiveRun, _result
from jevmanic.settings import Settings


def test_identical_inputs_can_hide_different_guardian_phases():
    fixture = json.loads((Path(__file__).parent / "fixtures" / "identical_inputs.json").read_text())
    games = []
    for prefix, target, tick in zip(fixture["prefixes"], fixture["targets"], fixture["ticks"]):
        game = Game(cavern=fixture["cavern"])
        run = _LiveRun(game, None, Settings())
        for n, move in enumerate(prefix):
            snap = game.snapshot()
            run.tried.add((snap.willy_x, snap.willy_y, move))
            ticks = game.run_macro(move)
            run.remember(_result(game, n, ticks, run.keys_at_start))
        state = describe.move_request_state(game.snapshot(), game.look_ahead(), tuple(target),
                                            run.visited, run.tried, run.settings)
        assert packed(state) == packed(fixture["input"][0])
        assert game.tick_count == tick
        game.emu.save_state(BRANCH_SLOT)
        games.append(game)
    assert games[0].snapshot() == games[1].snapshot()
    assert games[0]._willy_pixel() == games[1]._willy_pixel()
    assert games[0].emu.peek_range(ADDR_HGUARDS, 28) != games[1].emu.peek_range(ADDR_HGUARDS, 28)
    witness = fixture["continuation"]
    outcomes = [continuation(g, tick, witness["moves"]) for g, tick in zip(games, fixture["ticks"])]
    assert outcomes == witness["outcomes"]
    assert not outcomes[0]["dead"] and outcomes[1]["dead"]
