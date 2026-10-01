"""What can any joystick input reach? A search over single game ticks, with the guardians off.

The moves of the harness (walks, jumps, and waits) end on the cell grid. This
search presses any input at each game tick instead, so it shows what the game
itself allows. It explores from the start of each cavern, and it reports each
key and switch that Willy can touch. A second search starts with all keys
collected, and it reports if Willy can enter the portal.

A node is a moment when Willy is on the ground: his pixel position, the game's
direction and movement flags, the switches that are left, and the floor under
his feet. From each node, the search tries each input for one tick. If Willy
is then in the air, it holds each of nothing, left, and right until he lands.

Run:  uv run python -m experiments.tick_search --caverns 5,6,12,19

Eugene (cavern 5) stays when the guardians are off, and he closes the portal
after the last key, so the portal test proves nothing there. The Vat and The
Warehouse reach the node limit. No jev requests.
"""

import argparse
import time
from collections import deque

from jevmanic.game import (ADDR_HGUARDS, ADDR_ITEMS, ADDR_VGUARDS, ADDR_WILLY_ATTR, ADDR_WILLY_DIR, JOY_FIRE,
                           JOY_LEFT, JOY_RIGHT, Game)
from jevmanic.graph import feet

SLOT = 30000
INPUTS = (0, JOY_LEFT, JOY_RIGHT, JOY_FIRE, JOY_FIRE | JOY_LEFT, JOY_FIRE | JOY_RIGHT)
HOLDS = (0, JOY_LEFT, JOY_RIGHT)
MAX_AIR_TICKS = 60


def key(game: Game) -> tuple:
    px, py = game._willy_pixel()
    return px, py, game.emu.peek(ADDR_WILLY_DIR) & 3, tuple(game._switches()), feet(game)


def cover(game: Game, touched: set):
    x, y = game._cell(game._word(ADDR_WILLY_ATTR))
    rows = 2 if game._willy_pixel()[1] % 8 == 0 else 3
    touched.update((x + dx, y + dy) for dx in (0, 1) for dy in range(rows))


def search(game: Game, max_nodes: int) -> tuple[set, bool, int]:
    """All cells that Willy touches, if he enters the portal, and the number of nodes."""
    emu = game.emu
    emu.poke(ADDR_HGUARDS, 255)
    emu.poke(ADDR_VGUARDS, 255)
    slots = {key(game): SLOT}
    emu.save_state(SLOT)
    queue, touched_all, done = deque(slots), set(), False

    def add():
        k = key(game)
        if k not in slots and len(slots) < max_nodes:
            slots[k] = SLOT + len(slots)
            emu.save_state(slots[k])
            queue.append(k)

    while queue:
        node = queue.popleft()
        for joystick in INPUTS:
            emu.load_state(slots[node])
            game._tick(joystick)
            if game.is_complete():
                done = True
                continue
            if game.is_dead():
                continue
            touched = set()
            cover(game, touched)
            if not game.is_airborne():
                touched_all |= touched
                add()
                continue
            emu.save_state(SLOT - 1)
            for hold in HOLDS:
                emu.load_state(SLOT - 1)
                path = set(touched)
                for _ in range(MAX_AIR_TICKS):
                    game._tick(hold)
                    if game.is_complete():
                        done = True
                        break
                    if game.is_dead():
                        break
                    cover(game, path)
                    if not game.is_airborne():
                        touched_all |= path
                        add()
                        break
    emu.clear_states(SLOT - 1)
    return touched_all, done, len(slots)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--caverns", default="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20")
    parser.add_argument("--max-nodes", type=int, default=40000)
    args = parser.parse_args()
    game = Game()
    names = game.cavern_names()
    for cavern in [int(c) - 1 for c in args.caverns.split(",")]:
        start = time.time()
        game.select_cavern(cavern)
        snap = game.snapshot()
        touched, _, nodes = search(game, args.max_nodes)
        found = [f"{snap.key_letters[k]} {'yes' if k in touched else 'NO'}" for k in snap.keys]
        found += [f"switch {i + 1} {'yes' if s in touched else 'NO'}" for i, s in enumerate(snap.switches)]
        game.select_cavern(cavern)
        for i in range(5):  # all keys collected: the portal is open
            if game.emu.peek(ADDR_ITEMS + i * 5) == 255:
                break
            game.emu.poke(ADDR_ITEMS + i * 5, 0)
        game._tick(0)
        _, done, open_nodes = search(game, args.max_nodes)
        full = " (node limit)" if max(nodes, open_nodes) >= args.max_nodes else ""
        print(f"{cavern + 1:2} {names[cavern][:30]:30} keys: {', '.join(found)} | portal: {'yes' if done else 'NO'}"
              f"{full} ({time.time() - start:.0f} s)", flush=True)


if __name__ == "__main__":
    main()
