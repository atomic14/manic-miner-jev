# The design

This document describes the present design: how a decision works, which
moves jev gets, and the exact data of each request. The
[README](../README.md) explains the project, the terms, and the results.
[findings.md](findings.md) gives the measurements behind each part.

## One decision

The harness stops the game before each move. Then:

1. It reads the game from the emulator's memory: Willy, the guardians, the
   keys, the switches, the portal, the tiles, and the air.
2. **Look-ahead**: it plays each of the 6 moves in the emulator, and after
   each one it restores the game. This gives the true result of each move.
3. It removes each move that is not valid (see "Valid moves").
4. It builds the state: a JSON object with words and small numbers.
5. Jev gets the state and the question, and selects one move. This is a
   **move decision**.
6. The emulator plays the move. Then the next decision starts.

Before some move decisions, jev also makes a **key decision**: it selects
the target. The key decision comes at the start, after Willy collects a key
or flips a switch, and again 25 decisions after the last key decision. It
has one option for each key and each switch that is left.

The harness makes no jev request when only one move is valid. This
includes the case where all other safe moves give the same game as that
move. The log file and the
viewer mark such a decision "no jev call".

| The harness | Jev |
| --- | --- |
| Reads positions and turns them into facts | Selects the target |
| Plays each move ahead and gives its true result | Selects each move |
| Does not offer a move that is not valid | |
| Remembers the places that Willy visited and the moves that he tried there | |

## Valid moves

Jev gets only the valid moves. A move is not valid in three cases:

1. **It is deadly**: it kills Willy.
2. **It goes into a dead end**: Willy is alive after it, but then he cannot
   stay alive. The **dead-end check** finds this. It looks for one sequence
   of 4 moves that keeps Willy alive. If there is no such sequence, the move
   goes into a dead end. Example: a guardian follows Willy one cell behind
   him toward a wall. Each step is safe, but after 5 steps no move is safe.
   The check asks only "can Willy stay alive?". It ignores the keys and the
   portal, and it does not select a move. The check has a budget of moves.
   If the budget runs out before the answer is known, the check proves
   nothing, and the move stays valid.
3. **It has no effect**: another valid move gives the same game. The
   comparison uses the whole game after each move: Willy's pixel position
   and facing, the guardians, the floors, the keys, and the time. The same
   cell is not enough. For example, `jump_up` and `wait` both end in
   Willy's cell, but they leave a crumbling floor in different conditions.
   When two moves give the same game, `wait` stays, or else the first move.

If no move is safe, jev gets the least bad moves: the dead-end moves (with
a warning), or else all moves.

With the option `--no-way-back`, a move is also not valid if it leaves a key
or the portal out of reach. Willy can reach it now, but the movement graph
has no way to it after the move (see "Route facts from the movement graph").
If each safe move is such a move, they all stay. A key or a switch is not an
option of the key decision if Willy cannot reach it now. A key is not an
option either if another key is out of reach after it.

## The conveyor hold

A conveyor carries Willy. In the game, Willy stands still on a conveyor only
if the input in the opposite direction is held when he lands on it, and only
while it stays held. The moves use this:

- A fall onto a conveyor holds against it, so Willy stands still when he
  lands.
- `wait` on a conveyor holds against it.
- A walk in the conveyor's direction lets the conveyor carry Willy.

## Route facts from the movement graph

The route facts are `progress` and `progress_measures`, and the target's
`way_up` and `way_down`. By default they come from rules about the tile map
(`jevmanic/describe.py`). Three options give route facts from the emulator
instead:

- `--graph`: the harness builds a movement graph (`jevmanic/graph.py`). It
  plays each move from each place that Willy can reach, with the guardians
  switched off. A node is Willy's pixel position, his facing, the switches
  that are left, and the floor under his feet. An edge is one move. `progress`
  then compares the number of moves on the shortest way to the target, before
  and after the move. The target has no `way_up` and no `way_down`, because
  the tile rules can disagree with the graph.
