"""The state that we send to jev: a game Snapshot turned into facts.

Jev reads text only, and it is weak with coordinates and with large states.
So the state gives positions relative to Willy, in words and small numbers.

    cavern_map   the cavern map with its legend (for the key decision)
    keys_state   facts about each key and switch (for the key decision)
    words        facts about Willy, the target, and the guardians (for the move decision)
    moves_state  the true result of each valid move, from the look-ahead

The geometry facts (`way_up`, `way_down`, `progress`) are estimates from the
tile map. Each of them has been wrong in at least one cavern. Measure each
change with `experiments/measure.py`.
"""

from .game import (
    COLS,
    DEAD_END_CAUSE,
    ROWS,
    TILE_CONVEYOR,
    TILE_CRUMBLING,
    TILE_EMPTY,
    TILE_FLOOR,
    TILE_NASTY,
    TILE_WALL,
    Snapshot,
)
from .settings import Settings

# What each map symbol means for Willy. `map_legend` keeps only the symbols
# that are on the map.
SYMBOL_MEANING = {
    "W": "Willy. He is 2 cells wide and 2 cells high.",
    "key": "Willy collects it when he touches it.",
    "S": "a switch. Willy flips it when he touches it. A switch changes the cavern.",
    "P": "the exit portal, 2 cells wide and 2 cells high. Willy can enter it when he has all keys.",
    "G": "a guardian, 2 cells wide and 2 cells high. It moves. It kills Willy on contact.",
    "X": "a nasty. It does not move. It kills Willy on contact.",
    "=": "floor. Willy can stand on it. It does not stop a jump from below.",
    "~": "crumbling floor. Willy can stand on it. It breaks a little each time Willy stands on it, and then it is gone.",
    "<": "conveyor. Willy can stand on it. It moves Willy to the left.",
    ">": "conveyor. Willy can stand on it. It moves Willy to the right.",
    "#": "wall. It stops Willy. Willy can stand on top of it.",
    ".": "empty space.",
}


def map_legend(rows: list[str], snap: Snapshot) -> dict:
    """The legend for the symbols on this map. Each key gets its own letter."""
    present = set("".join(rows)) - {" "}
    legend = {}
    for symbol, meaning in SYMBOL_MEANING.items():
        if symbol == "key":
            for cell in snap.keys:
                letter = snap.key_letters.get(cell, "K")
                if letter in present:
                    legend[letter] = f"key {letter}. " + meaning
        elif symbol in present:
            legend[symbol] = meaning
    return legend


LOOK_AHEAD_CELLS = 6  # how far `to_the_left` and `to_the_right` look
MAX_JUMP_ROWS = 2  # a jump can reach a platform that is 2 rows higher
# Willy rises 20 pixels. His head can touch a key in the third row above him.
MAX_JUMP_REACH_ROWS = 3


# -- ASCII maps ---------------------------------------------------------------


def _grid(snap: Snapshot) -> list[list[str]]:
    """The tile map with the keys, switches, guardians, portal, and Willy drawn on it."""
    conveyor = ">" if snap.conveyor_direction == "right" else "<"
    grid = [[conveyor if ch == TILE_CONVEYOR else ch for ch in row] for row in snap.tiles]

    def put(x, y, ch, size=1):
        for dy in range(size):
            for dx in range(size):
                if 0 <= x + dx < COLS and 0 <= y + dy < ROWS:
                    grid[y + dy][x + dx] = ch

    for cell in snap.keys:
        put(*cell, snap.key_letters.get(cell, "K"))
    for cell in snap.switches:
        put(*cell, "S")
    for g in snap.guardians:
        put(g.x, g.y, "G", 2)
    # Draw the portal after the guardians, so that a guardian does not hide the exit.
    put(*snap.portal, "P", 2)
    put(snap.willy_x, snap.willy_y, "W", 2)
    return grid


def _rows(grid, x0, x1, y0, y1):
    out = []
    for y in range(y0, y1 + 1):
        # Cells outside the cavern show as wall.
        cells = [
            grid[y][x] if 0 <= x < COLS and 0 <= y < ROWS else TILE_WALL
            for x in range(x0, x1 + 1)
        ]
        out.append("".join(cells))
    return out


