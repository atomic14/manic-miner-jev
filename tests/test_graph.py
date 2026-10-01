"""Tests of the half steps and the movement graph. They need no jev calls."""

import asyncio
from collections import Counter

from jevmanic import describe, runner
from jevmanic.game import ADDR_ITEMS, ALL_MOVES, DEAD_END_CAUSE, HALF_STEPS, MACROS, Game, Outcome
from jevmanic.graph import DEAD, NO_WAY_BACK, Edge, MovementGraph, RouteFacts, Routes
from jevmanic.runner import Settings


def test_a_half_step_moves_willy_half_a_cell():
    game = Game()  # Central Cavern: Willy starts at pixel 16, and he faces right
    game.emu.save_state(500)
    game.run_macro("step_right")
    assert game._willy_pixel() == [20, 104]
    game.emu.load_state(500)
    game.emu.set_joystick(0)
    game.run_macro("step_left")  # a turn first, and then half a cell
    assert game._willy_pixel() == [12, 104] and game.snapshot().willy_facing == "left"
    game.emu.load_state(500)
    game.emu.set_joystick(0)
    outcomes = game.look_ahead(moves=ALL_MOVES)
    assert set(outcomes) == set(MACROS) | set(HALF_STEPS)
    assert (outcomes["step_right"].dx, outcomes["step_right"].dx_pixels) == (0, 4)
    state = describe.moves_state(game.snapshot(), outcomes, game.snapshot().keys[0], Counter())
    assert state["moves"]["step_right"]["movement"] == "Willy moves half a cell to the right"
    assert state["moves"]["walk_right"]["movement"] == "Willy moves 1 cell to the right"


def test_the_graph_counts_the_moves_to_each_key():
    game = Game()  # Central Cavern, from the start, with the guardians off
    graph = MovementGraph(game, MACROS).explore()
    snap = game.snapshot()
    moves = {snap.key_letters[k]: graph.moves_to_cell(k)[graph.start] for k in snap.keys}
    assert moves == {"A": 20, "B": 25, "C": 22, "D": 24, "E": 11}
    assert graph.moves_to_finish() == {}  # the portal is closed while a key is left
    assert game.snapshot() == snap  # the exploration does not change the game


def test_the_six_moves_cannot_enter_the_portal_of_the_processing_plant():
    game = Game(cavern=5)
    for i in range(5):  # all keys collected: the portal is open
        if game.emu.peek(ADDR_ITEMS + i * 5) == 255:
            break
        game.emu.poke(ADDR_ITEMS + i * 5, 0)
    game.run_macro("wait")
    six = MovementGraph(game, MACROS).explore()
    assert six.moves_to_finish().get(six.start) is None
    eight = MovementGraph(game, ALL_MOVES).explore()
    assert eight.moves_to_finish().get(eight.start) == 18


def _outcome(snap, dx, dead=False, cause=""):
    x = snap.willy_x + dx
    return Outcome(dead, cause, False, dx, 0, 0, 4, x, snap.willy_y, snapshot=snap, pixel=(x * 8, snap.willy_y * 8))


def test_the_graph_facts_in_the_state():
    snap = Game().snapshot()
    outcomes = {"walk_left": _outcome(snap, -1), "walk_right": _outcome(snap, 1), "wait": _outcome(snap, 0),
                "jump_up": _outcome(snap, 0, True, "nasty")}
    route = RouteFacts(now=5, after={"walk_left": 6, "walk_right": 4, "wait": 5}, no_way_back={})
    state = describe.moves_state(snap, outcomes, snap.keys[0], Counter(), route=route)
    assert state["progress_measures"] == describe.GRAPH_MEASURE
    assert {m: f["progress"] for m, f in state["moves"].items()} == {
        "walk_left": "farther", "walk_right": "nearer", "wait": "same"}
    # A move after which a key or the portal is out of reach is not valid ...
    route.no_way_back = {"walk_right": NO_WAY_BACK}
    state = describe.moves_state(snap, outcomes, snap.keys[0], Counter(), route=route)
    assert "walk_right" not in state["moves"] and state["moves_not_offered"]["walk_right"] == NO_WAY_BACK
    # ... unless each safe move is such a move.
    route.no_way_back = {m: NO_WAY_BACK for m in ("walk_left", "walk_right", "wait")}
    assert set(describe.moves_state(snap, outcomes, snap.keys[0], Counter(), route=route)["moves"]) == {
        "walk_left", "walk_right", "wait"}
    # No way to the target from here: a move to a place with a way is nearer.
    assert describe._graph_progress(None, 3) == "nearer" and describe._graph_progress(None, None) == "same"
    assert describe._graph_progress(3, None) == "farther"
    # The graph facts replace the way up and the way down of the tile map.
    base = Game(cavern=5).snapshot()  # Processing Plant: the first key is below the start
    assert "way_down" in describe.words(base, (15, 6))["target"]
    assert "way_down" not in describe.words(base, (15, 6), graph_facts=True)["target"]


