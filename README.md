# jev plays Manic Miner

This project uses [jev](https://docs.typesafe.ai/introduction) to play Manic
Miner. Jev is the System One model from TypeSafe. It does not write text. It
gets a state and typed questions, and it gives typed answers with
probabilities.

The game runs on a ZX Spectrum emulator. A web page shows the game, each
decision of jev, and all data that goes to jev.

The project is standalone. It contains the emulator sources and the game
snapshot.

## The rule of the project

**The decisions must come from jev.** The code gives facts and knowledge of
the game. The code does not tell jev what to select. But the code does not
offer a decision that we know is not valid.

This gives two modes:

- **Free mode** (the normal configuration). The instructions have three
  parts: the goal, the meaning of each fact, and knowledge of the game (for
  example "a crumbling floor breaks a little each time Willy stands on it").
  They do not say "select X when Y".
- **Rules mode** (for comparison only). The instructions are a numbered list
  of rules of the form "select X when Y", and the state marks the option with
  the smallest number of visits. Jev executes a procedure that we wrote. Most
  of the success of this mode comes from that procedure, not from jev.

## Result

Free mode with the present configuration. 10 live runs for each cavern. A run
is complete when Willy has all keys and goes into the portal.

| Cavern | Complete runs | Note |
| --- | --- | --- |
| 1 Central Cavern | 10 of 10 | 71 decisions |
| 3 The Menagerie | 10 of 10 | 66 decisions |
| 2 The Cold Room | 4 to 6 of 10 | the key order is the problem |
| 4 Abandoned Uranium Workings | 0 of 10 | 4.0 of 5 keys, then a trap in a corner |
| 16 The Sixteenth Cavern | 0 of 10 | 1.7 of 4 keys |

One complete run costs approximately $0.004. We measured only these caverns
with the present configuration. They have horizontal guardians only.

An older measurement of all 20 caverns (200 runs, before the corrections of
the prompt text) is a lower limit for the other caverns. Jev completed 6 of
the 20 caverns at least one time. Only cavern 9, which has 1 key, was
reliable.

<details><summary>The 200-run table</summary>

| Cavern | Complete runs | Mean keys |
| --- | --- | --- |
| 1 Central Cavern | 1 of 10 | 2.5 |
| 2 The Cold Room | 6 of 10 | 4.1 |
| 3 The Menagerie | 2 of 10 | 2.3 |
| 4 Abandoned Uranium Workings | 0 of 10 | 1.8 |
| 5 Eugene's Lair | 0 of 10 | 1.9 |
| 6 Processing Plant | 0 of 10 | 3.6 |
| 7 The Vat | 4 of 10 | 2.9 |
| 8 Miner Willy meets the Kong Beast | 0 of 10 | 1.8 |
| 9 Wacky Amoebatrons | 10 of 10 | 1 |
| 10 The Endorian Forest | 0 of 10 | 1.8 |
| 11 Attack of the Mutant Telephones | 0 of 10 | 2.3 |
| 12 Return of the Alien Kong Beast | 0 of 10 | 0.8 |
| 13 Ore Refinery | 0 of 10 | 1 |
| 14 Skylab Landing Bay | 0 of 10 | 0.9 |
| 15 The Bank | 0 of 10 | 2 |
| 16 The Sixteenth Cavern | 0 of 10 | 1.6 |
| 17 The Warehouse | 0 of 10 | 0 |
| 18 Amoebatrons' Revenge | 3 of 10 | 0.3 |
| 19 Solar Power Generator | 0 of 10 | 0.9 |
| 20 The Final Barrier | 0 of 10 | 2.5 |

</details>

### Rules mode compared with free mode

We wrote the rules of rules mode with caverns 1 and 2. Caverns 3, 4, and 16
are a fair test: they have horizontal guardians only, and we did not write a
rule with them. The two modes ran at the same time with the same code. 10
live runs for each cavern and each mode:

| Cavern | Free mode | Rules mode |
| --- | --- | --- |
| 1 Central Cavern (rules written with it) | 10 of 10 | 10 of 10 |
| 2 The Cold Room (rules written with it) | 6 of 10 | 9 of 10 |
| 3 The Menagerie (fair test) | 8 of 10, 4.7 keys | 1 of 10, 1.4 keys |
| 4 Abandoned Uranium Workings (fair test) | 0 of 10, 3.0 keys | 0 of 10, 1.3 keys |
| 16 The Sixteenth Cavern (fair test) | 0 of 10, 1.7 keys | 0 of 10, 1.0 keys |

The rules are better on the caverns that we wrote them with, and worse on the
other caverns. They fit caverns 1 and 2 too well. Free mode is thus the normal
configuration. Rules are a legitimate form of prompt optimisation, but each
rule must be general, and we must measure it on caverns that we did not use
to write it.

What the measurements show:

- **The safety part works.** A run ends because Willy makes no progress, or
  because the air ends. It does not end because of a move that the look-ahead
  said was safe.
- **Jev makes sensible single decisions, but it does not plan a route.** It
  selects a move that goes nearer to the target in 85 % of the decisions
  where such a move exists. It fails when the direct way is closed and Willy
  must go away from the target first, and it uses up crumbling floors that it
  needs later.
- **Jev does not always give the same answer for the same state.** When two
  options are near (0.47 and 0.44), two runs go different ways. Use 10 runs
  for each cavern to compare two designs. 3 runs show only large effects.

## Setup

You need `uv`, `clang++`, and `make`. You also need a TypeSafe API key.

```sh
uv sync
uv run make -C emulator                 # build the emulator module
echo "TYPESAFE_API_KEY=your-key" > .env
uv run pytest                           # tests, no jev calls
```

## How to run it

### The viewer

```sh
uv run python -m jevmanic.server
```

Open http://127.0.0.1:8000.

- **Replay** plays a recorded run. A replay makes no jev calls and costs
  nothing. The emulator is deterministic, thus a replay is always the same
  game. Select a group of recorded runs first:
  - **Saved example runs**: complete runs that are part of the project
    (folder `demo/`). Use them for a demonstration.
  - **Your live runs**: each run that you start is saved here (folder
    `runs/`).
  - **Measurement: name**: the runs of one measurement (folder
    `runs/name/`). A failed run shows where and why jev failed.

  The box **complete runs only** hides the runs in which Willy did not get
  to the portal. Each entry gives the cavern, the mode, the result, and the
  number of decisions.
- **Start live run** plays a new game with jev. Select the cavern and the
  state encoder first. Keep the **look-ahead** box set and use the `words`
  encoder. The **rules mode** box gives jev the procedure that we wrote. Use
  it for comparison only.
- **Pause**, **Step**, and **Speed** control the playback. One step is one
  decision. The game stops while jev makes a decision, thus real time is not
  necessary.
- Click a bar in the timeline to examine an earlier decision.

The page shows, for each decision:

- the key or switch that jev selected as the target, with a yellow box in
  the game
- the probability of each macro, the selected macro, and the confidence
- each macro that jev did not get, with the cause
- **the exact state JSON and the exact questions of the request**
- the time of the jev call, the input tokens, and the cost

### The terminal

```sh
uv run python -m jevmanic.cli words lookahead cavern=2
uv run python -m jevmanic.cli words lookahead cavern=2 until-complete
uv run python -m jevmanic.cli words lookahead cavern=2 rules     # comparison only
```

The cavern number starts at 1. With `until-complete`, the script plays again
until a run is complete (10 runs at most). Each live run writes a log file in
`runs/`. The viewer can replay it.

### Measurement

```sh
uv run python -m experiments.measure caverns=1,2 runs=10 label=my-test
uv run python -m experiments.measure caverns=1,2 runs=10 label=rules rules-move rules-target
uv run python -m experiments.diagnose runs/my-test/<file>.jsonl
```

`experiments/measure.py` plays many live games at the same time and prints a
table: complete runs, keys, decisions, tokens, and the rate of decisions with
a confidence below 0.5. The switches `no-extras`, `no-memory`, `depth=N`,
`rules-move`, and `rules-target` change one part of the design, to measure
what it gives. The log files go to `runs/<label>/`, and the viewer shows
them as the group "Measurement: label". The summaries of the measurements
in this document are in `experiments/results/`.
`experiments/diagnose.py` prints the map, the last positions, and the last
state of one run.

## How it works

Each decision has these steps:

1. The code reads the game data from the emulator memory: Willy, the
   guardians (horizontal and vertical), the keys, the switches, the portal,
   the tiles, and the air.
2. **Look-ahead.** The code tries each of the 6 macros in the emulator and
   then puts the game back. This gives the true result of each macro.
3. The code makes the state: a JSON object with words and small numbers.
4. Jev gets the state and the questions in one request. A Choice question
   selects the macro.
5. The emulator runs the macro. Then the next decision starts.

The 6 macros are `walk_left`, `walk_right` (1 cell), `jump_left`,
`jump_right`, `jump_up`, and `wait`. A macro ends when Willy is on the ground
and in line with the cell grid.

There is a second, less frequent request: jev selects the **target** (a key,
or a switch in the two caverns that have switches). The code sends it at the
start, after each collected key, and after 12 decisions with no new place
(that target is then left out).

### Valid moves

Jev gets only the moves that are valid. A move is not valid in three cases:

1. The move kills Willy.
2. The move is a dead end: Willy is alive after it, but then he cannot avoid
   a death. To find this, the code looks for one sequence of 12 macros that
   keeps Willy alive. If there is none, the move is a dead end. Example: a
   guardian follows Willy 1 cell behind him toward a wall. Each step is safe,
   but after 5 steps no move is safe. This check asks only "can Willy stay
   alive?". It does not look at keys or at the portal, and it does not select
   a move. It is the part of the design that is nearest to a search.
3. The move has no effect: Willy stays in the same place. `wait` is valid
   only when something can change (a guardian is near, or Willy is on a
   crumbling floor).

If no valid move is left, jev gets the best moves that remain, in this
sequence: moves with no effect, then dead end moves (with a warning), and
only then all moves. The first version of this filter had an error: it gave
jev all 6 moves too early. That version made the 200-run table.

### What the code does and what jev does

| The code | Jev |
| --- | --- |
| Reads positions and changes them into facts | Selects the target |
| Tries each macro and gives its true result | Selects each move |
| Does not offer a move that is not valid | |
| Remembers the places and the moves that Willy tried | |

## The data that we give to jev

Jev reads text only. It cannot read a screenshot. Jev is weak with
coordinates, with counts, and with large states. Thus the state gives
positions relative to Willy, in words and small numbers.

All examples below are from the recorded run
`demo/cavern-02-the-cold-room-free-mode.jsonl`. The exact text of all
questions is in `jevmanic/brain.py`. The state encoders are in
`jevmanic/describe.py`. The viewer shows the exact state and questions of
each request.

### Request 1: the target

Jev gets this request at the start, when Willy collects a key, when he lands
on a different floor level, and when he makes no progress for 12 decisions.
The state has one entry for each key that is left, and for each switch that
is not flipped. This example shows 2 of the keys:

```json
{
  "willy": {
    "standing_on": "crumbling floor"
  },
  "keys": {
    "key_2": {
      "what": "key",
      "side": "right",
      "horizontal_cells": 16,
      "horizontal_distance": "far",
      "height": "higher",
      "floor_rows_apart": 10,
      "rows_above_its_floor": 1,
      "floor_below_key": "floor",
      "current_target": "yes",
      "decisions_used_for_it": "a few"
    },
    "key_3": {
      "what": "key",
      "side": "right",
      "horizontal_cells": 18,
      "horizontal_distance": "far",
      "height": "higher",
      "floor_rows_apart": 5,
      "rows_above_its_floor": 0,
      "floor_below_key": "crumbling floor",
      "between_walls": "yes",
      "one_way_trip": "yes: Willy falls through the crumbling floor and cannot go back up",
      "decisions_used_for_it": "none"
    }
  }
}
```

| Field | Meaning |
| --- | --- |
| `what` | key, or switch (with the fact that a switch changes the cavern) |
| `side`, `horizontal_cells`, `horizontal_distance` | where it is, left or right of Willy |
| `height`, `floor_rows_apart` | its floor level, compared with the floor of Willy. A key that hangs above the floor of Willy is on the same level. |
| `rows_above_its_floor` | how high it is above its floor |
| `floor_below_key` | floor, crumbling floor, or conveyor |
| `current_target` | the key that Willy goes to now. Jev can keep it or change it. |
| `decisions_used_for_it`, `gave_up_on_it` | a short memory for each key |
| `between_walls`, `one_way_trip` | the key is in a shaft above a crumbling floor. Willy falls through and cannot go back up. |

The question is a Choice with one option for each entry. The instructions:

> Willy is a miner in a platform game. He must collect all keys. Willy can climb only 2 rows with one jump. `keys` gives facts about each key or switch relative to Willy. Select the key or switch that is the best for Willy to get next. `current_target` marks the key that Willy goes to now. Willy can keep it or change it. `decisions_used_for_it` tells how many decisions Willy used for this key before. `gave_up_on_it` tells how many times Willy made no progress toward this key.

The answer in the example: `key_4`, confidence
0.43. This request used 944 input
tokens.

### Request 2: the move

The state of decision 5 of the same run:

```json
{
  "willy": {
    "facing": "right",
    "standing_on": "floor"
  },
  "target": {
    "what": "selected key",
    "side": "right",
    "horizontal_cells": 5,
    "horizontal_distance": "medium",
    "height": "same level",
    "floor_rows_apart": 0,
    "rows_above_its_floor": 2
  },
  "keys_left": 5,
  "to_the_left": {
    "first_thing": "nothing, the floor is clear",
    "distance_cells": 6
  },
  "to_the_right": {
    "first_thing": "nothing, the floor is clear",
    "distance_cells": 6
  },
  "guardians": [
    {
      "side": "left",
      "horizontal_cells": 7,
      "horizontal_distance": "medium",
      "height": "higher",
      "moves": "away from Willy"
    },
    {
      "side": "right",
      "horizontal_cells": 2,
      "horizontal_distance": "near",
      "height": "same level",
      "moves": "toward Willy",
      "willy_is_in_its_patrol_area": "yes",
      "patrol_area_ends": {
        "cells_to_the_left": 3,
        "cells_to_the_right": 18
      }
    }
  ],
  "air": "plenty",
  "progress_measures": "distance to the target",
  "moves": {
    "walk_left": {
      "movement": "Willy moves 1 cells to the left",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no"
    },
    "walk_right": {
      "movement": "Willy moves 1 cells to the right",
      "progress": "nearer",
      "place": "new place",
      "tried_from_here": "no"
    },
    "jump_left": {
      "movement": "Willy moves 3 cells to the left and 2 rows higher",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no",
      "ends_on": "crumbling floor"
    },
    "wait": {
      "movement": "Willy stays in the same place",
      "progress": "same",
      "place": "visited before",
      "tried_from_here": "no"
    }
  },
  "moves_not_offered": {
    "jump_right": "kills Willy: guardian",
    "jump_up": "no effect: Willy stays in the same place"
  }
}
```

| Field | Meaning |
| --- | --- |
| `willy` | the direction that Willy looks in, and the tile below him |
| `target` | the key or switch that jev selected, or the portal. When the target is on a higher floor, it has a `way_up`: the nearest place where a jump gets to a higher platform. When the target is on a lower floor, it has a `way_down`: the nearest safe edge or crumbling floor. |
| `to_the_left`, `to_the_right` | the first thing in the path of Willy on his level: wall, nasty, edge, or nothing, with the distance in cells |
| `guardians` | the position of each guardian relative to Willy, and its direction. For a horizontal guardian on the level of Willy: is Willy in its patrol area, and where the patrol area ends. For a vertical guardian: does its column cross the level of Willy, and is it above, below, or on that level now. |
| `air` | plenty, low, or critical |
| `progress_measures` | the place that `progress` measures the distance to: the target (same level), the way up (higher floor), or the way down (lower floor) |
| `moves` | the true result of each valid macro, from the look-ahead |
| `moves.*.movement` | where Willy is after the macro |
| `moves.*.progress` | nearer, farther, or same |
| `moves.*.place` | new place, visited before, or visited many times (memory) |
| `moves.*.tried_from_here` | did Willy select this macro at this place before (memory) |
| `moves.*.ends_on`, `collects_key`, `completes_cavern`, `warning` | only when they apply |
| `moves_not_offered` | each macro that jev does not get, with the cause: it kills Willy (guardian, nasty, fall, or dead end), or it has no effect |

The request has 4 questions. Only the first one controls Willy.

**`move` (Choice).** The options are the valid macros. The instructions:

> Willy is a miner in a platform game. The goal: Willy must collect all keys, then go into the exit portal, and he must stay alive. The target is the key that Willy goes to now, or the portal when no key is left. Select the move that is the best for Willy now. `moves` gives the true result of each possible move. All moves in `moves` are safe and have an effect. `moves_not_offered` gives the moves that Willy cannot make now, with the cause. The meaning of the facts: `progress` tells if a move gets Willy nearer to the place that `progress_measures` names. `place` tells how frequently Willy was at the place where the move ends. `tried_from_here` tells if Willy made this move from this place before. `collects_key` tells that Willy gets a key with this move. `completes_cavern` tells that Willy goes into the portal with this move and the cavern is complete. `ends_on` tells that Willy stands on a crumbling floor after this move. `warning` tells that no move is safe after this move. Knowledge of the game: Willy can climb only 2 rows with one jump. If Willy comes back to the same places again and again, the direct way is closed, and he must go a different way, also if that way goes away from the target first. A crumbling floor breaks a little each time Willy stands on it. It can be the only way up, and it is also a way down. A nasty does not move: if it stops a jump, a jump from a different cell can go over it. A guardian moves along its patrol area: Willy can wait for it to go away, jump over it, or go out of its patrol area.

The criteria of the options:

- `jump_right`: Jump to the right. The result is in `moves.jump_right`.
- `jump_left`: Jump to the left. The result is in `moves.jump_left`.
- `walk_right`: Walk 1 cell to the right. The result is in `moves.walk_right`.
- `walk_left`: Walk 1 cell to the left. The result is in `moves.walk_left`.
- `jump_up`: Jump straight up. The result is in `moves.jump_up`.
- `wait`: Do not move. The result is in `moves.wait`.

**The other questions.** They go in the same request, thus they add almost no
time. The viewer shows their answers.

- `danger_right` (Noul): If Willy walks 2 cells to the right now, does he touch a nasty or a guardian, or fall from an edge?
- `danger_left` (Noul): If Willy walks 2 cells to the left now, does he touch a nasty or a guardian, or fall from an edge?
- `threat` (Score): How large is the threat to Willy at this moment?

The answer in the example: `walk_right`, confidence
0.64. The probabilities: `walk_right` 0.74, `walk_left` 0.11, `jump_left` 0.08, `wait` 0.07. This request used
1524 input tokens and took 288 ms.

The code makes no jev call when only one macro is valid, and when all valid
macros have the same result (Willy is in the air).

### Other state encoders

The viewer has 4 encoders. `words` is the one above.

| Encoder | Content |
| --- | --- |
| `words` | the facts in words, as above |
| `ascii_local` | a small ASCII map around Willy + the direction of the target |
| `ascii_full` | the full ASCII map of the cavern + the direction of the target |
| `hybrid` | `words` + `ascii_local` |

You can also run with no look-ahead. Then the criteria of the `move` question
give exact rules about the state, and the code does not check a macro before
it runs. Willy dies quickly. It is there for comparison.

## What we learned about jev

- **Give jev the goal and the meaning of each fact.** In Central Cavern, the
  state said that `jump_left` had `collects_key: true`, and jev selected
  `walk_left` (0.51 against 0.44). The instructions did not say that Willy
  must collect keys, and did not say what `collects_key` means. With the goal
  and the meaning in the text, and with no rule about what to select, the
  cavern went from 3 of 10 to 10 of 10 complete runs. The decisions per run
  (74) are near the result of our procedure in rules mode (70).
- **The dead end check gives much help.** Complete runs of 10, with the
  present configuration:

  | Depth of the check | Central Cavern | The Cold Room | The Menagerie |
  | --- | --- | --- | --- |
  | 0 (off) | 6 | 0 | 0 |
  | 2 | 10 | 4 | 1 |
  | 12 (the present value) | 10 | 4 | 10 |

  In The Menagerie at depth 2, all 9 deaths are at the same place, after 4 to
  6 decisions with no real choice: one trap that is 6 moves deep. The deep
  check removes the first step into it. A large part of "stay alive" thus
  comes from the code, not from jev.
- **A shorter prompt was worse.** We wrote the move text again with the same
  content in short sentences and a "field: meaning" form (190 words, not
  293). Central Cavern needed 89 decisions, not 71. The Menagerie went from
  10 of 10 to 4 of 10. Jev reads full sentences better than a terse list.
  The switch `brief-text` of the measurement tool turns it on.
- **A code guess can be better than two honest facts.** In cavern 4, the
  code selects a single tile in a corner as "the way up", `progress` points
  to it, and Willy goes into that trap in each run. We gave jev the way up on
  the left and on the right as facts, and measured `progress` to the target.
  Cavern 4 got its first complete run, but Central Cavern went from 10 of 10
  to 5 of 10, and The Menagerie from 10 of 10 to 1 of 10. The one reference
  that the code selects does important work. The switch `two-ways-up` of the
  measurement tool turns the two facts on.
- **A less rigid target helped.** Jev now gets the target question again when
  Willy collects a key, lands on a different floor level, or makes no
  progress. It can keep or change the target, and each key has a short memory
  (`decisions_used_for_it`, `gave_up_on_it`). The Menagerie went from 9 of 10
  to 10 of 10, and cavern 4 from 3.5 to 4.0 keys. Jev kept the target in 363
  of 421 requests.
- **More memory made the results worse.** We gave jev the last 4 moves with
  their results (`recent_moves`, `came_from`). The movement from left to
  right and back did not change (32 % of the decisions with it and without
  it). But jev selected a move that collects a key in 67 % of the cases, and
  in 89 % without the memory. The Menagerie went from 9 of 10 to 5 of 10.
  More text in the state takes weight away from the important facts. The
  switch `recent-moves` of the measurement tool turns it on.
- **The memory facts are not decisive.** Central Cavern is 9 of 10 with no
  memory facts, and 10 of 10 with them.
- **Jev cannot count the cells on an ASCII map.** `experiments/probe_gap.py`
  shows a map row with Willy, N empty cells, and a nasty. It asks "are there
  exactly 2 empty cells?". From the map, jev says yes with 0.61, 0.75, and
  0.60 for N = 1, 2, and 3. From a number, jev says yes with 0.03, 0.91, and
  0.03. A jump over a nasty is safe only at exactly 2 cells. Thus the code
  must give distances as numbers.
- **Field names are important.** Jev read `"rows_higher": 0` as "same level"
  when the thing was lower. One clear field is better than two fields.
- **Two facts must not disagree.** When "nearer to the portal" said right and
  "way down" said left, Willy went left and right with no end.
- **A true fact can mislead.** We gave the fact "after this move, these moves
  are safe". It made a loop: `jump_left` made `jump_right` safe, and
  `jump_right` took Willy back to the same place. We removed it.
- **Give the cause, not only the result.** "This move kills Willy" made jev
  wait at a nasty for 30 decisions. The cause (guardian or nasty) lets jev
  know if a wait can help.
- One move request uses approximately 1400 input tokens and takes
  approximately 300 ms from our computer.

Designs that we measured and removed, because they were not better than free
mode on caverns 1 to 4: one Noul question for each move (1 of 12 complete),
and a question in which jev selects the next platform from the map (1 of 18).
We also removed a "route mode": the code searched sequences of up to 32
macros to find the platforms that Willy can get to, jev selected one, and the
code walked the path. It completed caverns 2 and 3 in 9 and 10 of 10 runs,
but the code walked 3459 macros and jev selected 175 single moves. That
result came from the search, not from jev.

`experiments/probe_encodings.py` measures how well jev reads each encoder.
`experiments/probe_target.py` compares target rules with a free choice.

## Open work

- **The map of the cavern gives jev a better key decision.** A test that
  plays no game (`experiments/probe_key_order.py`) asks "which key next?" in
  13 situations of caverns 1 to 4. The reference is the key order of the
  complete recorded runs. Correct next key: facts only 5 of 13, map only 8,
  map and facts 12. In Central Cavern, jev selects key E first with the map.
  That is the known good order (E, A, C, D, B). With the facts only, it
  selects D first and gets E last.

  In play (switch `target-map`), Willy has all 5 keys of Central Cavern at
  decision 35 to 39. With the facts only, he has them at decision 62 to 66.
  But the complete runs went from 10 of 10 to 7 of 10. The better key order
  is not the cause. A test in which the code sets the key order (switch
  `key-order=EACDB`, no key request, the movement not changed) gives 10 of
  10 with the order E A C D B, and 9 of 10 with the old order A C D B E.
  We then changed one thing each time, in Central Cavern, 10 runs each:

  | Configuration | Complete | Decisions |
  | --- | --- | --- |
  | The code sets the order E A C D B (the known good order) | 10 | 80 |
  | The code sets the order A C D B E (the order of the facts-only runs) | 9 | 74 |
  | Test A: jev selects the key with the map, at the start and at each collected key, with the normal text | 7 | 94 |
  | The code sets the targets that jev selected in test A: E, then D, then B | 8 | 109 |

  The movement does the good order with no problem. The text of the key
  request is not the cause. The cause is the second key decision. With the
  map, jev selects E first, which is correct. After E, it selects D with a
  confidence of 0.86: D is only 5 cells away, and A is 20 cells away. But
  Willy can get to the top floor only at its left end, thus A is the correct
  next key. To see that, jev must follow the route on the map across four
  floors. That is a task of more than one step, and the jev documentation
  says that jev is weak at such tasks. With D as the target, the route along
  the top floor is different, and 2 or 3 of 10 runs then fail after the keys.

  The map has a letter for each key, `<` or `>` for a conveyor, and a legend
  that says what each symbol means for Willy.
- **A separate key decision with the map (hybrid) gave no gain in play.**
  Switch `hybrid-keys`: jev gets the key decision, with the map, at the start
  and when Willy collects a key, and the run is then in movement mode.
  `key-every=25` repeats the key decision after 25 decisions. Caverns 1 to 4,
  complete runs of 10: 7, 0, 7, 0 with no repeat, and 9, 2, 6, 0 with the
  repeat (the normal configuration: 10, 4 to 6, 10, 0). The key decisions
  are good, but the runs fail in movement mode, where the better key order
  shows weak move facts.
- **One correction for one place harmed a different cavern.** After the last
  key of Central Cavern, Willy stands on the crumbling floor that is his way
  down, and `progress` says that a walk toward the portal is nearer. Jev
  walks away and the run fails. We changed the measure for this case ("to
  stay is nearer"). The Menagerie, which has many crumbling floors, went from
  10 of 10 to 1 of 10. We removed the change. The error in Central Cavern is
  still there.
- **The target order is the open problem.** In The Cold Room, the full
  difference between rules mode (9 of 10) and free mode (4 to 6 of 10) is
  the order of the keys. We measured two prompt changes for it, 10 runs each:

  | Change to the target text | Cavern 1 | Cavern 2 | Cavern 3 | Cavern 4 | Cavern 16 |
  | --- | --- | --- | --- | --- | --- |
  | None (the normal text) | 10 | 4 to 6 | 10 | 0, 4.0 keys | 0, 1.7 keys |
  | + the meaning of `one_way_trip` | 8 | 0 | 10 | - | - |
  | The three target rules of rules mode | 7 | 8 | 9 | 0, 0 keys | 0, 2.0 keys |

  The sentence about `one_way_trip` did its task (jev did not select the
  shaft key too early), but then a different order problem ended the runs:
  Willy used the one crumbling way up two times. The target rules correct
  that order in cavern 2, and they make caverns 1 and 4 worse. A good key
  order needs a plan of the route. Jev gets facts relative to Willy, and a
  rule about those facts fits one cavern and not the next one.
- **The depth of the dead end check.** See the table above. Options: keep 12,
  use a smaller depth, or replace the search with experience (a memory of
  the places where Willy died in earlier runs).
- **Cavern 4.** Each run ends in a trap in the top left corner, because the
  code selects a single tile as "the way up".
- **Rules mode is not a strict prompt yet.** The state still has the mark
  `least_visited_option`, which the code selects.

## Limits

- The code now reads vertical guardians, Eugene, and the switches, and the
  state gives facts about them. We did not measure the effect of these facts
  yet. The 200-run table was made before them. The column and the rows of
  Eugene are an assumption.
- The Kong Beast, the Skylabs, and the light beam of cavern 19 have no facts
  in the state. The look-ahead still removes a move that they make deadly,
  because it runs the real game.
- The cause of a death (guardian or nasty) is an estimate from the positions
  at the death.
- The success rates come from 10 runs for each cavern. They are not exact.

## Files

| Path | Content |
| --- | --- |
| `emulator/` | ZX Spectrum emulator (C++) and the pybind11 binding `env.cpp` |
| `roms/ManicMiner.z80` | game snapshot |
| `jevmanic/game.py` | start of a cavern, memory reads, macros, look-ahead, dead end check |
| `jevmanic/describe.py` | state encoders |
| `jevmanic/brain.py` | questions and the jev calls |
| `jevmanic/runner.py` | live run, log file, replay |
| `jevmanic/server.py`, `jevmanic/web/` | viewer |
| `jevmanic/cli.py` | live run in the terminal |
| `experiments/` | measurement, diagnosis, and tests of how well jev reads a state |
| `experiments/results/` | the summaries of the measurements in this document |
| `demo/` | recorded complete runs, in git |
| `runs/` | log files of your runs (JSON Lines), not in git |

A log file has one header line, then one line for each jev request (a
"target" record or a "decision" record with its state and answers), then one
end line.

The emulator core comes from the esp32-zxspectrum project, which took it from
[OpenVegaPlus](https://github.com/alvaroalea/OpenVegaPlus).