def cavern_map(snap: Snapshot, empty: str = TILE_EMPTY) -> dict:
    """The full map of the cavern with its legend. Each string is one row. `empty` is the symbol for empty space."""
    rows = _rows(_grid(snap), 0, COLS - 1, 0, ROWS - 1)
    legend = map_legend(rows, snap)
    if empty != TILE_EMPTY:
        rows = [row.replace(TILE_EMPTY, empty) for row in rows]
        legend = {(empty if s == TILE_EMPTY else s): m for s, m in legend.items()}
    return {
        "map_legend": legend,
        "map_note": "Each string is one row. The first row is the top of the cavern.",
        "map": rows,
    }


# -- Words ----------------------------------------------------------------------


def _distance_word(cells: int) -> str:
    if cells <= 1:
        return "adjacent"
    if cells <= 3:
        return "near"
    if cells <= 8:
        return "medium"
    return "far"


def _tile(snap, x, y) -> str:
    if y >= ROWS:
        return TILE_FLOOR
    if not (0 <= x < COLS and 0 <= y < ROWS):
        return TILE_WALL
    return snap.tiles[y][x]


ALMOST_GONE_ROWS = 4  # one walk across a tile uses about 4 of its 8 pixel rows


def _crumbling_words(rows_gone: int) -> str:
    """A crumbling floor with its condition. The condition is a word because jev is weak with numbers."""
    if rows_gone >= ALMOST_GONE_ROWS:
        return "crumbling floor, almost gone"
    return "crumbling floor, partly gone" if rows_gone else "crumbling floor, new"


def _standing_on(snap: Snapshot) -> str:
    if snap.airborne:
        return "nothing, Willy is in the air"
    below = {_tile(snap, snap.willy_x + dx, snap.willy_y + 2) for dx in (0, 1)}
    if TILE_CONVEYOR in below:
        return "conveyor"
    if TILE_CRUMBLING in below:
        return _crumbling_words(max(snap.crumbled.get((snap.willy_x + dx, snap.willy_y + 2), 0) for dx in (0, 1)))
    return "floor"


def _look(snap: Snapshot, direction: int) -> dict:
    """What Willy meets first if he walks in one direction on his level."""
    front = snap.willy_x + 1 if direction > 0 else snap.willy_x
    for i in range(1, LOOK_AHEAD_CELLS + 1):
        x = front + direction * i
        body = [_tile(snap, x, snap.willy_y), _tile(snap, x, snap.willy_y + 1)]
        if TILE_WALL in body:
            return {"first_thing": "wall", "distance_cells": i}
        if TILE_NASTY in body:
            return {"first_thing": "nasty", "distance_cells": i}
        under = _tile(snap, x, snap.willy_y + 2)
        if under == TILE_NASTY:
            return {"first_thing": "nasty in the floor", "distance_cells": i}
        if under == TILE_EMPTY:
            return {"first_thing": "edge of the floor, then a drop", "distance_cells": i}
    return {"first_thing": "nothing, the floor is clear", "distance_cells": LOOK_AHEAD_CELLS}


def _horizontal_guardians(snap: Snapshot) -> list:
    """The guardians that the facts describe: only the horizontal ones.

    The snapshot also has the vertical guardians, and the map shows them, but
    the facts leave them out. See "Facts about vertical guardians made the
    results worse" in docs/findings.md. The look-ahead plays the real game,
    so it still removes a move that a vertical guardian makes deadly.
    """
    return [g for g in snap.guardians if g.axis == "horizontal"]


def patrol_covers(g, column: int, row: int) -> bool:
    """Is this cell in the patrol area of a horizontal guardian? A guardian is 2 x 2 cells."""
    return g.min_x <= column <= g.max_x + 1 and g.y <= row <= g.y + 1


MAX_SAFE_FALL_ROWS = 4  # Willy dies when he lands after a fall of 5 rows or more


def _fall_is_safe(snap: Snapshot, x: int, floor_row: int) -> bool:
    """Is the fall safe if Willy stands at column x and the floor goes away?

    Willy is 2 cells wide. The fall is not safe if a nasty or a guardian's
    patrol area is below one of his 2 columns, above the first solid tile.
    It is also not safe if the fall is too long. Willy lands on the first
    solid tile below either column, so the shorter drop counts.
    """
    drops = []
    for column in (x, x + 1):
        landing = ROWS
        for y in range(floor_row + 1, ROWS):
            tile = _tile(snap, column, y)
            if tile == TILE_NASTY:
                return False
            if tile != TILE_EMPTY:
                landing = y
                break
            # A guardian's patrol area (a guardian is 2 x 2 cells).
            for g in _horizontal_guardians(snap):
                if patrol_covers(g, column, y):
                    return False
        drops.append(landing - floor_row)
    return min(drops) <= MAX_SAFE_FALL_ROWS


