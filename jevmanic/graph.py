"""The movement graph: where each move takes Willy, from each place that he can reach.

The route facts of the setting `graph_facts` come from this graph. The code
plays each move from each place in the emulator, with the guardians switched
off, and it saves the game at each new place. A node is Willy's pixel
position, his facing, the switches that are left, and the floor under his
feet: a crumbling floor changes while Willy stands on it. An edge is one move.
The number of moves to a key, a switch, or the portal comes from a search
backward from the edges that touch it.

The graph ignores the guardians, so a way in the graph can still need good
timing. See "Route facts from a movement graph" in docs/findings.md.
"""

from collections import deque
from dataclasses import dataclass

from .game import (
    ADDR_HGUARDS,
    ADDR_VGUARDS,
    ADDR_WILLY_ATTR,
    ADDR_WILLY_DIR,
    ADDR_WILLY_PIXEL_Y,
    COLS,
    ROWS,
    TILE_CRUMBLING,
    Game,
    Outcome,
    Snapshot,
)

# The graph saves the game at each node, in the slots from GRAPH_SLOT up. They are
# above all other slots, and `explore` frees them at its end.
GRAPH_SLOT = 20000
# A graph has at most this number of nodes. The caverns with many crumbling floors
# (The Vat, The Warehouse) reach it, because each state of a crumbling floor under
# Willy is a node.
MAX_NODES = 6000
# A special enemy (Eugene, the Kong Beast, a Skylab) is not in the guardian lists, so
# it stays. A move that it makes deadly is tried again after up to this number of waits.
WAIT_RETRIES = 4
# After a crumbling floor breaks, the graph is made again when it is this number of
# decisions old. A new graph takes up to 30 seconds in the caverns with many crumbling floors.
STALE_DECISIONS = 5
DEAD, DONE = "dead", "done"
NO_WAY_BACK = "no way back: a key or the portal is out of reach after it"


def feet(game: Game) -> tuple:
    """The pixels of the two cells below Willy. They change while a crumbling floor breaks."""
    x, y = game._cell(game._word(ADDR_WILLY_ATTR))
    row = y + 2 if game._willy_pixel()[1] % 8 == 0 else y + 3
    if row >= ROWS:
        return ()
    return tuple(game._cell_pixels(c, row) for c in (x, x + 1) if c < COLS)


def node_key(game: Game) -> tuple:
    px, py = game._willy_pixel()
    return (px, py, game.emu.peek(ADDR_WILLY_DIR) & 1, tuple(game._switches()), feet(game))


def place(node: tuple) -> tuple:
    """A node without the floor under the feet: Willy's pixel position, his facing, and the switches."""
    return node[:4]


def place_after(outcome: Outcome) -> tuple:
    """The place where a move of the look-ahead ends."""
    after = outcome.snapshot
    return (outcome.pixel[0], outcome.pixel[1], 1 if after.willy_facing == "left" else 0, tuple(after.switches))


@dataclass(frozen=True)
class Edge:
    dest: object  # a node, DEAD, or DONE (the move completes the cavern)
    touched: frozenset  # the cells that Willy covers during the move
    waits: int = 0  # waits before the move, when a special enemy makes it deadly at first


