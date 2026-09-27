"""The state that we send to jev: a game Snapshot changed into facts.

Jev reads text only. Jev is weak with coordinates and with large states. Thus
the state gives positions relative to Willy, in words and small numbers.

    cavern_map   the map of the cavern with its legend (for the key decision)
    keys_state   facts about each key and switch (for the key decision)
    words        facts about Willy, the target, and the guardians (for a move)
    moves_state  the true result of each valid move, from the look-ahead

The geometry facts (`way_up`, `way_down`, `progress`) are guesses of the code
from the tile map. Each of them was wrong in one cavern or more. Measure each
change (see the README).
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

# What each map cell means for Willy. The map legend has only the symbols
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
    """The meaning of each symbol that is on the map."""
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


LOOK_AHEAD_CELLS = 6  # how far the move facts look to the left and right
MAX_JUMP_ROWS = 2  # a jump can reach a platform that is 2 rows higher


# -- ASCII maps ---------------------------------------------------------------


def _grid(snap: Snapshot) -> list[list[str]]:
    """The tile map with the keys, switches, guardians, portal, and Willy on it."""
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
    # The portal comes after the guardians, thus a guardian does not hide the exit.
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


def cavern_map(snap: Snapshot) -> dict:
    """The full map of the cavern with its legend. Each string is one row."""
    rows = _rows(_grid(snap), 0, COLS - 1, 0, ROWS - 1)
    return {
        "map_legend": map_legend(rows, snap),
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


ALMOST_GONE_ROWS = 4  # one walk across a tile uses approximately 4 of its 8 pixel rows


def _crumbling_words(rows_gone: int) -> str:
    """A crumbling floor with its condition. Jev is weak with numbers, thus the condition is a word."""
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
    """The guardians that the facts describe.

    The snapshot also has the vertical guardians, and the map shows them. The
    facts do not: a measurement showed that facts about vertical guardians
    make the results worse. The look-ahead runs the real game, thus it removes
    a move that a vertical guardian makes deadly.
    """
    return [g for g in snap.guardians if g.axis == "horizontal"]


def patrol_covers(g, column: int, row: int) -> bool:
    """Is this cell in the patrol area of a horizontal guardian? A guardian is 2 x 2 cells."""
    return g.min_x <= column <= g.max_x + 1 and g.y <= row <= g.y + 1


MAX_SAFE_FALL_ROWS = 4  # Willy dies when he lands after a fall of 5 rows or more


def _fall_is_safe(snap: Snapshot, x: int, floor_row: int) -> bool:
    """Is the fall safe if Willy stands at column x and the floor goes away?

    Willy is 2 cells wide. The fall is not safe if a nasty or the patrol of
    a guardian is below one of his 2 columns, before the first solid tile. It
    is also not safe if the fall is too long: Willy lands on the first solid
    tile below one of his 2 columns.
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
            # The patrol of a guardian. A guardian is 2 cells wide and 2 cells high.
            for g in _horizontal_guardians(snap):
                if patrol_covers(g, column, y):
                    return False
        drops.append(landing - floor_row)
    return min(drops) <= MAX_SAFE_FALL_ROWS


def _way_down(snap: Snapshot, preferred_side: str = "", target_x: int | None = None):
    """The nearest safe place on the floor of Willy where he can go down.

    That place is an edge of the floor or a crumbling floor. A crumbling
    floor breaks when Willy stands on it, and then Willy falls. A place is
    safe only if no nasty is in the fall path. The code prefers a place on
    the side of the target.

    A long crumbling floor is a way down at each cell. If Willy stands on
    one, the way down is the safe place on that floor that is nearest to the
    target (The Menagerie: the place above the last key).
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
        # `x` is the column of Willy if he stands at the place.
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
                # Prefer the way down on the side of the target. If not, Willy
                # goes down on the wrong side and then comes back up: a loop.
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
    """The column on the crumbling floor of Willy, nearer to the target, where a fall is safe."""
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
    """The row of the first solid tile below a thing. This is its floor level."""
    for row in range(y + 1, ROWS):
        if any(_tile(snap, x + dx, row) in SOLID for dx in range(width)):
            return row
    return ROWS


def _find_ways_up(snap: Snapshot) -> dict:
    """The nearest place on each side where a jump gets Willy to a higher platform.

    The code looks along the level of Willy to the left and to the right. It
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
                if _tile(snap, x, y) in SOLID and all(_tile(snap, x, y - k) == TILE_EMPTY for k in (1, 2)):
                    found[side] = {"side": side, "horizontal_cells": i, "rows_higher": rows_up, "cell": (x, snap.willy_y)}
                    break
            if side in found:
                break
    return found


def _way_up(snap: Snapshot, preferred_side: str):
    """One way up, which the code selects: the one on the side of the target."""
    found = _find_ways_up(snap)
    if not found:
        return "none on this level"
    # Give the way up on the side of the target, if there is one. If not, the nearest.
    return found.get(preferred_side) or min(found.values(), key=lambda w: w["horizontal_cells"])