def test_a_dead_end_move_stays_with_its_warning_when_no_move_is_safe_with_the_graph():
    snap = Game().snapshot()
    kills = _outcome(snap, 1, True, "guardian")
    dead_end = _outcome(snap, -1, True, DEAD_END_CAUSE)
    outcomes = {name: (dead_end if name == "walk_left" else kills) for name in MACROS}
    state = describe.moves_state(snap, outcomes, snap.keys[0], Counter(), route=RouteFacts(3, {}, {}))
    assert set(state["moves"]) == {"walk_left"} and "warning" in state["moves"]["walk_left"]


def test_a_key_that_leaves_another_key_out_of_reach_is_not_an_option():
    """A small graph: key K1 is at the end of a one-way drop, and key K2 is up the other way."""
    snap = Game().snapshot()
    k1, k2 = (1, 1), (2, 2)
    start, pit, ledge = (0, 0, 0, ()), (1, 0, 0, ()), (2, 0, 0, ())
    graph = MovementGraph(None, {})
    graph.start = start
    graph.edges = {
        start: {"drop": Edge(pit, frozenset({k1})), "climb": Edge(ledge, frozenset())},
        pit: {"wait": Edge(pit, frozenset())},
        ledge: {"grab": Edge(ledge, frozenset({k2})), "back": Edge(start, frozenset()), "fall": Edge(DEAD, frozenset({k1}))},
    }
    routes = Routes(None, {})
    routes.graph, routes._places = graph, {n: [n] for n in graph.edges}
    routes.update = lambda snap, outcomes=None: start
    keys_snap = snap.__class__(**{**snap.__dict__, "keys": [k1, k2]})
    assert routes.valid_goals(keys_snap, [k1, k2]) == [k2]
    # With K2 collected, K1 is the last key, and it is an option again.
    last = snap.__class__(**{**snap.__dict__, "keys": [k1]})
    assert routes.valid_goals(last, [k1]) == [k1]


def test_a_live_run_with_half_steps_and_the_graph_and_its_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "MAX_DECISIONS", 8)
    game = Game()
    settings = Settings(rule="nearer", forced_key_order="EACDB", graph_facts=True, half_steps=True, no_way_back=True)

    async def collect(generator):
        return [data async for kind, data in generator if kind == "event"]

    events = asyncio.run(collect(runner.play_live(game, None, 0, settings, show_paths=True)))
    header, end = events[0], events[-1]
    assert header["settings"]["half_steps"] and end["graph_explorations"] >= 1
    decisions = [e for e in events if e["type"] == "decision"]
    assert all(set(d["offered"]) <= set(ALL_MOVES) for d in decisions)
    assert all(d["state"]["progress_measures"] == describe.GRAPH_MEASURE for d in decisions)
    assert decisions[0]["moves_to_target"] == 11  # key E, as in the test above
    assert set([e for e in events if e["type"] == "paths"][0]["paths"]) == set(ALL_MOVES)
    replay = asyncio.run(collect(runner.play_replay(game, header["file"], show_paths=True)))
    results = [e for e in replay if e["type"] == "result"]
    assert len(results) == len(decisions) and not any(r.get("replay_mismatch") for r in results)
