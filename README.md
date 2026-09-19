# jev plays Manic Miner

This project uses [jev](https://docs.typesafe.ai/introduction) to play Manic
Miner. Jev is the System One model from TypeSafe. It does not write text. It
gets a state and typed questions, and it gives typed answers with
probabilities.

The game runs on a ZX Spectrum emulator. A web page shows the game, each
decision of jev, and all data that goes to jev.

The project is standalone. It contains the emulator sources and the game
snapshot.

## Result

Jev completes the first three caverns with one set of rules. One complete run
costs approximately $0.005.

| Cavern | Complete runs | Decisions in the best run |
| --- | --- | --- |
| 1 Central Cavern | 3 of 3 | 70 |
| 2 The Cold Room | 2 of 2 | 65 |
| 3 The Menagerie | 1 of 2 | 74 |

The number of runs is small, thus the rates are not exact. We wrote the rules
with cavern 1 and cavern 2. Cavern 3 is a test: we did not look at it before
the runs.

Jev does not always give the same answer for the same state. When two options
are near (for example 0.47 and 0.44), two runs can go different ways. Thus
some live runs fail and some succeed.

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
  game. The first runs in the list are complete runs from the `demo/` folder,
  one for each of the three caverns.
- **Start live run** plays a new game with jev. Select the cavern and the
  state encoder first. Keep the **look-ahead** box set and use the `words`
  encoder: this is the configuration that completes the caverns.
- **Pause**, **Step**, and **Speed** control the playback. One step is one
  decision. The game stops while jev makes a decision, thus real time is not
  necessary.
- Click a bar in the timeline to examine an earlier decision.

The page shows, for each decision:

- the key that jev selected as the target, with a yellow box in the game
- the probability of each macro, the selected macro, and the confidence
- each macro that jev did not get, with the cause
- **the exact state JSON and the exact questions of the request**
- the time of the jev call, the input tokens, and the cost

### The terminal

```sh
uv run python -m jevmanic.cli words lookahead cavern=2
uv run python -m jevmanic.cli words lookahead cavern=2 until-complete
```

The cavern number starts at 1. With `until-complete`, the script plays again
until a run is complete (10 runs at most). Each live run writes a log file in
`runs/`. The viewer can replay it.

## How it works

Each decision has these steps:

1. The code reads the game data from the emulator memory: Willy, the
   guardians, the keys, the portal, the tiles, and the air.
2. **Look-ahead.** The code tries each of the 6 macros in the emulator and
   then puts the game back. This gives the true result of each macro.
3. The code makes the state: a JSON object with words and small numbers.
4. Jev gets the state and the questions in one request. A Choice question
   selects the macro.
5. The emulator runs the macro. Then the next decision starts.

The 6 macros are `walk_left`, `walk_right` (1 cell), `jump_left`,
`jump_right`, `jump_up`, and `wait`. A macro ends when Willy is on the ground
and in line with the cell grid.

There is a second, less frequent request: jev selects the **target key**. The
code sends it at the start, after each collected key, and after 12 decisions
with no new place (that key is then left out).

### What the code does and what jev does

The code does the geometry and the safety. Jev makes the decisions.

| The code | Jev |
| --- | --- |
| Reads positions and changes them into facts | Selects the target key |
| Tries each macro and gives its result | Selects each move |
| Removes a macro that kills Willy | |
| Remembers the places and the moves that Willy tried | |

The code removes a macro in two cases. The macro kills Willy directly. Or the
macro is a dead end: Willy is alive after it, but no sequence of 12 macros
keeps him alive. This check asks only "can Willy stay alive?". It does not
look for the target, thus it is not a search for a route. It is the part of
the design that is nearest to a search.

## The data that we give to jev

Jev reads text only. It cannot read a screenshot. Jev is weak with
coordinates, with counts, and with large states. Thus the state gives
positions relative to Willy, in words and small numbers, and it contains only
the facts that the questions need.

All examples below are from the recorded run `demo/cavern-02-the-cold-room.jsonl`.
The exact text of all questions is in `jevmanic/brain.py`. The state encoders
are in `jevmanic/describe.py`.

### Request 1: the target key

The state has one entry for each key that is left. This example shows 2 of
the 5 keys:

```json
{
  "willy": {
    "standing_on": "floor"
  },
  "keys": {
    "key_3": {
      "side": "right",
      "horizontal_cells": 23,
      "horizontal_distance": "far",
      "height": "higher",
      "floor_rows_apart": 7,
      "rows_above_its_floor": 0,
      "floor_below_key": "crumbling floor",
      "between_walls": "yes",
      "one_way_trip": "yes: Willy falls through the crumbling floor and cannot go back up"
    },
    "key_5": {
      "side": "right",
      "horizontal_cells": 16,
      "horizontal_distance": "far",
      "height": "same level",
      "floor_rows_apart": 0,
      "rows_above_its_floor": 2,
      "floor_below_key": "floor"
    }
  }
}
```

| Field | Meaning |
| --- | --- |
| `side`, `horizontal_cells`, `horizontal_distance` | where the key is, left or right of Willy |
| `height`, `floor_rows_apart` | the floor level of the key, compared with the floor of Willy. A key that hangs above the floor of Willy is on the same level. |
| `rows_above_its_floor` | how high the key is above its floor |
| `floor_below_key` | floor, crumbling floor, or conveyor |
| `between_walls`, `one_way_trip` | the key is in a shaft above a crumbling floor. Willy falls through and cannot go back up. |

The question is a Choice with one option for each key. The instructions:

> Willy is a miner in a platform game. He must collect all keys. Select the key that Willy goes to next. `keys` gives facts about each key relative to Willy. Willy can climb only 2 rows with one jump, thus a key on a much higher floor needs a long route. Apply these rules in order. Rule 1: do not select a key that has `one_way_trip`, if a different key is left. Willy cannot come back from it, thus it must be the last key. Rule 2: prefer the key with the smallest `floor_rows_apart`. Rule 3: if two keys are equal, prefer the key with the smallest `horizontal_cells`.

The answer in the example: `key_5`, probability 1.00. This request used
962 input tokens.

### Request 2: the move

The state of decision 7 of the same run:

```json
{
  "willy": {
    "facing": "right",
    "standing_on": "floor"
  },
  "target": {
    "what": "selected key",
    "side": "right",
    "horizontal_cells": 9,
    "horizontal_distance": "far",
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
      "horizontal_cells": 5,
      "horizontal_distance": "medium",
      "height": "higher",
      "moves": "away from Willy"
    },
    {
      "side": "right",
      "horizontal_cells": 4,
      "horizontal_distance": "medium",
      "height": "same level",
      "moves": "toward Willy",
      "willy_is_in_its_patrol_area": "no"
    }
  ],
  "air": "plenty",
  "progress_measures": "distance to the target",
  "moves": {
    "walk_left": {
      "movement": "Willy moves 1 cells to the left",
      "progress": "farther",
      "place": "visited before",
      "tried_from_here": "no"
    },
    "walk_right": {
      "movement": "Willy moves 1 cells to the right",
      "progress": "nearer",
      "place": "new place",
      "tried_from_here": "no"
    },
    "jump_left": {
      "movement": "Willy moves 5 cells to the left",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no"
    },
    "jump_up": {
      "movement": "Willy stays in the same place",
      "progress": "same",
      "place": "visited before",
      "tried_from_here": "yes"
    },
    "wait": {
      "movement": "Willy stays in the same place",
      "progress": "same",
      "place": "visited before",
      "tried_from_here": "no"
    }
  },
  "moves_that_kill_willy": {
    "jump_right": "kills Willy: guardian"
  }
}
```

| Field | Meaning |
| --- | --- |
| `willy` | the direction that Willy looks in, and the tile below him |
| `target` | the key that jev selected, or the portal. When the target is on a higher floor, it has a `way_up`: the nearest place where a jump gets to a higher platform. When the target is on a lower floor, it has a `way_down`: the nearest safe edge or crumbling floor. |
| `to_the_left`, `to_the_right` | the first thing in the path of Willy on his level: wall, nasty, edge, or nothing, with the distance in cells |
| `guardians` | the position of each guardian relative to Willy, and its direction. For a guardian on the level of Willy: is Willy in its patrol area, and where the patrol area ends. |
| `air` | plenty, low, or critical |
| `progress_measures` | the place that `progress` measures the distance to: the target (same level), the way up (higher floor), or the way down (lower floor) |
| `moves` | the true result of each safe macro, from the look-ahead |
| `moves.*.movement` | where Willy is after the macro |
| `moves.*.progress` | nearer, farther, or same |
| `moves.*.place` | new place or visited before (memory) |
| `moves.*.tried_from_here` | did Willy select this macro at this place before (memory) |
| `moves.*.ends_on`, `collects_key`, `completes_cavern` | only when they apply |
| `moves_that_kill_willy` | each macro that jev does not get, with the cause: guardian, nasty, fall, or dead end |

The request has 4 questions. Only the first one controls Willy.

**`move` (Choice).** The options are the safe macros. The instructions:

> Willy is a miner in a platform game. Select the best next move for Willy. Willy must go to the target. `moves` gives the true result of each move. All moves in `moves` are safe. `progress` tells if a move gets Willy nearer to the place that `progress_measures` names. Apply the first rule that matches. When two moves match the same rule, select the move whose `tried_from_here` is no, because a move that Willy tried here before did not help. A crumbling floor breaks a little each time Willy stands on it, and it can be the only way up. Thus when `target.height` is not lower, do not select wait on a crumbling floor, and prefer a jump to a walk when the move has `ends_on` crumbling floor. Rule 1: select a move that has `completes_cavern` or `collects_key`. Rule 2: when a guardian in `guardians` has `height` same level, moves toward Willy, and its `horizontal_cells` is 4 or less, select the jump toward that guardian if that jump is in `moves`, because the jump goes over the guardian. Do not walk away from it toward a wall. Rule 3: when `target.way_down.side` is Willy stands on it, select wait, because the crumbling floor breaks and Willy falls. Rule 4: select a move whose `progress` is nearer and whose `place` is new place. When `target.height` is higher, prefer a move that goes higher. When `target.height` is lower, prefer a move that goes lower. Rule 5: select a move whose `progress` is nearer. Rule 6: when a move toward the target is in `moves_that_kill_willy` with the cause guardian, select wait, because a guardian moves away. Rule 7: when a jump toward the target is in `moves_that_kill_willy` with the cause nasty, select the walk move that goes away from the target, because a nasty does not move and a jump from 1 cell farther back can go over it. Rule 8: select a move whose `place` is new place.

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
  The levels of `threat`:
  1. No nasty and no guardian is near Willy.
  2. A nasty or a guardian is near, but it is not in the path of Willy.
  3. A nasty or a guardian is in the path of Willy and 3 or more cells away.
  4. A nasty or a guardian is 1 or 2 cells from Willy on his level.

The answer in the example: `walk_right`, probability 0.91, confidence 0.88.
The look-ahead removed `jump_right`, because the guardian kills Willy in that
jump. This request used 1630 input tokens and took
344 ms.

If only one macro is safe, the code runs it and makes no jev call.

### Other state encoders

The viewer has 4 encoders. `words` is the one above.

| Encoder | Content |
| --- | --- |
| `words` | the facts in words, as above |
| `ascii_local` | a small ASCII map around Willy + the direction of the target |
| `ascii_full` | the full ASCII map of the cavern + the direction of the target |
| `hybrid` | `words` + `ascii_local` |

You can also run with no look-ahead ("rules" mode). Then the criteria of the
`move` question give exact rules about the state, and the code does not check
a macro before it runs. Willy dies quickly in this mode. It is there for
comparison.

## What we learned about the data for jev

- **Jev cannot count the cells on an ASCII map.** `experiments/probe_gap.py`
  shows a map row with Willy, N empty cells, and a nasty. It asks "are there
  exactly 2 empty cells?". From the map, jev says yes with 0.61, 0.75, and
  0.60 for N = 1, 2, and 3. From a number, jev says yes with 0.03, 0.91, and
  0.03. A jump over a nasty is safe only at exactly 2 cells. Thus the code
  must give distances as numbers.
- **Give exact rules in the criteria.** A criterion that gives only the
  purpose of an option does not work well. The public Doom projects for jev
  found the same.
- **Field names are important.** Jev read `"rows_higher": 0` as "same level"
  when the thing was lower. One clear field is better than two fields.
- **Two facts must not disagree.** When "nearer to the portal" said right and
  "way down" said left, Willy went left and right with no end. One `progress`
  measure for one purpose stopped that.
- **Give the cause, not only the result.** "This move kills Willy" made jev
  wait at a nasty for 30 decisions. With the cause, the rules can tell jev to
  wait for a guardian, or to go back 1 cell and jump over a nasty.
- **Memory helps.** One step of look-ahead cannot see a loop. The facts
  `place` and `tried_from_here` were sufficient for jev to get out of one.
- **Low confidence comes before a failure.** When no rule matches the state,
  the confidence goes below 0.5 and jev almost guesses.
- One move request uses approximately 1700 input tokens and takes
  approximately 300 ms from our computer.

`experiments/probe_encodings.py` measures how well jev reads each encoder.
`experiments/probe_target.py` compares the target rules with a free choice.

## Limits

- The code reads horizontal guardians only. Cavern 5 (Eugene's Lair) has a
  vertical guardian. The look-ahead still finds each death, because it runs
  the real game, but the state does not describe that guardian.
- The rules contain general knowledge of the game (jump over a guardian, keep
  a crumbling floor, a one-way key is the last key). We tested them in three
  caverns only.
- The success rates come from a small number of runs.

## Files

| Path | Content |
| --- | --- |
| `emulator/` | ZX Spectrum emulator (C++) and the pybind11 binding `env.cpp` |
| `roms/ManicMiner.z80` | game snapshot |
| `jevmanic/game.py` | start of a cavern, memory reads, macros, look-ahead |
| `jevmanic/describe.py` | state encoders |
| `jevmanic/brain.py` | questions and the jev calls |
| `jevmanic/runner.py` | live run, log file, replay |
| `jevmanic/server.py`, `jevmanic/web/` | viewer |
| `jevmanic/cli.py` | live run in the terminal |
| `experiments/` | tests of how well jev reads a state |
| `demo/` | recorded complete runs, in git |
| `runs/` | log files of your runs (JSON Lines), not in git |

A log file has one header line, then one line for each jev request (a
"target" record or a "decision" record with its state and answers), then one
end line.

The emulator core comes from the esp32-zxspectrum project, which took it from
[OpenVegaPlus](https://github.com/alvaroalea/OpenVegaPlus).