- `--half-steps`: two more moves, `step_left` and `step_right`. Each one moves
  Willy half a cell (4 pixels). A walk always ends on the cell grid, and some
  jumps must start between two cells.
- `--no-way-back` (with `--graph`): the moves and the keys that leave a key
  or the portal out of reach are not offered (see "Valid moves").

The graph ignores the guardians, so a way in the graph can still need good
timing, and the look-ahead still removes each deadly move. A special enemy
(Eugene, the Kong Beast, a Skylab) is not in the guardian lists, so the graph
keeps it. A move that it makes deadly is tried again after a few waits.

The harness builds the graph again in these cases:

- a switch is flipped, or the last key is collected;
- Willy, or the end of a safe move, is not in the graph;
- a crumbling floor has broken, and the graph is five decisions old.

A graph has at most 6,000 nodes. The caverns with many crumbling floors (The
Vat, The Warehouse) reach this limit, and a graph takes up to 30 seconds
there.

## Instruction sets

An **instruction set** is a folder in `jevmanic/instructions/<name>/` with
three plain text files: `move.txt`, `key.txt`, and `key_facts_only.txt`. The
files have no markup, because the jev documentation says that jev reads the
words as they are. With each set, jev gets the same states, the same
options, and the same schedule of requests. So the text is the only
difference between two sets.

