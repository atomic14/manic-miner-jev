"""The key decision lab: ask jev the key question for a situation that a person sets up.

The person selects a cavern, marks keys as collected, and puts Willy at a
place. The lab makes the same request as a live run (the same state and the
same question), and gives the answer of jev.

Limits: the cavern is in its start condition (no crumbling floor is used, and
the guardians are at their start positions). The key memory is empty, as in
the first key request of a run.
"""

from dataclasses import replace

from . import describe
from .brain import DEFAULT_INSTRUCTIONS, key_question, questions_as_json
from .game import (
    COLS,
    ROWS,
    TILE_CONVEYOR,
    TILE_CRUMBLING,
    TILE_EMPTY,
    TILE_FLOOR,
    TILE_NASTY,
    TILE_WALL,
    Game,
    Snapshot,
)
from .key_orders import OPTIMUM_KEY_ORDER

SOLID = (TILE_FLOOR, TILE_CRUMBLING, TILE_WALL, TILE_CONVEYOR)  # tiles that Willy can stand on


def cavern_info(game: Game, cavern: int) -> dict:
    """The data that the page needs to draw the cavern and to find a click."""
    game.select_cavern(cavern)
    snap = game.snapshot()
    return {
        "cavern": cavern,
        "name": snap.cavern_name,
        "keys": [{"letter": snap.key_letters[k], "cell": list(k)} for k in snap.keys],
        "switches": [list(s) for s in snap.switches],
        "willy": [snap.willy_x, snap.willy_y],
        "optimum_order": OPTIMUM_KEY_ORDER[cavern],
    }


def standing_place(snap: Snapshot, x: int, y: int) -> tuple[int, int]:
    """The place nearest to the click where Willy can stand. Willy is 2 x 2 cells."""

    def tile(cx, cy):
        return snap.tiles[cy][cx] if 0 <= cx < COLS and 0 <= cy < ROWS else TILE_WALL

    def can_stand(wx, wy):
        body = [tile(wx + dx, wy + dy) for dx in (0, 1) for dy in (0, 1)]
        free = all(t == TILE_EMPTY for t in body)
        below = [tile(wx + dx, wy + 2) for dx in (0, 1)]
        return free and any(t in SOLID for t in below) and TILE_NASTY not in below

    x = max(1, min(COLS - 3, x))
    # The click is on the body of Willy: look down from one row above the click.
    rows = list(range(max(0, y - 1), ROWS - 2)) + list(range(max(0, y - 2), -1, -1))
    for wy in rows:
        for wx in (x, x - 1, x + 1):
            if can_stand(wx, wy):
                return wx, wy
    return snap.willy_x, snap.willy_y


def situation(game: Game, cavern: int, willy, collected: str) -> Snapshot:
    """The start of the cavern, with Willy at a different place and some keys collected."""
    game.select_cavern(cavern)
    snap = game.snapshot()
    keys = [k for k in snap.keys if snap.key_letters[k] not in collected.upper()]
    if willy:
        x, y = standing_place(snap, int(willy[0]), int(willy[1]))
    else:
        x, y = snap.willy_x, snap.willy_y
    return replace(snap, willy_x=x, willy_y=y, keys=keys)


def request_for(snap: Snapshot, with_map: bool = True, instructions: str = DEFAULT_INSTRUCTIONS,
                custom_text: str = ""):
    """The state and the question of the key request, the same as in a live run.

    `custom_text` replaces the instruction text: a person can try a text with no file.
    """
    names = {cell: f"key_{snap.key_letters[cell]}" for cell in snap.keys}
    names.update({cell: f"switch_{i + 1}" for i, cell in enumerate(snap.switches)})
    memory = {"current": None, "used": {}, "gave_up": {}}
    state = describe.key_request_state(snap, names, memory, with_map)
    question = key_question(list(names.values()), instructions, with_map)
    if custom_text.strip():
        question["key"].instructions = " ".join(custom_text.split())  # one paragraph, as from a file
    return state, question


async def ask(game: Game, brain, cavern: int, willy, collected: str, with_map: bool = True,
              instructions: str = DEFAULT_INSTRUCTIONS, custom_text: str = "") -> dict:
    snap = situation(game, cavern, willy, collected)
    out = {"willy": [snap.willy_x, snap.willy_y], "keys_left": [snap.key_letters[k] for k in snap.keys]}
    goals = len(snap.keys) + len(snap.switches)
    if goals == 0:
        return {**out, "no_call": "No key is left. The target is the exit portal, and there is no key request."}
    state, question = request_for(snap, with_map, instructions, custom_text)
    out.update(state=state, question=questions_as_json(question))
    if goals == 1:
        return {**out, "no_call": "Only one key is left. A live run makes no jev call for this."}
    answer = await brain.ask(state, question, "key")
    return {**out, **{k: v for k, v in answer.to_json().items() if k != "state"}}