def _way_down(snap: Snapshot, preferred_side: str = "", target_x: int | None = None):
    """The nearest safe place on Willy's floor where he can go down.

    That place is an edge of the floor or a crumbling floor. A crumbling
    floor breaks when Willy stands on it, and then Willy falls. A place is
    safe only if `_fall_is_safe` accepts it. A place on the target's side
    comes first.

    Each cell of a long crumbling floor is a way down. If Willy stands on
    one, the way down is the safe place on that floor nearest to the target.
    For example, in The Menagerie it is the place above the last key.
    """
    floor_row = snap.willy_y + 2

    def opening(x):
        return _tile(snap, x, floor_row) in (TILE_EMPTY, TILE_CRUMBLING)

    def falls_at(x):
        # Willy falls only when the floor is gone below his 2 columns.
        return opening(x) and opening(x + 1)

    here = snap.willy_x
    if falls_at(here) and _fall_is_safe(snap, here, floor_row):
        nearer = _safe_fall_nearer_to_target(snap, falls_at, target_x)
        if nearer is None:
            return {"what": "crumbling floor", "side": "Willy stands on it", "cell": (here, snap.willy_y)}
        side = "right" if nearer > here else "left"
        return {"what": "crumbling floor", "side": side, "horizontal_cells": abs(nearer - here),
                "cell": (nearer, snap.willy_y)}
    best = None
    for direction, side in ((-1, "left"), (+1, "right")):
        # `x` is Willy's column if he stands at the place.
        for i in range(1, COLS):
            x = snap.willy_x + direction * i
            body = [_tile(snap, c, r) for c in (x, x + 1) for r in (snap.willy_y, snap.willy_y + 1)]
            if TILE_WALL in body:
                break
            if TILE_NASTY in body:
                continue  # Willy cannot stand here
            if falls_at(x) and _fall_is_safe(snap, x, floor_row):
                under = {_tile(snap, x, floor_row), _tile(snap, x + 1, floor_row)}
                what = "crumbling floor" if TILE_CRUMBLING in under else "edge of the floor"
                found = {"what": what, "side": side, "horizontal_cells": i, "cell": (x, snap.willy_y)}
                # Prefer the way down on the target's side. Otherwise Willy
                # goes down on the wrong side and comes back up: a loop.
                if best is None or side == preferred_side or (
                    best["side"] != preferred_side and i < best["horizontal_cells"]
                ):
                    best = found
                break
    if best is None:
        return "none on this level"
    if falls_at(here):
        best["warning"] = "a nasty or a guardian is below the place where Willy stands"
    return best


def _safe_fall_nearer_to_target(snap: Snapshot, falls_at, target_x):
    """A column on Willy's crumbling floor, nearer to the target, where a fall is safe. None if there is none."""
    if target_x is None or target_x == snap.willy_x:
        return None
    floor_row = snap.willy_y + 2
    direction = 1 if target_x > snap.willy_x else -1
    best = None
    x = snap.willy_x + direction
    while falls_at(x) and abs(target_x - x) < abs(target_x - (x - direction)):
        body = [_tile(snap, c, r) for c in (x, x + 1) for r in (snap.willy_y, snap.willy_y + 1)]
        if TILE_WALL in body or TILE_NASTY in body:
            break
        if _fall_is_safe(snap, x, floor_row):
            best = x
        if TILE_CRUMBLING not in (_tile(snap, x, floor_row), _tile(snap, x + 1, floor_row)):
            break  # the floor is gone here: Willy falls and cannot walk across
        x += direction
    return best


SOLID = (TILE_FLOOR, TILE_CRUMBLING, TILE_CONVEYOR, TILE_WALL)
MAX_GAP_CELLS = 3  # a jump can go across a gap of this width


def _floor_row_under(snap: Snapshot, x: int, y: int, width: int = 1) -> int:
    """The row of the first solid tile below a thing: its floor level."""
    for row in range(y + 1, ROWS):
        if any(_tile(snap, x + dx, row) in SOLID for dx in range(width)):
            return row
    return ROWS