def _relative(snap: Snapshot, x: int, y: int, width: int = 1) -> dict:
    """The position of a thing relative to Willy, in words and in cells.

    `height` compares floor levels, not rows. A key that hangs above the floor
    of Willy is on the same level: Willy gets it with a jump.
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
        return {"what": "selected switch", **_relative(snap, *target)}
    if not snap.keys or target is None or tuple(target) not in snap.keys:
        if snap.keys:
            return {"what": "no target selected"}
        px, py = snap.portal
        return {"what": "exit portal (all keys collected)", **_relative(snap, px, py, 2)}
    return {"what": "selected key", **_relative(snap, *target)}


def target_cell(snap: Snapshot, target):
    """The cell that Willy must go to: the selected key or switch, or the portal."""
    if target is not None and tuple(target) in snap.keys + snap.switches:
        return tuple(target)
    return snap.portal


def _key_facts(snap: Snapshot, x: int, y: int) -> dict:
    """Facts about one key for the target question."""
    floor = _floor_row_under(snap, x, y)
    # Walls on the two sides of the key, in its row, not more than 2 cells away.
    wall_left = any(_tile(snap, x - i, y) == TILE_WALL for i in (1, 2))
    wall_right = any(_tile(snap, x + i, y) == TILE_WALL for i in (1, 2))
    floor_type = {TILE_CRUMBLING: "crumbling floor", TILE_CONVEYOR: "conveyor"}.get(_tile(snap, x, floor), "floor")
    facts = {**_relative(snap, x, y), "floor_below_key": floor_type}
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


def keys_state(snap: Snapshot, key_names: dict, memory: dict | None = None) -> dict:
    """The state for the question that selects the target key.

    `memory` is for the flexible target: {"current": cell, "used": {cell: decisions},
    "gave_up": {cell: times}}. It gives each key a short memory.
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
    """The side on which the code looks first for a way up or a way down.

    The state and the progress measure must use the same side. If not, the
    way in the state and "nearer" point to different sides, and jev goes left
    and right with no end (cavern 6). A target that is almost directly above
    or below Willy gives no preferred side: if it did, one step of Willy
    would change the side.
    """
    rel = _relative(snap, x, y, width)
    if rel["side"] in ("left", "right") and rel["horizontal_cells"] >= SIDE_PREFERENCE_CELLS:
        return rel["side"]
    return ""


def _progress_reference(snap: Snapshot, target):
    """The place that a move must get nearer to, and the name of that measure.

    Same level: the target. Higher floor: the way up. Lower floor: the way
    down. One measure for one purpose: two measures that do not agree make
    jev go left and right.
    """
    tx, ty = target_cell(snap, target)
    width = 1 if snap.keys else 2
    height = _relative(snap, tx, ty, width)["height"]
    side = _preferred_side(snap, tx, ty, width)
    if height == "lower":
        way = _way_down(snap, side, tx)
        if isinstance(way, dict):
            return way["cell"], "distance to the way down"
    if height == "higher":
        way = _way_up(snap, side)
        if isinstance(way, dict):
            return way["cell"], "distance to the way up"
    return (tx, snap.willy_y if height == "same level" else ty), "distance to the target"


LOOP_VISITS = 3  # a place with this number of visits is part of a loop


def _visit_count(visited, x, y) -> int:
    return visited.get((x, y), 0) if hasattr(visited, "get") else int((x, y) in visited)


def _visits_word(visited, x, y) -> str:
    count = _visit_count(visited, x, y)
    if count == 0:
        return "new place"
    if count < LOOP_VISITS:
        return "visited before"
    return "visited many times"


# The facts about the direction of each move (the setting `progress` of a run):
#   route  `progress` (nearer, farther, same) and `progress_measures`. The code measures
#          the distance to one reference (the target, the way up, or the way down), and
#          two rules of the code change the word: a move that uses the way up or the way
#          down is "nearer", and a move that leaves the level of the target is "farther".
#   plain  only measured distances, with no rules: `to_target`, and `to_way_up` or
#          `to_way_down` when the target is on a different floor. Jev decides which
#          distance is important.
#   none   no facts about the direction.
PROGRESS_FACTS = ("route", "plain", "none")


# The fields of the move state (the setting `move_facts` of a run). "full" is the
# normal state. The other sets keep only the facts of each move that they name,
# and no other part of the state: a test of which facts jev needs.
MOVE_FACT_SETS = {
    "full": None,
    "progress": ("progress",),
    "progress-goal": ("progress", "collects_key", "completes_cavern"),
    "progress-goal-memory": ("progress", "collects_key", "completes_cavern", "place", "tried_from_here"),
}


def reduced_move_state(state: dict, move_facts: str) -> dict:
    """The move state with only the facts of `move_facts`. The full state is returned unchanged."""
    keep = MOVE_FACT_SETS[move_facts]
    if keep is None:
        return state
    moves = state["moves"]
    if isinstance(moves, dict):
        moves = {name: {k: v for k, v in facts.items() if k in keep} for name, facts in moves.items()}
    return {"moves": moves}


