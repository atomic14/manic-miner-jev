"""Can a move set complete each cavern, if the guardians are off?

The script follows a short way to each key in turn with the emulator: first
in the cavern's optimum key order, then in other orders. On the way to a key
it prefers a way after which the other keys are still in reach, and it flips
a switch first if a key is out of reach. A found route proves that the move
set can complete the cavern without guardians. If no order works, the move
set probably cannot, but that is no proof: the script tries only some ways.

Run:  uv run python -m experiments.solvable --caverns 5,6,12,19
      uv run python -m experiments.solvable --caverns 5,6,12,19 --half-steps

Eugene (cavern 5) stays when the guardians are off, and he closes the portal
after the last key. So a failure in cavern 5 after all keys proves nothing.
No jev requests.
"""

import argparse
import itertools
import time

from jevmanic.game import ADDR_HGUARDS, ADDR_VGUARDS, ALL_MOVES, MACROS, Game
from jevmanic.graph import DEAD, DONE, MovementGraph
from jevmanic.key_orders import OPTIMUM_KEY_ORDER

SLOT = 15000  # below the graph's slots, which each exploration frees


def play(game: Game, moves: list[str]) -> bool:
    """Play moves with the guardians off. False if Willy dies."""
    for move in moves:
        game.emu.poke(ADDR_HGUARDS, 255)
        game.emu.poke(ADDR_VGUARDS, 255)
        game.run_macro(move)
        if game.is_dead():
            return False
    return True


def safe_way(graph: MovementGraph, cell: tuple, others: list) -> list[str] | None:
    """A way to the cell after which each cell in `others` is still in reach, or else any way."""
    maps = [graph.moves_to_cell(other) for other in others]

    def keeps_others(edge):
        return cell in edge.touched and edge.dest != DEAD and (
            edge.dest == DONE or all(m.get(edge.dest) is not None or o in edge.touched for m, o in zip(maps, others)))

    return graph.way_from_start(keeps_others) or graph.way_from_start(lambda edge: cell in edge.touched)


def go(game: Game, moves: dict, hit_cell: tuple | None, others: list) -> int | None:
    """Play a way to a key (or into the portal if `hit_cell` is None). The number of moves, or None."""
    graph = MovementGraph(game, moves).explore()
    way = graph.way_from_start(lambda e: e.dest == DONE) if hit_cell is None else safe_way(graph, hit_cell, others)
    if way is None:
        for switch in game.snapshot().switches:
            to_switch = graph.way_from_start(lambda e, s=switch: s in e.touched)
            if to_switch and play(game, to_switch):
                rest = go(game, moves, hit_cell, others)
                return None if rest is None else len(to_switch) + rest
        return None
    return len(way) if play(game, way) else None


def solve(cavern: int, moves: dict, max_orders: int, orders: list | None = None):
    game = Game(cavern=cavern)
    snap = game.snapshot()
    letters = {snap.key_letters[k]: k for k in snap.keys}
    optimum = OPTIMUM_KEY_ORDER[cavern]
    if orders is None:
        others = ["".join(p) for p in itertools.permutations(sorted(letters)) if "".join(p) != optimum]
        # Take the first keys in turn, so that a few orders already try each first key.
        groups = {}
        for order in others:
            groups.setdefault(order[0], []).append(order)
        orders = [optimum] + [o for batch in itertools.zip_longest(*groups.values()) for o in batch if o]
    game.emu.save_state(SLOT)
    failures = []
    for order in orders[:max_orders]:
        game.emu.load_state(SLOT)
        game.emu.set_joystick(0)
        total = 0
        for i, letter in enumerate(order):
            cell = letters[letter]
            if cell not in game.snapshot().keys:
                continue  # collected on the way to an earlier key
            left = [k for k in game.snapshot().keys if k != cell]
            n = go(game, moves, cell, left)
            if n is None:
                failures.append(f"{letter} out of reach after {order[:i] or 'the start'}")
                break
            total += n
        else:
            n = go(game, moves, None, [])
            if n is not None:
                return order, total + n, failures
            failures.append(f"portal out of reach after {order}")
    return None, None, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--caverns", default="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20")
    parser.add_argument("--half-steps", action="store_true", help="the move set with the two half steps")
    parser.add_argument("--orders", type=int, default=24, help="the most key orders to try (default 24)")
    parser.add_argument("--order", help="try only these key orders, for example CDEAB,DECAB")
    args = parser.parse_args()
    moves = ALL_MOVES if args.half_steps else MACROS
    names = Game().cavern_names()
    for cavern in [int(c) - 1 for c in args.caverns.split(",")]:
        start = time.time()
        orders = args.order.split(",") if args.order else None
        order, total, failures = solve(cavern, moves, args.orders, orders)
        result = f"route with the key order {order} in {total} moves" if order else "no route found"
        why = "; ".join(sorted(set(failures))[:6])
        print(f"{cavern + 1:2} {names[cavern][:30]:30} {result} ({time.time() - start:.0f} s)"
              + (f" | {why}" if not order else ""), flush=True)


if __name__ == "__main__":
    main()