def _room_above(snap: Snapshot, x: int, y: int, ladder_fix: bool) -> bool:
    """Is there room for Willy above a landing place?

    With `ladder_fix`, a floor tile leaves room: a floor does not stop a jump
    from below, so single floor tiles can form a "ladder".
    """
    tile = _tile(snap, x, y)
    if ladder_fix:
        return tile not in (TILE_WALL, TILE_NASTY)
    return tile == TILE_EMPTY


def _find_ways_up(snap: Snapshot, ladder_fix: bool = False) -> dict:
    """The nearest place on each side where a jump gets Willy to a higher platform.

    The search goes along Willy's level to the left and to the right. It
    stops at a wall, and at a gap that is too wide for a jump.
    """
    floor_row = snap.willy_y + 2
    found = {}
    for direction, side in ((-1, "left"), (+1, "right")):
        front = snap.willy_x + 1 if direction > 0 else snap.willy_x
        gap = 0
        for i in range(1, COLS):
            x = front + direction * i
            if TILE_WALL in (_tile(snap, x, snap.willy_y), _tile(snap, x, snap.willy_y + 1)):
                # A low wall is also a platform: Willy can jump onto its top.
                top = snap.willy_y + 1 if _tile(snap, x, snap.willy_y) != TILE_WALL else snap.willy_y
                if _tile(snap, x, top - 1) == TILE_EMPTY and _tile(snap, x, top - 2) == TILE_EMPTY:
                    found[side] = {"side": side, "horizontal_cells": i, "rows_higher": floor_row - top, "cell": (x, snap.willy_y)}
                break
            gap = gap + 1 if _tile(snap, x, floor_row) == TILE_EMPTY else 0
            if gap > MAX_GAP_CELLS:
                break
            for rows_up in range(1, MAX_JUMP_ROWS + 1):
                y = floor_row - rows_up
                if _tile(snap, x, y) in SOLID and all(_room_above(snap, x, y - k, ladder_fix) for k in (1, 2)):
                    found[side] = {"side": side, "horizontal_cells": i, "rows_higher": rows_up, "cell": (x, snap.willy_y)}
                    break
            if side in found:
                break
    return found


def _way_up(snap: Snapshot, preferred_side: str, ladder_fix: bool = False):
    """The way up on the target's side, or else the nearest one."""
    found = _find_ways_up(snap, ladder_fix)
    if not found:
        return "none on this level"
    return found.get(preferred_side) or min(found.values(), key=lambda w: w["horizontal_cells"])


def _relative(snap: Snapshot, x: int, y: int, width: int = 1) -> dict:
    """The position of a thing relative to Willy, in words and in cells.

    `height` compares floor levels, not rows. A key that hangs above Willy's
    floor is on the same level: Willy gets it with a jump.
    """
    if x + width - 1 < snap.willy_x:
        side, dx = "left", snap.willy_x - (x + width - 1)
    elif x > snap.willy_x + 1:
        side, dx = "right", x - (snap.willy_x + 1)
    else:
        side, dx = "same column", 0
    willy_floor = snap.willy_y + 2
    thing_floor = _floor_row_under(snap, x, y, width)
    levels = willy_floor - thing_floor  # a positive value is a higher floor
    if snap.airborne:
        levels = 0 if abs(levels) <= 2 else levels
    height = "higher" if levels > 0 else "lower" if levels < 0 else "same level"
    return {
        "side": side,
        "horizontal_cells": dx,
        "horizontal_distance": _distance_word(dx),
        "height": height,
        # Do not use a signed number here. A test showed that jev reads
        # "rows_higher: 0" as "same level" when the thing is lower.
        "floor_rows_apart": abs(levels),
        "rows_above_its_floor": thing_floor - y - 1,
    }


def _target(snap: Snapshot, target) -> dict:
    """The target: the key or switch that jev selected, or the portal when no key is left."""
    if target is not None and tuple(target) in snap.switches:
        return {"what": "selected switch", **_target_relative(snap, *target)}
    if not snap.keys or target is None or tuple(target) not in snap.keys:
        if snap.keys:
            return {"what": "no target selected"}
        px, py = snap.portal
        return {"what": "exit portal (all keys collected)", **_target_relative(snap, px, py, 2)}
    return {"what": "selected key", **_target_relative(snap, *target)}