- `promptD` is the default set. It gives the goal, the meaning of each fact,
  and knowledge of the game (for example "a crumbling floor breaks a little
  each time Willy stands on it"). It has no instructions of the form "select
  X when Y".
- `promptA` produced the results in the README. It is the same as promptD,
  but it says that each move in `moves` is safe and has an effect. That is
  not always true: a dead-end move stays when no move is safe. In Central Cavern, promptD
  completed 18 of 20 runs and promptA 20 of 20. This difference can be
  chance. We did not compare the two sets in other caverns.
- `promptD-map` is promptD with one more sentence: the state also has the
  present cavern map and its legend. It is for `--move-map`.
- `promptD-map-noprogress` is promptD-map without the sentence about
  `progress`. It is for `--move-map --no-progress-facts`.
- `promptD-graph` is promptD without the sentence about loops ("If Willy
  comes back to the same places again and again, the direct way is closed").
  It is for `--graph`: with route facts from the graph, "nearer" is on the
  shortest way, and the sentence can take Willy away from it.
- `promptC` is a very short text for Laya, a different decision model (see
  "Laya instead of jev" in [findings.md](findings.md)).

Two parts of the design come close to the limit of the project principle:

- `progress` has two adjustments: a move that uses the way up or the way
  down is "nearer", and a move that leaves the target's level is "farther".
  So `progress` contains route knowledge, and it comes close to marking the
  correct move (see "Questions and criticisms" in the README).
- One sentence of the move text tells jev when it can leave "nearer": "If
  Willy comes back to the same places again and again, the direct way is
  closed, and he must go a different way, even if that way goes away from
  the target first." In Central Cavern, jev completes 0 of 20 runs without
  this sentence and 20 of 20 with it (with a smaller state).

## The data that we give to jev

Jev reads text only. It cannot read a screenshot. Jev is weak with
coordinates, with counts, and with large states. So the state gives
positions relative to Willy, in words and small numbers.

All examples below come from the recorded run
`demo/cavern-02-the-cold-room-promptA.jsonl` (The Cold Room, promptA). The
exact texts are in `jevmanic/instructions/`. The code that builds the state
is in `jevmanic/describe.py`. The viewer shows the exact state and question
of each request.

### Request 1: the key decision

The state has the cavern map with its legend. It also has one entry of facts
for each key that is left, and for each switch that is not flipped. This
example shows the full legend and 2 of the 5 keys:

```json
{
  "map_legend": {
    "W": "Willy. He is 2 cells wide and 2 cells high.",
    "A": "key A. Willy collects it when he touches it.",
    "B": "key B. Willy collects it when he touches it.",
    "C": "key C. Willy collects it when he touches it.",
    "D": "key D. Willy collects it when he touches it.",
    "E": "key E. Willy collects it when he touches it.",
    "P": "the exit portal, 2 cells wide and 2 cells high. Willy can enter it when he has all keys.",
    "G": "a guardian, 2 cells wide and 2 cells high. It moves. It kills Willy on contact.",
    "X": "a nasty. It does not move. It kills Willy on contact.",
    "=": "floor. Willy can stand on it. It does not stop a jump from below.",
    "~": "crumbling floor. Willy can stand on it. It breaks a little each time Willy stands on it, and then it is gone.",
    ">": "conveyor. Willy can stand on it. It moves Willy to the right.",
    "#": "wall. It stops Willy. Willy can stand on top of it.",
    ".": "empty space."
  },
  "map_note": "Each string is one row. The first row is the top of the cavern.",
  "map": [
    "#..................#############",
    "#......A................B.....X#",
    "#..............................#",
    "#................GG..~~~=......#",
    "#................GG............#",
    "#===================........#..#",
    "#....................====#~~#..#",
    "#=~~~~~..................#C.#..#",
    "#........................#~~#..#",
    "#..D.....=======.........#~~#..#",
    "#..................~~~~..#~~#..#",
    "#..>>>>..................#~~#..#",
    "#.............====.E.....#~~#..#",
    "#.WW....~~~~................GPP#",
    "#.WW........................GPP#",
    "#==============================#"
  ],
  "willy": {
    "standing_on": "floor"
  },
  "keys": {
    "key_C": {
      "what": "key",
      "side": "right",
      "horizontal_cells": 23,
      "horizontal_distance": "far",
      "height": "higher",
      "floor_rows_apart": 7,
      "rows_above_its_floor": 0,
      "floor_below_key": "crumbling floor",
      "between_walls": "yes",
      "one_way_trip": "yes: Willy falls through the crumbling floor and cannot go back up",
      "decisions_used_for_it": "none"
    },
    "key_E": {
      "what": "key",
      "side": "right",
      "horizontal_cells": 16,
      "horizontal_distance": "far",
      "height": "same level",
      "floor_rows_apart": 0,
      "rows_above_its_floor": 2,
      "floor_below_key": "floor",
      "decisions_used_for_it": "none"
    }
  }
}
```

On the map, each key has its own letter, and it keeps that letter for the
whole run. A conveyor is `<` or `>`: the direction in which it carries
Willy. The legend tells what each symbol means for Willy.

| Fact of a key | Meaning |
| --- | --- |
| `what` | key, or switch (with the fact that a switch changes the cavern) |
| `side`, `horizontal_cells`, `horizontal_distance` | where the key is, left or right of Willy |
| `height`, `floor_rows_apart` | the key's floor level, compared with Willy's floor. A key that hangs above Willy's floor is on the same level if a jump reaches it: at most 3 rows above Willy's head. A key that hangs higher is `higher`, even when `floor_rows_apart` is 0. |
| `rows_above_its_floor` | how high the key is above its floor |
| `floor_below_key` | floor, crumbling floor, or conveyor |
| `between_walls`, `one_way_trip` | the key is in a shaft above a crumbling floor. Willy falls through and cannot go back up. |
| `current_target` | the present target. Jev can keep it or change it. |
| `decisions_used_for_it`, `gave_up_on_it` | a short memory for each key. `gave_up_on_it` occurs only when the key decision has no map (`--facts-only-keys`). Then the text also explains it. |

The question is a Choice with one option for each key and switch. The text of
the default set `promptD` follows. (promptA has an older wording of the
sentence about crumbling floors.)

> Willy is a miner in a platform game. The map shows the cavern, and `map_legend` tells what each symbol means. `keys` gives facts about each key or switch relative to Willy. Willy must collect all keys and then go into the exit portal. Willy can climb only 2 rows with one jump. He can fall to a lower floor, but after a long fall he cannot climb back. A crumbling floor breaks when Willy uses it, so a way across a crumbling floor can be open only once. Select the key or switch that Willy gets next, in an order that lets him get all keys. `current_target` marks the key that Willy goes to now. Willy can keep it or change it. `decisions_used_for_it` tells how many decisions Willy used for this key before.

Jev's answer in the example is `key_D`, with a probability of 0.50 and a
confidence of 0.37. The other probabilities: `key_E` 0.32, `key_A` 0.11,
`key_C` 0.06, and `key_B` 0.01. This request used 1638 input tokens.

A test showed that the text must name the map. When the state has the map
and the text does not name it, jev selects the same key as with no map.

### Request 2: the move decision

The state of decision 6 of the same run, as the present code builds it:

```json
{
  "willy": {
    "facing": "right",
    "standing_on": "crumbling floor, partly gone"
  },
  "target": {
    "what": "selected key",
    "side": "left",
    "horizontal_cells": 15,
    "horizontal_distance": "far",
    "height": "lower",
    "floor_rows_apart": 1,
    "rows_above_its_floor": 1,
    "way_down": {
      "what": "edge of the floor",
      "side": "left",
      "horizontal_cells": 2,
      "warning": "a nasty or a guardian is below the place where Willy stands"
    }
  },
  "keys_left": 5,
  "to_the_left": {
    "first_thing": "edge of the floor, then a drop",
    "distance_cells": 1
  },
  "to_the_right": {
    "first_thing": "edge of the floor, then a drop",
    "distance_cells": 4
  },
  "guardians": [
    {
      "side": "left",
      "horizontal_cells": 16,
      "horizontal_distance": "far",
      "height": "higher",
      "direction": "toward Willy"
    },
    {
      "side": "left",
      "horizontal_cells": 5,
      "horizontal_distance": "medium",
      "height": "lower",
      "direction": "toward Willy"
    }
  ],
  "air": "plenty",
  "progress_measures": "distance to the way down",
  "moves": {
    "walk_left": {
      "movement": "Willy moves 1 cell to the left and 2 rows lower",
      "progress": "nearer",
      "place": "new place",
      "tried_from_here": "no"
    },
    "walk_right": {
      "movement": "Willy moves 1 cell to the right",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no",
      "ends_on": "crumbling floor, partly gone"
    },
    "jump_left": {
      "movement": "Willy moves 4 cells to the left and 1 row higher",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no"
    },
    "jump_up": {
      "movement": "Willy stays in the same place",
      "progress": "same",
      "place": "visited before",
      "tried_from_here": "no",
      "ends_on": "crumbling floor, partly gone"
    },
    "wait": {
      "movement": "Willy stays in the same place",
      "progress": "same",
      "place": "visited before",
      "tried_from_here": "no",
      "ends_on": "crumbling floor, almost gone"
    }
  },
  "moves_not_offered": {
    "jump_right": "kills Willy: fall or other cause"
  }
}
```

| Fact | Meaning |
| --- | --- |
| `willy` | the direction that Willy faces, and the tile below him |
| `target` | the target's position. A target on a higher floor has a `way_up`: the nearest place where a jump reaches a higher platform. A target on a lower floor has a `way_down`: the nearest safe edge or crumbling floor. If Willy stands on a crumbling floor, `way_down` is the safe place to fall on that floor that is nearest to the target. A `warning` tells when Willy must not wait at a place. |
| `to_the_left`, `to_the_right` | the first thing in Willy's path on his level (wall, nasty, edge, or nothing), with its distance in cells |
| `guardians` | the position of each horizontal guardian relative to Willy, and its `direction` (toward Willy or away from him). For a guardian on Willy's level: whether Willy is in its patrol area, and where that area ends. The code can also describe vertical guardians, but that is off, because it made the results worse. |
| `air` | plenty, low, or critical |
| `progress_measures` | the place that `progress` measures the distance to: the target (same level), the way up (higher floor), or the way down (lower floor) |
| `moves` | the true result of each valid move, from the look-ahead |
| `moves.*.movement` | where Willy is after the move |
| `moves.*.progress` | nearer, farther, or same |
| `moves.*.place` | new place, visited before, or visited many times (memory) |
| `moves.*.tried_from_here` | whether Willy made this move from this place before (memory) |
| `moves.*.ends_on`, `collects_key`, `completes_cavern`, `warning` | present only when they apply. `ends_on` and `willy.standing_on` give the condition of a crumbling floor: new, partly gone, or almost gone. The code reads it from the tile's pixels. |
| `moves_not_offered` | each move that jev does not get, with the reason: it kills Willy (guardian, nasty, fall, or dead end), or it has no effect because another move gives the same game |

The request has one question, `move`. It is a Choice, and its options are
the valid moves. The text of the default set `promptD` follows. The example
run used `promptA`, which has one sentence instead of the four sentences
that start with "The code removed": "All moves in `moves` are safe and have
an effect."

> Willy is a miner in a platform game. The goal: Willy must collect all keys, then go into the exit portal, and he must stay alive. The target is the key that Willy goes to now, or the portal when no key is left. Select the move that is the best for Willy now. `moves` gives the true result of each possible move. The code removed each move that kills Willy. It also removed each move that gives the same game as another move. If no move is safe, a move after which Willy cannot stay alive stays in `moves` with a `warning`. If each move kills Willy, `moves` says this. `moves_not_offered` gives the moves that Willy cannot make now, with the cause. The meaning of the facts: `progress` tells if a move gets Willy nearer to the place that `progress_measures` names. `place` tells how frequently Willy was at the place where the move ends. `tried_from_here` tells if Willy made this move from this place before. `collects_key` tells that Willy gets a key with this move. `completes_cavern` tells that Willy goes into the portal with this move and the cavern is complete. `ends_on` tells that Willy stands on a crumbling floor after this move, and how much of that floor is left. `warning` tells that no move is safe after this move. Knowledge of the game: Willy can climb only 2 rows with one jump. If Willy comes back to the same places again and again, the direct way is closed, and he must go a different way, even if that way goes away from the target first. A crumbling floor breaks a little each time Willy stands on it. It can be the only way up, and it is also a way down. A nasty does not move: if it stops a jump, a jump from a different cell can go over it. A guardian moves along its patrol area: Willy can wait for it to go away, jump over it, or go out of its patrol area.

The options and their criteria:

- `jump_right`: Jump to the right. The result is in `moves.jump_right`.
- `jump_left`: Jump to the left. The result is in `moves.jump_left`.
- `walk_right`: Walk to the right. The result is in `moves.walk_right`.
- `walk_left`: Walk to the left. The result is in `moves.walk_left`.
- `jump_up`: Jump straight up. The result is in `moves.jump_up`.
- `wait`: Do not move. The result is in `moves.wait`.

Jev's answer in the example is `walk_left`, with a probability of 0.57 and a
confidence of 0.44. The other probabilities: `jump_left` 0.25, `walk_right`
0.15, and `wait` 0.03. This request used 1406 input tokens and took 233 ms.

### With the movement graph

With `--graph --half-steps --no-way-back`, the requests change in these ways:

- `progress_measures` is "the target, by the number of moves on the shortest
  way to it", and `progress` compares that number before and after the move.
- The target has no `way_up` and no `way_down`.
- `moves` can have `step_left` and `step_right`. Their `movement` is, for
  example, "Willy moves half a cell to the left". Their options have the
  criteria "Take a half step to the left. The result is in `moves.step_left`."
- `moves_not_offered` can give the cause "no way back: a key or the portal is
  out of reach after it".
- The key decision offers only the keys and switches that Willy can reach and
  that leave no key out of reach. `keys` describes only those. The map still
  shows each key.

The log file's decision records also have `moves_to_target`: the number of
moves from Willy's place to the target in the graph. Jev does not get it.

## Log files

A log file is in JSON Lines format. The first line is the header. Then there
is one line for each decision, including the decisions with no jev request:

- a `target` record for a key decision;
- a `decision` record for a move decision, with its state, its answer, and
  its result.

The last line is the end record, with the outcome. The header has the
version of the moves (`macros: 2` means with the conveyor hold). The viewer
does not show a log file of an earlier version (other moves, or settings
with earlier names).