def _compare(before: int, after: int) -> str:
    return "nearer" if after < before else "farther" if after > before else "same"


def moves_state(snap: Snapshot, outcomes: dict, target, visited, tried=frozenset(), progress_facts="route") -> dict:
    """The result of each macro, from the look-ahead. Deadly macros are separate."""
    (tx, ty), measure = _progress_reference(snap, target)
    goal = target_cell(snap, target)
    same_level = _relative(snap, *goal, 1 if snap.keys else 2)["height"] == "same level"

    def distance(x, y):
        return abs(tx - x) + abs(ty - y)

    def to_goal(x, y):
        return abs(goal[0] - x) + abs(goal[1] - y)

    now = distance(snap.willy_x, snap.willy_y)
    way_name = "to_way_up" if measure.endswith("way up") else "to_way_down" if measure.endswith("way down") else None
    moves, removed = {}, {}
    # A wait is valid only if something can change while Willy waits.
    guardian_near = any(g["height"] == "same level" for g in _guardians(snap))
    guardian_blocks = any(o.dead and o.cause in ("guardian", DEAD_END_CAUSE) for o in outcomes.values())
    wait_can_help = guardian_near or guardian_blocks or _standing_on(snap).startswith(("crumbling floor", "conveyor"))

    def is_useful(name, o):
        has_effect = o.dx or o.dy or o.keys_collected or o.complete
        return bool(has_effect) or (name == "wait" and wait_can_help)

    # If no safe move has an effect, the harmless moves stay in the list. A
    # move with no effect is always better than a move that kills Willy.
    some_move_is_useful = any(is_useful(n, o) for n, o in outcomes.items() if not o.dead)
    # If no move is safe, the dead end moves stay in the list. Willy is alive
    # after a dead end move, thus it is better than a move that kills him now.
    no_move_is_safe = all(o.dead for o in outcomes.values())
    for name, o in outcomes.items():
        dead_end_only = o.dead and o.cause == DEAD_END_CAUSE
        if o.dead and not (no_move_is_safe and dead_end_only):
            removed[name] = f"kills Willy: {o.cause}"
            continue
        if not o.dead and some_move_is_useful and not is_useful(name, o):
            # We know that this move is not valid, thus jev does not get it.
            removed[name] = "no effect: Willy stays in the same place"
            continue
        movement = movement_words(o.dx, o.dy)
        after = distance(o.x, o.y)
        progress = "nearer" if after < now else "farther" if after > now else "same"
        # A move that uses the way up or the way down is progress, also when
        # it goes past the reference cell.
        if (measure.endswith("way up") and o.dy > 0) or (measure.endswith("way down") and o.dy < 0):
            progress = "nearer"
        # The target is on the level of Willy. A move that leaves this level
        # is not progress, also when it goes in the direction of the target.
        if same_level and o.dy != 0 and not (o.keys_collected or o.complete):
            progress = "farther"
        floor_after = {_tile(snap, o.x + dx, o.y + 2) for dx in (0, 1)}
        result = {"movement": movement}
        if progress_facts == "route":
            result["progress"] = progress
        elif progress_facts == "plain":
            result["to_target"] = _compare(to_goal(snap.willy_x, snap.willy_y), to_goal(o.x, o.y))
            if way_name:
                result[way_name] = _compare(now, after)
        result |= {
            "place": _visits_word(visited, o.x, o.y),
            # Memory: did Willy select this move at this place before?
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
    out = {"progress_measures": measure} if progress_facts == "route" else {}
    return {**out, "moves": moves, "moves_not_offered": removed or "none"}


def _guardians(snap: Snapshot) -> list[dict]:
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
            # The patrol area: the columns that the guardian goes through.
            left, right = g.min_x, g.max_x + 1
            inside = snap.willy_x + 1 >= left and snap.willy_x <= right
            facts["willy_is_in_its_patrol_area"] = "yes" if inside else "no"
            if inside:
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


def words(snap: Snapshot, target=None) -> dict:
    target_words = _target(snap, target)
    goal = target_cell(snap, target)
    side = _preferred_side(snap, *goal, 1 if snap.keys else 2)
    if target_words.get("height") == "lower":
        target_words["way_down"] = _public(_way_down(snap, side, goal[0]))
    elif target_words.get("height") == "higher":
        target_words["way_up"] = _public(_way_up(snap, side))
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
        parts.append(f"{abs(dx)} cells to the {'right' if dx > 0 else 'left'}")
    if dy:
        parts.append(f"{abs(dy)} rows {'higher' if dy > 0 else 'lower'}")
    return "Willy moves " + " and ".join(parts)


def _public(way):
    """Remove the fields that are only for the code."""
    return {k: v for k, v in way.items() if k != "cell"} if isinstance(way, dict) else way