def _target_relative(snap: Snapshot, x: int, y: int, size: int = 1) -> dict:
    """A target's floor level, corrected when it hangs beyond Willy's jump reach.

    A shared floor does not make a high target reachable. Compare its bottom
    row with Willy's highest possible head position. The portal is two rows high.
    Keep the actual floor distance; it can be zero even for a high target.
    """
    relative = _relative(snap, x, y, size)
    if not snap.airborne and y + size - 1 < snap.willy_y - MAX_JUMP_REACH_ROWS:
        relative["height"] = "higher"
    return relative


def target_cell(snap: Snapshot, target):
    """The cell that Willy must go to: the selected key or switch, or the portal."""
    if target is not None and tuple(target) in snap.keys + snap.switches:
        return tuple(target)
    return snap.portal


def _key_facts(snap: Snapshot, x: int, y: int) -> dict:
    """Facts about one key or switch for the key decision."""
    floor = _floor_row_under(snap, x, y)
    # Walls on both sides of the key, in its row, at most 2 cells away.
    wall_left = any(_tile(snap, x - i, y) == TILE_WALL for i in (1, 2))
    wall_right = any(_tile(snap, x + i, y) == TILE_WALL for i in (1, 2))
    floor_type = {TILE_CRUMBLING: "crumbling floor", TILE_CONVEYOR: "conveyor"}.get(_tile(snap, x, floor), "floor")
    facts = {**_target_relative(snap, x, y), "floor_below_key": floor_type}
    if wall_left and wall_right:
        facts["between_walls"] = "yes"
        if floor_type == "crumbling floor":
            facts["one_way_trip"] = "yes: Willy falls through the crumbling floor and cannot go back up"
    return facts


def _amount_word(count: int) -> str:
    if count == 0:
        return "none"
    if count <= 10:
        return "a few"
    return "many" if count <= 30 else "very many"


def key_names(snap: Snapshot) -> dict:
    """The option name of each key and switch. A key's name uses its map letter."""
    names = {cell: f"key_{snap.key_letters[cell]}" for cell in snap.keys}
    names.update({cell: f"switch_{i + 1}" for i, cell in enumerate(snap.switches)})
    return names


def keys_state(snap: Snapshot, key_names: dict, memory: dict | None = None) -> dict:
    """The key decision's state without the map: facts about each key and switch.

    `memory` gives each key a short memory: {"current": cell, "used": {cell:
    decisions}, "gave_up": {cell: times}}. With it, jev can keep the target
    or change it.
    """
    facts = {key_names[k]: {"what": "key", **_key_facts(snap, *k)} for k in snap.keys}
    for cell in snap.switches:
        facts[key_names[cell]] = {
            "what": "switch. Willy flips it when he touches it. A switch changes the cavern: "
                    "it can open a wall or remove a danger.",
            **_key_facts(snap, *cell),
        }
    if memory is not None:
        for cell in snap.keys + snap.switches:
            fact = facts[key_names[cell]]
            if cell == memory.get("current"):
                fact["current_target"] = "yes"
            fact["decisions_used_for_it"] = _amount_word(memory["used"].get(cell, 0))
            if memory["gave_up"].get(cell, 0):
                fact["gave_up_on_it"] = f"{memory['gave_up'][cell]} times"
    return {"willy": {"standing_on": _standing_on(snap)}, "keys": facts}


SIDE_PREFERENCE_CELLS = 3  # a target that is nearer than this gives no preferred side


def _preferred_side(snap: Snapshot, x: int, y: int, width: int = 1) -> str:
    """The side where the search for a way up or a way down looks first.

    The state and `progress` must use the same side. Otherwise the way in
    the state and "nearer" point to different sides, and Willy goes left
    and right without end. See "The way down and `progress` must use the
    same side" in docs/findings.md. A target almost directly above or below
    Willy gives no preferred side, because one step would change the side.
    """
    rel = _relative(snap, x, y, width)
    if rel["side"] in ("left", "right") and rel["horizontal_cells"] >= SIDE_PREFERENCE_CELLS:
        return rel["side"]
    return ""