class MovementGraph:
    """The places that Willy can reach from the present game, and the moves between them."""

    def __init__(self, game: Game, moves: dict, max_nodes: int = MAX_NODES):
        self.game, self.moves, self.max_nodes = game, moves, max_nodes
        self.edges: dict[tuple, dict[str, Edge]] = {}
        self.start = None
        self.truncated = False
        self._back = None
        # For a way from the start: the node and the moves before each node, on the first way found.
        self.parent: dict[tuple, tuple] = {}

    def explore(self) -> "MovementGraph":
        """Play each move from each place, with the guardians off. The game does not change."""
        game, emu = self.game, self.game.emu
        ticks = game.tick_count
        emu.save_state(GRAPH_SLOT - 1)
        # A guardian list that ends at its first entry: no guardians.
        emu.poke(ADDR_HGUARDS, 255)
        emu.poke(ADDR_VGUARDS, 255)
        self.start = node_key(game)
        slots = {self.start: GRAPH_SLOT}
        emu.save_state(GRAPH_SLOT)
        queue = deque([self.start])
        while queue:
            node = queue.popleft()
            out = {}
            for move in self.moves:
                edge = self._try(node, move, slots[node])
                out[move] = edge
                if edge.dest in (DEAD, DONE) or edge.dest in slots:
                    continue
                if len(slots) >= self.max_nodes:
                    self.truncated = True
                    continue
                slots[edge.dest] = GRAPH_SLOT + len(slots)
                emu.save_state(slots[edge.dest])
                self.parent[edge.dest] = (node, ["wait"] * edge.waits + [move])
                queue.append(edge.dest)
            self.edges[node] = out
        emu.load_state(GRAPH_SLOT - 1)
        emu.set_joystick(0)
        game.tick_count = ticks
        emu.clear_states(GRAPH_SLOT - 1)
        return self

    def _play(self, move: str) -> frozenset:
        """Play one move. Returns the cells that Willy covers on the way (a key there is collected)."""
        game = self.game
        touched = set()
        for _ in game.macro_ticks(move):
            if game.is_dead() or game.is_complete():
                break
            x, y = game._cell(game._word(ADDR_WILLY_ATTR))
            rows = 2 if (game.emu.peek(ADDR_WILLY_PIXEL_Y) // 2) % 8 == 0 else 3
            touched.update((x + dx, y + dy) for dx in (0, 1) for dy in range(rows))
        return frozenset(touched)

    def _try(self, node: tuple, move: str, slot: int) -> Edge:
        """The edge of one move from one node. The game is at the end of the move afterwards."""
        game, emu = self.game, self.game.emu
        emu.load_state(slot)
        emu.set_joystick(0)
        touched = self._play(move)
        waits = 0
        while game.is_dead() and waits < WAIT_RETRIES:
            waits += 1
            emu.load_state(slot)
            emu.set_joystick(0)
            for _ in range(waits):
                game.run_macro("wait")
            if game.is_dead() or node_key(game) != node:
                # The waits kill Willy, or change his place or his floor: the move stays deadly.
                return Edge(DEAD, touched)
            touched = self._play(move)
        if game.is_dead():
            return Edge(DEAD, touched)
        # A move can go into the portal in the air, so this test comes before the next one.
        if game.is_complete():
            return Edge(DONE, touched, waits)
        if game.is_airborne():
            return Edge(DEAD, touched)  # Willy did not land: no edge
        return Edge(node_key(game), touched, waits)

    def way_from_start(self, hit) -> list[str] | None:
        """The moves of a short way from the start through an edge for which `hit(edge)` is true, or None.

        The way uses the first way found to each node, so it is not always the shortest.
        """
        best = None
        for node, out in self.edges.items():
            for move, edge in out.items():
                if edge.dest == DEAD or not hit(edge):
                    continue
                moves, at = ["wait"] * edge.waits + [move], node
                while at in self.parent:
                    at, before = self.parent[at]
                    moves = before + moves
                if best is None or len(moves) < len(best):
                    best = moves
        return best

    def moves_to(self, hit) -> dict[tuple, int]:
        """The smallest number of moves from each node to an edge for which `hit(edge)` is true.

        The edge that hits counts as one move. A node that is not in the result has no way there.
        """
        if self._back is None:
            self._back = {}
            for node, out in self.edges.items():
                for edge in out.values():
                    if edge.dest not in (DEAD, DONE):
                        self._back.setdefault(edge.dest, []).append(node)
        found = {node: 1 for node, out in self.edges.items()
                 if any(edge.dest != DEAD and hit(edge) for edge in out.values())}
        queue = deque(found)
        while queue:
            node = queue.popleft()
            for before in self._back.get(node, ()):
                if before not in found:
                    found[before] = found[node] + 1
                    queue.append(before)
        return found

    def moves_to_cell(self, cell: tuple) -> dict[tuple, int]:
        """Moves from each node to the collection of a key or a switch at `cell`."""
        return self.moves_to(lambda edge: cell in edge.touched)

    def moves_to_finish(self) -> dict[tuple, int]:
        """Moves from each node into the open portal. Empty while a key is left."""
        return self.moves_to(lambda edge: edge.dest == DONE)


@dataclass
class RouteFacts:
    """The route facts of one move decision, from the movement graph."""

    now: int | None  # moves from Willy's place to the target; None: no way from here
    after: dict  # move name -> moves to the target after the move, or None
    no_way_back: dict  # move name -> the reason, for each move after which a key or the portal is out of reach


class Routes:
    """The movement graph of one run. It is made again when the cavern changes."""

    def __init__(self, game: Game, moves: dict):
        self.game, self.moves = game, moves
        self.graph: MovementGraph | None = None
        self.signature = None
        self.since = 0
        self.explorations = 0
        self._places: dict[tuple, list] = {}
        self._maps: dict = {}

    @staticmethod
    def _signature(snap: Snapshot) -> tuple:
        crumbling = frozenset((x, y) for y, row in enumerate(snap.tiles) for x, tile in enumerate(row)
                              if tile == TILE_CRUMBLING)
        return crumbling, tuple(snap.switches), not snap.keys

    def update(self, snap: Snapshot, outcomes: dict | None = None) -> tuple:
        """Make the graph again if it is old. Returns Willy's place.

        The graph is old if a switch was flipped, the last key was collected,
        Willy or the end of a safe move is not in it, or a crumbling floor
        broke and the graph is STALE_DECISIONS decisions old.
        """
        signature = self._signature(snap)
        here = place(node_key(self.game))

        def missing():
            ends = [place_after(o) for o in (outcomes or {}).values() if not o.dead]
            return here not in self._places or any(p not in self._places for p in ends)

        if (self.graph is None or signature[1:] != self.signature[1:] or missing()
                or (signature != self.signature and self.since >= STALE_DECISIONS)):
            self.graph = MovementGraph(self.game, self.moves).explore()
            self.signature, self.since, self._maps = signature, 0, {}
            self.explorations += 1
            self._places = {}
            for node in self.graph.edges:
                self._places.setdefault(place(node), []).append(node)
        return here

    def _moves_to(self, cell: tuple | None) -> tuple[dict, dict]:
        """Moves to a key or a switch (or into the portal if `cell` is None), for each node and for each place."""
        if cell not in self._maps:
            nodes = self.graph.moves_to_cell(cell) if cell is not None else self.graph.moves_to_finish()
            places = {}
            for node, moves in nodes.items():
                p = place(node)
                places[p] = min(moves, places.get(p, moves))
            self._maps[cell] = (nodes, places)
        return self._maps[cell]

    def reachable(self, snap: Snapshot, goal: tuple | None) -> bool:
        """Is there a way from Willy's place to a key or a switch?"""
        here = self.update(snap)
        return goal is not None and self._moves_to(goal)[1].get(here) is not None

    def move_facts(self, snap: Snapshot, outcomes: dict, goal: tuple | None, no_way_back: bool) -> RouteFacts:
        """The moves to the goal (a key or a switch, or the portal if None) now and after each safe move.

        Call it once for each move decision: it counts the decisions for STALE_DECISIONS.
        """
        self.since += 1
        here = self.update(snap, outcomes)
        places = self._moves_to(goal)[1]
        after = {}
        for name, o in outcomes.items():
            if o.dead:
                continue
            reached = o.complete if goal is None else goal not in o.snapshot.keys + o.snapshot.switches
            after[name] = 0 if reached else places.get(place_after(o))
        cut = {}
        if no_way_back:
            for name, o in outcomes.items():
                end = place_after(o)
                if o.dead or o.complete or end not in self._places:
                    continue  # a place that is not in the graph proves nothing
                left = [k for k in snap.keys if k in o.snapshot.keys]
                targets = left if snap.keys else [None]
                if any(self._moves_to(t)[1].get(here) is not None and self._moves_to(t)[1].get(end) is None
                       for t in targets):
                    cut[name] = NO_WAY_BACK
        return RouteFacts(places.get(here), after, cut)

    def valid_goals(self, snap: Snapshot, goals: list) -> list:
        """The keys and switches that Willy can reach now, without the keys that leave another key out of reach.

        A key stays if some move collects it and ends at a place from which
        each other key is still in reach. If no goal passes, the reachable goals
        stay, and if none is reachable, all goals stay.
        """
        here = self.update(snap)
        reachable = [g for g in goals if self._moves_to(g)[1].get(here) is not None]
        valid = [g for g in reachable if g not in snap.keys or len(snap.keys) == 1
                 or self._keeps_other_keys(g, [k for k in snap.keys if k != g])]
        return valid or reachable or list(goals)

    def _keeps_other_keys(self, key: tuple, others: list) -> bool:
        maps = [self._moves_to(k)[0] for k in others]
        for out in self.graph.edges.values():
            for edge in out.values():
                if edge.dest == DEAD or key not in edge.touched:
                    continue
                if edge.dest == DONE or all(m.get(edge.dest) is not None or k in edge.touched
                                            for m, k in zip(maps, others)):
                    return True
        return False