def _progress_reference(snap: Snapshot, target, ladder_fix: bool = False):
    """The cell that `progress` measures the distance to, and the text for `progress_measures`.

    Target on the same level: the target. On a higher floor: the way up. On
    a lower floor: the way down. There is only one reference, because two
    references that disagree make Willy go left and right.
    """
    tx, ty = target_cell(snap, target)
    width = 1 if snap.keys else 2
    height = _target_relative(snap, tx, ty, width)["height"]
    side = _preferred_side(snap, tx, ty, width)
    if height == "lower":
        way = _way_down(snap, side, tx)
        if isinstance(way, dict):
            return way["cell"], "distance to the way down"
    if height == "higher":
        way = _way_up(snap, side, ladder_fix)
        if isinstance(way, dict):
            return way["cell"], "distance to the way up"
    return (tx, snap.willy_y if height == "same level" else ty), "distance to the target"


LOOP_VISITS = 3  # a place with this number of visits is part of a loop


def _visits_word(visited, x, y) -> str:
    count = visited.get((x, y), 0)
    if count == 0:
        return "new place"
    if count < LOOP_VISITS:
        return "visited before"
    return "visited many times"


def moves_state(snap: Snapshot, outcomes: dict, target, visited, tried=frozenset(), ladder_fix: bool = False) -> dict:
    """The result of each valid move, from the look-ahead, and the moves that are not valid.

    `progress` (nearer, farther, same) compares the distance to one reference:
    the target, the way up, or the way down (see `progress_measures`). Two
    exceptions change the word: a move that uses the way up or the way down
    is "nearer", and a move that leaves the target's level is "farther".
    """
    (tx, ty), measure = _progress_reference(snap, target, ladder_fix)
    goal = target_cell(snap, target)
    same_level = _target_relative(snap, *goal, 1 if snap.keys else 2)["height"] == "same level"

    def distance(x, y):
        return abs(tx - x) + abs(ty - y)

    now = distance(snap.willy_x, snap.willy_y)
    moves, removed = {}, {}
    # If no move is safe, the moves into a dead end stay valid, with a
    # warning: Willy is alive after them, which is better than dying now.
    no_move_is_safe = all(o.dead for o in outcomes.values())
    kept = {}
    # A move has no effect only if another move gives the same game. The same
    # cell is not enough: the moves can differ in time, guardians, or floors.
    # `wait` is the one that stays, because it says that nothing is decided.
    for name in sorted(outcomes, key=lambda n: n != "wait"):
        o = outcomes[name]
        dead_end_only = o.dead and o.cause == DEAD_END_CAUSE
        if o.dead and not (no_move_is_safe and dead_end_only):
            removed[name] = f"kills Willy: {o.cause}"
            continue
        same = next((other for other in kept if o.same_result(outcomes[other])), None)
        if same:
            removed[name] = f"no effect: the same result as {same}"
            continue
        kept[name] = o
    for name, o in outcomes.items():
        if name not in kept:
            continue
        movement = movement_words(o.dx, o.dy)
        after = distance(o.x, o.y)
        progress = "nearer" if after < now else "farther" if after > now else "same"
        # A move that uses the way up or the way down is "nearer", even when
        # it goes past the reference cell.
        if (measure.endswith("way up") and o.dy > 0) or (measure.endswith("way down") and o.dy < 0):
            progress = "nearer"
        # The target is on Willy's level. A move that leaves this level is
        # "farther", even when it goes toward the target.
        if same_level and o.dy != 0 and not (o.keys_collected or o.complete):
            progress = "farther"
        floor_after = {_tile(snap, o.x + dx, o.y + 2) for dx in (0, 1)}
        result = {
            "movement": movement,
            "progress": progress,
            "place": _visits_word(visited, o.x, o.y),
            # Memory: did Willy make this move from this place before?
            "tried_from_here": "yes" if (snap.willy_x, snap.willy_y, name) in tried else "no",
        }
        if o.dead:
            result["warning"] = "dead end: Willy is alive after this move, but then no move is safe"
        if TILE_CRUMBLING in floor_after:
            result["ends_on"] = _crumbling_words(o.floor_rows_gone)
        if o.keys_collected:
            result["collects_key"] = True
        if o.complete:
            result["completes_cavern"] = True
        moves[name] = result
    removed = {n: removed[n] for n in outcomes if n in removed}  # the order of the moves
    return {"progress_measures": measure, "moves": moves, "moves_not_offered": removed or "none"}


def _guardians(snap: Snapshot) -> list[dict]:
    """Facts about each horizontal guardian, relative to Willy.

    For a guardian on Willy's level, the facts also say if Willy is in its
    patrol area, and how many cells it is to each end of that area.
    """
    out = []
    for g in _horizontal_guardians(snap):
        rel = _relative(snap, g.x, g.y, 2)
        facts = {k: rel[k] for k in ("side", "horizontal_cells", "horizontal_distance")}
        if rel["side"] == "same column":
            approach = "at Willy"
        elif rel["side"] == g.moving:
            approach = "away from Willy"
        else:
            approach = "toward Willy"
        facts["height"] = rel["height"]
        # Not `moves`: the state uses that name for the valid moves of Willy.
        facts["direction"] = approach
        if rel["height"] == "same level":
            # The patrol area: the columns that the guardian covers. `max_x` is
            # its left column at the right limit, so +1 adds its second column.
            left, right = g.min_x, g.max_x + 1
            # Willy covers columns willy_x and willy_x + 1.
            inside = snap.willy_x + 1 >= left and snap.willy_x <= right
            facts["willy_is_in_its_patrol_area"] = "yes" if inside else "no"
            if inside:
                # Cells from Willy's far side to each end, both ends counted.
                to_left, to_right = snap.willy_x + 1 - left + 1, right - snap.willy_x + 1
                facts["patrol_area_ends"] = {"cells_to_the_left": to_left, "cells_to_the_right": to_right}
        out.append(facts)
    return out


def _air_word(air: float) -> str:
    if air > 0.5:
        return "plenty"
    if air > 0.2:
        return "low"
    return "critical"


def words(snap: Snapshot, target=None, ladder_fix: bool = False) -> dict:
    """The move decision's facts that do not depend on the moves: Willy, the target, and the guardians.

    The target gets a `way_down` or a `way_up` when it is on a different floor.
    """
    target_words = _target(snap, target)
    goal = target_cell(snap, target)
    side = _preferred_side(snap, *goal, 1 if snap.keys else 2)
    if target_words.get("height") == "lower":
        target_words["way_down"] = _public(_way_down(snap, side, goal[0]))
    elif target_words.get("height") == "higher":
        target_words["way_up"] = _public(_way_up(snap, side, ladder_fix))
    return {
        "willy": {"facing": snap.willy_facing, "standing_on": _standing_on(snap)},
        "target": target_words,
        "keys_left": len(snap.keys),
        "to_the_left": _look(snap, -1),
        "to_the_right": _look(snap, +1),
        "guardians": _guardians(snap),
        "air": _air_word(snap.air),
    }


def movement_words(dx: int, dy: int) -> str:
    """The change of place in words. `dx` is cells to the right, `dy` is rows higher."""
    if dx == 0 and dy == 0:
        return "Willy stays in the same place"
    parts = []
    if dx:
        parts.append(f"{abs(dx)} {'cell' if abs(dx) == 1 else 'cells'} to the {'right' if dx > 0 else 'left'}")
    if dy:
        parts.append(f"{abs(dy)} {'row' if abs(dy) == 1 else 'rows'} {'higher' if dy > 0 else 'lower'}")
    return "Willy moves " + " and ".join(parts)


def _public(way):
    """The way without the `cell` field, which only the code uses."""
    return {k: v for k, v in way.items() if k != "cell"} if isinstance(way, dict) else way


# -- The states of the two decisions ------------------------------------------------
# The live run, the lab, and the request checks (checks.py) all build states with
# these functions, so the checks test the state that jev gets.


def move_request_state(snap: Snapshot, outcomes: dict, target, visited, tried,
                       settings: Settings | None = None) -> dict:
    """The complete state of a move decision, with the run's settings (the defaults if None)."""
    settings = settings or Settings()
    ladder_fix = settings.ladder_fix
    state = {**words(snap, target, ladder_fix), **moves_state(snap, outcomes, target, visited, tried, ladder_fix)}
    if settings.move_map:
        state = {**cavern_map(snap, settings.map_empty), **state}
    if not settings.progress_facts:
        state.pop("progress_measures", None)
        if isinstance(state["moves"], dict):
            for facts in state["moves"].values():
                facts.pop("progress", None)
    if not settings.guardian_facts:
        del state["guardians"]
    return state


def key_request_state(snap: Snapshot, names: dict, memory: dict | None, settings: Settings | None = None) -> dict:
    """The complete state of a key decision: the key facts, and the map if the settings ask for it."""
    settings = settings or Settings()
    state = keys_state(snap, names, memory)
    return {**cavern_map(snap, settings.map_empty), **state} if settings.map_key_decision else state
