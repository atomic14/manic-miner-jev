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

This gives two sets of instructions, **promptA** and **promptB**. **The
instructions are the only difference**: jev gets the same state, the same
options, and the same schedule of requests with the two sets. (The earlier
names were "free mode" for promptA and "rules mode" for promptB. Older log
files and measurement labels use those names.) For a person who
knows LLMs: two different system prompts. The texts are plain text files in
`jevmanic/instructions/<name>/` (`move.txt`, `key.txt`, and
`key_facts_only.txt`). To try a new text, copy a folder, change the files,
and run with `--instructions <name>`. The files have no markup: the jev
documentation says that instructions are a string or JSON, and that jev reads
the words as they are.

- **PromptA** (the normal configuration). The instructions have three
  parts: the goal, the meaning of each fact, and knowledge of the game (for
  example "a crumbling floor breaks a little each time Willy stands on it").
  They do not say "select X when Y".
- **PromptB** (for comparison only). The instructions are a numbered list
  of rules of the form "select X when Y". Jev executes a procedure that we
  wrote. Most of the success of promptB comes from that procedure, not from
  jev.

## Result

PromptA with the present default configuration. 10 live runs for each
cavern. A run is complete when Willy has all keys and goes into the portal.

| Cavern | Complete runs | Mean keys | The older table |
| --- | --- | --- | --- |
| 1 Central Cavern | **10 of 10** | 5 of 5 | 1 of 10, 2.5 keys |
| 2 The Cold Room | 4 to 6 of 10 | 3.0 to 4.1 of 5 | 6 of 10, 4.1 keys |
| 3 The Menagerie | **10 of 10** | 5 of 5 | 2 of 10, 2.3 keys |
| 4 Abandoned Uranium Workings | 0 of 10 | 4.0 of 5 | 0 of 10, 1.8 keys |
| 5 Eugene's Lair | 0 of 10 | 0.5 of 5 | 0 of 10, 1.9 keys |
| 6 Processing Plant | 0 of 10 | 2.6 of 5 (after a correction, see below) | 0 of 10, 3.6 keys |
| 7 The Vat | 1 of 10 | 0.5 of 5 | 4 of 10, 2.9 keys |
| 8 Miner Willy meets the Kong Beast | 0 of 10 | 0.7 of 4 | 0 of 10, 1.8 keys |
| 9 Wacky Amoebatrons | **10 of 10** | 1 of 1 | 10 of 10 |
| 10 The Endorian Forest | 0 of 10 | 2.2 of 5 | 0 of 10, 1.8 keys |
| 11 Attack of the Mutant Telephones | **5 of 10** | 3.8 of 5 | 0 of 10, 2.3 keys |
| 12 Return of the Alien Kong Beast | 0 of 10 | 0.0 of 5 | 0 of 10, 0.8 keys |
| 13 Ore Refinery | 0 of 10 | 1.0 of 5 | 0 of 10, 1.0 keys |
| 14 Skylab Landing Bay | 0 of 10 | 0.4 of 4 | 0 of 10, 0.9 keys |
| 15 The Bank | 0 of 10 | 1.8 of 3 | 0 of 10, 2.0 keys |
| 16 The Sixteenth Cavern | 0 of 10 | 1.7 of 4 | 0 of 10, 1.6 keys |
| 17 The Warehouse | 0 of 10 | 0.7 of 5 | 0 of 10, 0.0 keys |
| 18 Amoebatrons' Revenge | **8 of 10** | 0.8 of 1 | 3 of 10 |
| 19 Solar Power Generator | 0 of 10 | 1.0 of 3 | 0 of 10, 0.9 keys |
| 20 The Final Barrier | 0 of 10 | 4.2 of 5 | 0 of 10, 2.5 keys |

The table is from the configuration with the key decision from the facts
only. The key decision now uses the map of the cavern by default. We measured
the new default on 5 caverns (10 runs each): Central Cavern 9 of 10, The
Menagerie 9 of 10, cavern 12 from 0.0 to 1.6 keys, cavern 8 no change, and
The Cold Room **1 of 10** (before: 4 to 6 of 10). In The Cold Room, the first
two key decisions are good (D, E). The third decision is key C in 9 of 10
runs: the key in the shaft, which Willy cannot come back from. The option
`--facts-only-keys` gives the old key decision.

After a correction of the `way_down` fact (see "What we learned"), Central
Cavern is complete in **40 of 40** runs (two measurements of 20 runs), and
The Menagerie in 17 of 20.

All results above used a dead end check of 12 moves. The default is now 4
moves, which is a smaller help from the code. With 4 moves, Central Cavern
is complete in 19 to 20 of 20 runs, The Cold Room in 2 of 20, and The
Menagerie in 12 of 20.

Jev completes 4 caverns in 8 or more of 10 runs (1, 3, 9, 18), and 2 caverns
in approximately half of the runs (2, 11). It completed caverns 4 and 7 one
time each. 12 caverns have no complete run.

"The older table" is the first measurement of all caverns (200 runs), before
the corrections of the prompt text and of the valid moves. The changes after
that table helped caverns 1, 3, 4, 11, 18, and 20. They made caverns 5, 6, 7,
and 8 worse (fewer keys).

We found the cause for cavern 6 after this table: the state gave the way down
on one side, and the `progress` measure used a way down on the other side,
and the measure changed sides each time Willy moved one cell. Willy went left
and right between two columns in each run. With one preferred side for the
two, cavern 6 collects 2.4 keys, and not 0.0. It is still 0 of 10 complete.
The way down now also refuses a fall of 5 rows or more, which kills Willy.
That second correction gave no measurable change (2.6 keys).

The causes that we found in the other caverns, not corrected yet:

- Cavern 8: Willy jumps into the small place between two walls where the
  closed portal is. His walks have no effect there. The only way out is a
  jump to the left, onto the level of a guardian. The look-ahead removes that
  jump each time that the guardian makes it deadly, thus the only valid move
  is `wait`, and the run stops after 30 decisions with no new place. (We
  first thought that Willy could never move again there. A test showed that
  the jump to the left gets him out when the guardian is away.)
- Cavern 17: Willy moves between the two columns of the start platform. The
  only way forward is `walk_right`, which is "nearer", and jev selects
  `walk_left` with a confidence of 0.31.

One complete run costs approximately $0.004 to $0.010. The summaries of all
measurements are in `experiments/results/`.

**The base for comparison: a random player.** It gets the same valid moves as
jev (the same look-ahead and the same dead end check of 12 moves) and selects
one at random. It makes no jev call. 10 runs for each cavern:

| Cavern | Jev: complete | Jev: keys | Random: complete | Random: keys |
| --- | --- | --- | --- | --- |
| 1 Central Cavern | 10 of 10 | 5 | 0 of 10 | 0.1 |
| 2 The Cold Room | 4 to 6 of 10 | 3.0 to 4.1 | 0 of 10 | 1 |
| 3 The Menagerie | 10 of 10 | 5 | 0 of 10 | 0.6 |
| 4 Abandoned Uranium Workings | 0 of 10 | 4.0 | 0 of 10 | 0.1 |
| 5 Eugene's Lair | 0 of 10 | 0.5 | 0 of 10 | 0.6 |
| 6 Processing Plant | 0 of 10 | 2.6 | 0 of 10 | 0.9 |
| 7 The Vat | 1 of 10 | 0.5 | 0 of 10 | 0 |
| 8 Miner Willy meets the Kong Beast | 0 of 10 | 0.7 | 0 of 10 | 0.2 |
| 9 Wacky Amoebatrons | 10 of 10 | 1 | 0 of 10 | 0 |
| 10 The Endorian Forest | 0 of 10 | 2.2 | 0 of 10 | 0.6 |
| 11 Attack of the Mutant Telephones | 5 of 10 | 3.8 | 0 of 10 | 0 |
| 12 Return of the Alien Kong Beast | 0 of 10 | 0.0 | 0 of 10 | 0.5 |
| 13 Ore Refinery | 0 of 10 | 1.0 | 0 of 10 | 0 |
| 14 Skylab Landing Bay | 0 of 10 | 0.4 | 0 of 10 | 0.1 |
| 15 The Bank | 0 of 10 | 1.8 | 0 of 10 | 0.3 |
| 16 The Sixteenth Cavern | 0 of 10 | 1.7 | 0 of 10 | 0 |
| 17 The Warehouse | 0 of 10 | 0.7 | 0 of 10 | 0 |
| 18 Amoebatrons' Revenge | 8 of 10 | 0.8 | 0 of 10 | 0 |
| 19 Solar Power Generator | 0 of 10 | 1.0 | 0 of 10 | 0.4 |
| 20 The Final Barrier | 0 of 10 | 4.2 | 0 of 10 | 0 |

The random player completed 0 of 200 runs, and it collects 0.3 keys in a run
(the mean of all caverns). Jev completed 48 to 50 of 200 runs and collects
2.0 keys. Thus the look-ahead alone does not complete a cavern. The decisions
of jev do. In 3 caverns jev is not better than the random player: cavern 5
(0.5 and 0.6 keys), cavern 12 (0.0 and 0.5 keys), and cavern 14 (0.4 and 0.1
keys, no complete run). An earlier measurement with 30 random runs for each
of caverns 1, 2, and 3 gave 0, 1, and 0 complete runs.

### PromptB compared with promptA

We wrote the rules of promptB with caverns 1 and 2. Caverns 3, 4, and 16
are a fair test: they have horizontal guardians only, and we did not write a
rule with them. The two prompts ran at the same time with the same code. 10
live runs for each cavern and each prompt:

| Cavern | PromptA | PromptB |
| --- | --- | --- |
| 1 Central Cavern (rules written with it) | 10 of 10 | 10 of 10 |
| 2 The Cold Room (rules written with it) | 6 of 10 | 9 of 10 |
| 3 The Menagerie (fair test) | 8 of 10, 4.7 keys | 1 of 10, 1.4 keys |
| 4 Abandoned Uranium Workings (fair test) | 0 of 10, 3.0 keys | 0 of 10, 1.3 keys |
| 16 The Sixteenth Cavern (fair test) | 0 of 10, 1.7 keys | 0 of 10, 1.0 keys |

The table above is from older code, in which promptB got no map for the
key decision. The instructions are now the only difference between the two
modes. With the present code (dead end check of 4 moves), 20 runs each:

| Cavern | promptA | promptB |
| --- | --- | --- |
| 1 Central Cavern (rules written with it) | 19 to 20 | 20 |
| 2 The Cold Room (rules written with it) | 2 to 4 | **19** |
| 3 The Menagerie (fair test) | 12 to 17 | **2** |

The result is the same as before, and it is now a clean comparison of two
texts. In The Cold Room, rule 1 of the key text puts the one-way key last.

The rules are better on the caverns that we wrote them with, and worse on the
other caverns. They fit caverns 1 and 2 too well. PromptA is thus the normal
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

Open http://127.0.0.1:8000. The page explains itself: it starts with what
jev and the game are, and how to read the page.

- **1 · Watch a recorded run** (free). A replay makes no jev calls and needs
  no API key. The emulator is deterministic, thus a replay is always the same
  game. Select a group of recorded runs first:
  - **Saved example runs**: complete runs that are part of the project
    (folder `demo/`). Use them for a demonstration.
  - **Your live runs**: each run that you start is saved here (folder
    `runs/`).
  - **Measurement: name**: the runs of one measurement (folder
    `runs/name/`). A failed run shows where and why jev failed.

  The box **complete runs only** hides the runs in which Willy did not get
  to the portal.
- **2 · Let jev play a new game** (uses the jev API). Select the cavern and
  press **Start live run**. **Settings** has the options, each with a short
  text: who selects the next key (jev, or a fixed order that starts with the
  optimum order of the cavern), the map for the key decision, the depth of
  the dead end check (the default is 4 moves), and promptB.
- **Pause**, **Step**, **Stop**, and **Speed** are above the game screen, in
  a replay and in a live run. A line of text tells what occurs now and what
  you can do next. The keys: Space = pause or resume, right arrow = step. The
  game stops after a decision and before its move, thus you see what jev
  selected before it occurs.
- **show the possible moves**: during a pause, the game screen shows the path
  of Willy for each of the 6 macros, as faded figures of Willy in the colour
  of the macro, one figure for each 2 game ticks. The selected macro is the
  brightest and has the mark ▶. A red cross marks a move that kills Willy.
  The paths are for the viewer only: they do not go to jev or to the log
  file.
- Click a bar in the timeline to examine an earlier decision, with its
  possible moves.

The page has a second tab, the **key decision lab**. It asks jev the key
question for a situation that you set up: select a cavern, click a key to
mark it as collected, and click any other place to put Willy there. The
request is the same as in a live run (one jev call, approximately $0.0001).
The page shows the probabilities, the exact state with the map, and the next
key of the optimum order for comparison. You can select the instruction set,
and you can change the instruction text in a text box to see how the answer
changes (the change is not saved). Limits: the cavern is in its start
condition, and jev has no memory of earlier decisions.

The first tab shows, for each decision:

- the key or switch that jev selected as the target, with a yellow box in
  the game
- the probability of each macro, the selected macro, and the confidence
- each macro that jev did not get, with the cause
- **the exact state JSON and the exact questions of the request**
- the time of the jev call, the input tokens, and the cost

### The terminal

```sh
uv run python -m jevmanic.cli --cavern 2
uv run python -m jevmanic.cli --cavern 2 --until-complete
uv run python -m jevmanic.cli --cavern 2 --instructions promptB   # comparison only
uv run python -m jevmanic.cli --help                      # all options
```

The cavern number starts at 1. With `--until-complete`, the script plays again
until a run is complete (10 runs at most). Each live run writes a log file in
`runs/`. The viewer can replay it.

### Measurement

```sh
uv run python -m experiments.measure --caverns 1,2 --runs 10 --label my-test
uv run python -m experiments.measure --caverns 1,2 --runs 10 --label rules --instructions promptB
uv run python -m experiments.diagnose runs/my-test/<file>.jsonl
```

`experiments/measure.py` plays many live games at the same time and prints a
table: complete runs, keys, decisions, tokens, and the rate of decisions with
a confidence below 0.5. The terminal and the measurement have the same 6 run
options. Each option changes one part of the design, to measure what it
gives:

| Option | Effect |
| --- | --- |
| `--instructions NAME` | the set of instruction texts: `promptA` (default) or `promptB` (comparison) |
| `--facts-only-keys` | the key decision gets the facts only, and no map |
| `--key-every N` | repeat the key decision after N decisions (default 25, 0 = no repeat) |
| `--depth N` | the moves that the dead end check looks ahead (default 12, 0 = off) |
| `--key-order LETTERS` | the code sets the key order, and there is no key request. `optimum` gives the optimum order of the cavern (`jevmanic/key_orders.py`). |
| `--random-moves` | a base for comparison: a random choice from the valid moves |

Earlier measurements used switches that are now removed, because the
measurement showed no gain. Their results stay in `experiments/results/`.
The log files go to `runs/<label>/`, and the viewer shows
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

A conveyor carries Willy along. In the game, he stands still on it only if
the opposite direction is held when he drops onto it, and for as long as it
is held. After a jump in the direction of the conveyor, or after one tick
with no key, the conveyor has him and he cannot stop again. The macros use
this: a fall onto a conveyor holds against it, and `wait` on a conveyor holds
against it ("do not move"). A walk in the direction of the conveyor rides it.

There is a second, less frequent request: jev selects the **target** (a key,
or a switch in the two caverns that have switches). The code sends it at the
start, after each collected key, and again after 25 decisions.

### Valid moves

Jev gets only the moves that are valid. A move is not valid in three cases:

1. The move kills Willy.
2. The move is a dead end: Willy is alive after it, but then he cannot avoid
   a death. To find this, the code looks for one sequence of 4 macros that
   keeps Willy alive. If there is none, the move is a dead end. Example: a
   guardian follows Willy 1 cell behind him toward a wall. Each step is safe,
   but after 5 steps no move is safe. This check asks only "can Willy stay
   alive?". It does not look at keys or at the portal, and it does not select
   a move. It is the part of the design that is nearest to a search.
3. The move has no effect: Willy stays in the same place. `wait` is valid
   only when something can change (a guardian is near, or Willy is on a
   crumbling floor or on a conveyor).

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
`demo/cavern-02-the-cold-room-promptA.jsonl`. The exact text of all
instructions is in `jevmanic/instructions/`. The code that makes the state is in
`jevmanic/describe.py`. The viewer shows the exact state and questions of
each request.

### Request 1: the key decision

Jev gets this request at the start, when Willy collects a key, and again
after 25 decisions. The state has the map of the cavern with its legend, and
one entry with facts for each key that is left (and for each switch that is
not flipped). This example shows 2 of the keys and 3 legend entries:

```json
{
  "map_legend": {
    "W": "Willy. He is 2 cells wide and 2 cells high.",
    "A": "key A. Willy collects it when he touches it.",
    "B": "key B. Willy collects it when he touches it.",
    "...": "one entry for each symbol on the map"
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

On the map, each key has its own letter and keeps it for the full run. A
conveyor is `<` or `>`: the direction in which it moves Willy. The legend
says what each symbol means for Willy.

| Field of a key | Meaning |
| --- | --- |
| `what` | key, or switch (with the fact that a switch changes the cavern) |
| `side`, `horizontal_cells`, `horizontal_distance` | where it is, left or right of Willy |
| `height`, `floor_rows_apart` | its floor level, compared with the floor of Willy. A key that hangs above the floor of Willy is on the same level. |
| `rows_above_its_floor` | how high it is above its floor |
| `floor_below_key` | floor, crumbling floor, or conveyor |
| `between_walls`, `one_way_trip` | the key is in a shaft above a crumbling floor. Willy falls through and cannot go back up. |
| `current_target` | the key that Willy goes to now. Jev can keep it or change it. |
| `decisions_used_for_it`, `gave_up_on_it` | a short memory for each key |

The question is a Choice with one option for each entry. The instructions:

> Willy is a miner in a platform game. The map shows the cavern, and `map_legend` tells what each symbol means. `keys` gives facts about each key or switch relative to Willy. Willy must collect all keys and then go into the exit portal. Willy can climb only 2 rows with one jump. He can fall to a lower floor, but after a long fall he cannot climb back. A crumbling floor breaks when Willy uses it, thus a way that goes across a crumbling floor can be open only one time. Select the key or switch that Willy gets next, in an order that lets him get all keys. `current_target` marks the key that Willy goes to now. Willy can keep it or change it. `decisions_used_for_it` tells how many decisions Willy used for this key before. `gave_up_on_it` tells how many times Willy made no progress toward this key.

The answer in the example: `key_D`, confidence
0.47. This request used 1638 input
tokens.

A test showed that the text must name the map. With the map in the state and
a text that does not name it, jev selects the same key as with no map.

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
      "ends_on": "crumbling floor, new"
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
| `target` | the key or switch that jev selected, or the portal. When the target is on a higher floor, it has a `way_up`: the nearest place where a jump gets to a higher platform. When the target is on a lower floor, it has a `way_down`: the nearest safe edge or crumbling floor. If Willy stands on a crumbling floor, it is the safe fall place on that floor that is nearest to the target. |
| `to_the_left`, `to_the_right` | the first thing in the path of Willy on his level: wall, nasty, edge, or nothing, with the distance in cells |
| `guardians` | the position of each horizontal guardian relative to Willy, and its direction. For a guardian on the level of Willy: is Willy in its patrol area, and where the patrol area ends. (Facts about vertical guardians exist behind a switch. They are off, because they made the results worse.) |
| `air` | plenty, low, or critical |
| `progress_measures` | the place that `progress` measures the distance to: the target (same level), the way up (higher floor), or the way down (lower floor) |
| `moves` | the true result of each valid macro, from the look-ahead |
| `moves.*.movement` | where Willy is after the macro |
| `moves.*.progress` | nearer, farther, or same |
| `moves.*.place` | new place, visited before, or visited many times (memory) |
| `moves.*.tried_from_here` | did Willy select this macro at this place before (memory) |
| `moves.*.ends_on`, `collects_key`, `completes_cavern`, `warning` | only when they apply. `ends_on` and `willy.standing_on` give the condition of a crumbling floor: new, partly gone, or almost gone. The code reads it from the pixels of the tile. |
| `moves_not_offered` | each macro that jev does not get, with the cause: it kills Willy (guardian, nasty, fall, or dead end), or it has no effect |

The request has 4 questions. Only the first one controls Willy.

**`move` (Choice).** The options are the valid macros. The instructions:

> Willy is a miner in a platform game. The goal: Willy must collect all keys, then go into the exit portal, and he must stay alive. The target is the key that Willy goes to now, or the portal when no key is left. Select the move that is the best for Willy now. `moves` gives the true result of each possible move. All moves in `moves` are safe and have an effect. `moves_not_offered` gives the moves that Willy cannot make now, with the cause. The meaning of the facts: `progress` tells if a move gets Willy nearer to the place that `progress_measures` names. `place` tells how frequently Willy was at the place where the move ends. `tried_from_here` tells if Willy made this move from this place before. `collects_key` tells that Willy gets a key with this move. `completes_cavern` tells that Willy goes into the portal with this move and the cavern is complete. `ends_on` tells that Willy stands on a crumbling floor after this move, and how much of that floor is left. `warning` tells that no move is safe after this move. Knowledge of the game: Willy can climb only 2 rows with one jump. If Willy comes back to the same places again and again, the direct way is closed, and he must go a different way, also if that way goes away from the target first. A crumbling floor breaks a little each time Willy stands on it. It can be the only way up, and it is also a way down. A nasty does not move: if it stops a jump, a jump from a different cell can go over it. A guardian moves along its patrol area: Willy can wait for it to go away, jump over it, or go out of its patrol area.

The criteria of the options:

- `jump_right`: Jump to the right. The result is in `moves.jump_right`.
- `jump_left`: Jump to the left. The result is in `moves.jump_left`.
- `walk_right`: Walk 1 cell to the right. The result is in `moves.walk_right`.
- `walk_left`: Walk 1 cell to the left. The result is in `moves.walk_left`.
- `jump_up`: Jump straight up. The result is in `moves.jump_up`.
- `wait`: Do not move. The result is in `moves.wait`.

The answer in the example: `walk_right`, confidence
0.64. The probabilities: `walk_right` 0.74, `walk_left` 0.11, `jump_left` 0.08, `wait` 0.07. This request used
1524 input tokens and took 288 ms.

The code makes no jev call when only one macro is valid, and when all valid
macros have the same result (Willy is in the air).

## What we learned about jev

- **Give jev the goal and the meaning of each fact.** In Central Cavern, the
  state said that `jump_left` had `collects_key: true`, and jev selected
  `walk_left` (0.51 against 0.44). The instructions did not say that Willy
  must collect keys, and did not say what `collects_key` means. With the goal
  and the meaning in the text, and with no rule about what to select, the
  cavern went from 3 of 10 to 10 of 10 complete runs. The decisions per run
  (74) are near the result of our procedure in promptB (70).
- **The dead end check gives much help.** Complete runs of 10, with the
  present configuration:

  | Moves of the dead end check | Central Cavern | The Cold Room | The Menagerie |
  | --- | --- | --- | --- |
  | 0 (off) | 6 | 0 | 0 |
  | 1 | 7 | 1 | 0 |
  | 2 | 10 | 4 | 1 |
  | 4 | - | - | 6 |
  | 6 | - | - | 9 |
  | 8 | - | - | 9 |
  | 12 (the value at that time) | 10 | 4 | 10 |

  A second measurement of Central Cavern with the present code, 20 runs
  each: 7 of 20 with the check off, 9 with 1 move, 17 with 2 moves, and 20
  with 4 moves. All 26 deaths are at one place: Willy lands on the conveyor
  behind the guardian, the conveyor carries him along, and the guardian
  turns. With the check off, Willy is still alive at the end of each move
  that jev gets, because the look-ahead of 1 move removes each move that
  kills him directly.

  **The default is now 4 moves.** It is a compromise: it is sufficient for
  Central Cavern, and it is a smaller help from the code than 12 moves. All
  results in this document before this change used 12 moves. 20 runs each,
  with the present code:

  | Moves of the dead end check | Central Cavern | The Cold Room | The Menagerie |
  | --- | --- | --- | --- |
  | 4 (the default) | 19 to 20 | 2 | 12 |
  | 6 | - | 4 | 15 |
  | 12 | 20 | 2 to 3 | 15 to 19 |

  The Menagerie pays for the compromise: 6 of its 8 failed runs at 4 moves
  are deaths. Use `--depth 12` to get the earlier results again.

  A check of 1 move gives almost no gain. 2 moves are sufficient for Central
  Cavern and The Cold Room. The Menagerie needs 6 moves.

  In The Menagerie at depth 2, all 9 deaths are at the same place, after 4 to
  6 decisions with no real choice: one trap that is 6 moves deep. The deep
  check removes the first step into it. A large part of "stay alive" thus
  comes from the code, not from jev.
- **A shorter prompt was worse.** We wrote the move text again with the same
  content in short sentences and a "field: meaning" form (190 words, not
  293). Central Cavern needed 89 decisions, not 71. The Menagerie went from
  10 of 10 to 4 of 10. Jev reads full sentences better than a terse list.
  We removed the short text.
- **A code guess can be better than two honest facts.** In cavern 4, the
  code selects a single tile in a corner as "the way up", `progress` points
  to it, and Willy goes into that trap in each run. We gave jev the way up on
  the left and on the right as facts, and measured `progress` to the target.
  Cavern 4 got its first complete run, but Central Cavern went from 10 of 10
  to 5 of 10, and The Menagerie from 10 of 10 to 1 of 10. The one reference
  that the code selects does important work. We removed the two facts.
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
  More text in the state takes weight away from the important facts. We
  removed this memory.
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

Designs that we measured and removed, because they were not better than promptA on caverns 1 to 4: one Noul question for each move (1 of 12 complete),
and a question in which jev selects the next platform from the map (1 of 18).
We also removed a "route mode": the code searched sequences of up to 32
macros to find the platforms that Willy can get to, jev selected one, and the
code walked the path. It completed caverns 2 and 3 in 9 and 10 of 10 runs,
but the code walked 3459 macros and jev selected 175 single moves. That
result came from the search, not from jev.

`experiments/probe_target.py` compares target rules with a free choice.

## Open work

- **The map of the cavern gives jev a better key decision.** A test that
  plays no game (`experiments/probe_key_order.py`) asks "which key next?" in
  13 situations of caverns 1 to 4. The reference is the key order of the
  complete recorded runs. Correct next key: facts only 5 of 13, map only 8,
  map and facts 12. In Central Cavern, jev selects key E first with the map.
  That is the known good order (E, A, C, D, B). With the facts only, it
  selects D first and gets E last.

  In play, with the map in the key decision, Willy has all 5 keys of Central Cavern at
  decision 35 to 39. With the facts only, he has them at decision 62 to 66.
  But the complete runs went from 10 of 10 to 7 of 10. The better key order
  is not the cause. A test in which the code sets the key order (option
  `--key-order EACDB`, no key request, the movement not changed) gives 10 of
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
- **A switch as a target made no difference.** In the two Kong Beast caverns
  (8 and 12), a switch is a target that jev can select. With the switch
  targets and with no switch targets, the two caverns are 0 of 10, with the
  same number of keys (0.7 and 0.8 in cavern 8, 0.0 in cavern 12). The runs
  fail before the switches are important.
- **Facts about vertical guardians made the results worse.** The code reads
  the vertical guardians, and the state can give their column, their
  direction, and if their column crosses the level of Willy. Caverns 9 and
  18 (4 vertical guardians each), complete runs of 10: with the facts 9 and
  2, without them 10 and 8. With the facts, a run needs more decisions (109
  and not 73 in cavern 9), and more decisions have a low confidence. The
  look-ahead already removes each move that a vertical guardian makes
  deadly, thus the facts add text and no safety. We removed them.
- **An LLM in the place of jev: one run, for comparison.** The decision
  maker `jevmanic/llm_brain.py` calls Claude Haiku through the `claude`
  command line tool. It gets the same instructions, the same options, and
  the same state as jev, with no tools and no project files. One run of
  Central Cavern, the default configuration:

  | | jev | Claude Haiku |
  | --- | --- | --- |
  | Result | complete in 8 to 10 of 10 runs | complete (1 run) |
  | Decisions | 70 to 75 | 123 |
  | All 5 keys at decision | 37 to 42 | 87 |
  | Time for the decisions of one run | 24 seconds | 39 minutes |
  | Time for one call | 0.3 seconds | 17.8 seconds |
  | Cost of one run | $0.004 | $1.30 |

  Haiku collected the first key at decision 13 (jev: 14). Then it went left
  and right on a lower platform for approximately 60 decisions before it
  found the way up. It reasons before each answer, thus one call is slow.
  This is one run only. It shows that the task is possible for an LLM with
  the same facts, and that jev is 100 times quicker and 300 times cheaper
  for each decision. Command:
  `uv run python -m jevmanic.cli --cavern 1 --llm haiku`.
- **A reasoning model as the planner, and jev as the player.** A clean
  subagent (a reasoning model) got only the map, the legend, the guardian
  limits, and the game mechanics. It gave a key order for caverns 1 to 4 with
  reasons, for example "the top floor can only be reached from the far left,
  and E is on the only way up". For Central Cavern it gave E A C D B, the
  known good order. For The Cold Room it gave the most frequent order of our
  complete runs. We used only its key order (option `--key-order`), and jev
  made each move decision. Complete runs of 10, caverns 1 to 4: 7, 6, 9, 0.
  The default gives 8 to 10, 4 to 6, 10, 0. The runs need fewer decisions
  (The Cold Room 76, not 95 to 122; The Menagerie 54, not 66), but no more
  runs are complete. The full record (the input, the answer with the
  reasons and the route plans, and the measurement) is in
  [docs/planner-subagent.md](docs/planner-subagent.md).
- **10 runs are not sufficient to compare two configurations that are near.**
  The same configuration (the code sets the order E A C D B in Central
  Cavern) gave 10 of 10 in one measurement and 7 of 10 in the next one.
  A second example: after the clean of the code, Central Cavern gave 6 of 10,
  and then 19 of 20 with the same code.
  Thus a difference such as 7 of 10 against 10 of 10 can be chance. This
  makes some conclusions in this document weaker, for example "the second
  key decision is the cause". Large differences (10 of 10 against 1 of 10)
  are real.
- **A separate key decision with the map gave no gain in play.** Jev gets
  the key decision, with the map, at the start and when Willy collects a
  key, and the run is then in movement mode. `--key-every 25` repeats the key
  decision after 25 decisions. This is now the default. Caverns 1 to 4,
  complete runs of 10: 7, 0, 7, 0 with no repeat, and 9, 2, 6, 0 with the
  repeat (the normal configuration: 10, 4 to 6, 10, 0). The key decisions
  are good, but the runs fail in movement mode, where the better key order
  shows weak move facts.
- **A correction must be true in each cavern.** After the last key of
  Central Cavern, Willy stands on the crumbling floor that is his way down,
  and `progress` said that a walk toward the portal is nearer. Jev gave the
  two walks almost the same probability (0.45 and 0.44). The walk to the
  right ends in a place with no way out. This was the cause of 4 of 5 failed
  runs. The first correction ("to leave the way down is farther") gave
  Central Cavern 19 of 20, but The Menagerie went to 0 of 20: there, Willy
  must walk along a long crumbling floor to the place above the last key,
  and each cell of that floor is a way down. The correction that is true in
  the two caverns: if Willy stands on a crumbling floor, the way down is the
  safe fall place on that floor that is nearest to the target. `way_down`
  and `progress` use that place. Result: Central Cavern 20 of 20 and 20 of
  20, The Menagerie 17 of 20, The Cold Room 2 of 10 (no change).
- **The condition of a crumbling floor: no harm, and no gain that we can
  measure.** The game keeps no counter. It moves the pixels of the tile down
  while Willy stands on it, and one walk across a tile uses approximately
  half of it. The move facts now give the condition as a word. 20 runs each:
  Central Cavern 20 (before: 40 of 40), The Cold Room 2 (before: 3 of 20),
  The Menagerie 19 (before: 17). We kept it, because it is true and it
  corrects `ends_on` for a tile that is gone after the move.
  We then also gave the condition to the key decision: a symbol `-` on the
  map for a tile that is almost gone, and the condition in
  `floor_below_key`. The key orders did not change (Central Cavern E D B in
  20 of 20 runs, The Cold Room D E C in 17 of 20), and the results were 20,
  2, and 16 of 20. We removed it from the key decision.
- **A guardian fact for each move made the results worse.** All deaths with
  a short dead end check are at the conveyor of Central Cavern, behind the
  guardian. We gave each move the fact `guardian_after` (where the guardian
  on the level of Willy is after the move, and if it moves toward him).
  Central Cavern, 20 runs: 4 and not 7 with the check off, 14 and not 17
  with 2 moves. The Menagerie with the default check: 7 of 20, not 17 to 19.
  We removed it. This is one more case of "more text in the state takes
  weight away from the important facts".
- **The conveyor hold: true to the game, but no gain that we can measure.**
  Before this change, Willy was always carried on a conveyor, and `wait` was
  a ride. Central Cavern, 20 runs: 4 and not 7 with the dead end check off,
  20 and not 17 with 2 moves, 20 of 20 with the default. The Menagerie: 15
  of 20. At the deadly place of Central Cavern (the conveyor behind the
  guardian), Willy gets onto the conveyor with a jump, and then no key can
  stop him. Jev can select a drop there (`walk_left`, then Willy stands
  still), but it selects `jump_left` with 0.54 to 0.57, because the state
  gives no cause to prefer the walk. The dead end check of 2 to 4 moves does
  real work at this place, and we found no fact that replaces it.
- **The key decision before each move: no gain, and 2 times the cost.**
  `--key-every 1`, 20 runs each, caverns 1, 2, 3: 20, 0, 17 (the base: 19,
  2, 12). Jev kept the target in 97 % of 5640 key requests, and the key
  orders did not change.
- **The word "optimum" in the key question: no gain.** "Select the optimum
  key or switch for Willy to get next": 20, 4, 13. We put the text back.
- **The optimum key order helps one cavern and harms a different one.** The
  code sets the order (`--key-order optimum`), and jev makes each move
  decision. 20 runs each: Central Cavern 20 (80 decisions, not 100), The
  Cold Room **12** (the base: 2 to 4), The Menagerie **3** (the base: 12 to
  17, all other runs "stuck: no progress"). In The Cold Room, the optimum
  order has the one-way key C last, and jev selects it third. In The
  Menagerie, the optimum order is a route that the move facts do not
  support.
- **Laya in the place of jev: it follows the facts, but it completes no
  cavern.** [Laya](https://github.com/mizorewww/laya-mlx) is a typed decision
  model (421M parameters) that runs on an Apple Silicon computer with MLX.
  Its request has the same form as a jev request (`--laya`, install with
  `uv sync --extra laya`). One request takes approximately 50 ms, with no
  network call and no cost. The answers are deterministic, thus 10 runs are
  one run.
  - **The same request as jev (promptA, the JSON state): 0 of 30 runs, and no
    key.** The probabilities are almost equal. Laya gives 256 tokens to the
    instructions and the options together, and it cuts the rest with no
    message: the 6 move options use 130 tokens, and promptA has 402 tokens.
    The full input has 1024 tokens at most. `LayaBrain.cut_report()` gives
    what was cut.
  - **What Laya can read.** We measured this on the 261 recorded decisions
    of three complete jev runs ("does Laya select a move whose `progress` is
    nearer?"). Nested JSON: 26 to 41 of 62. One short sentence for each
    option ("walk_right is nearer."): 56 of 62. A longer instruction, a
    condition ("if there is none, select…"), or a second fact in each
    sentence made it worse. Laya prefers the first option: the mean of the
    probabilities for 6 different option orders removes this (215 of 226,
    and jev has 85 %). One yes or no question for each move was worse.
  - **The form that we use for Laya** (`jevmanic/laya_brain.py`, with
    `--instructions promptC --key-order optimum`): the text "jump_right is
    nearer and new." for each move, the option names with no text, the
    instruction "Select the move that is nearer. A move that collects a key
    is the best.", and the mean of 6 orders. The key decision does not work
    (Laya selects the first key), thus the code sets the key order.
  - **Result in real games:** The Cold Room 4 of 5 keys, and no key in
    caverns 1, 3, 4, 9, and 18. No cavern is complete. Laya follows
    `progress`, but it cannot weigh it against the loop facts, thus Willy
    walks the same path again and again.
  - **The other checkpoints are not better.** The checkpoint that we use
    (`laya-typed-decisions`) is a ModernBERT-large encoder that was trained
    for four business tasks. The general checkpoint (`laya`) and the
    multilingual one select a "nearer" move in 198 and 130 of 226 decisions
    (the one that we use: 212). `RLAgent` in the package is only a second
    name for `Agent`, and the package has no training code. The model is an
    encoder that matches the words of the question with the words of the
    options. It does not weigh two facts. A model of this type needs training
    on this task to do more.
  - **The Snake demo of Laya works in a different way.** Its code finds the
    best move with a planner and writes "Safe. Best route to food." into the
    text of that option. The model matches the word "best". That is against
    the rule of this project, thus we did not do it.
- **A local LLM with the answer read from its logits: the same request as
  jev, and one complete cavern.** Two open projects,
  [jevfire](https://github.com/kikoncuo/jevfire) and
  [SemIf](https://github.com/TheoLeeCJ/SemIf), reproduce the jev interface
  with an open LLM: the model gets the state and the question in one chat
  prompt, each option has a one-letter label, and the code reads the
  probability of each label at the first output position. One forward pass
  is one decision, with no text generation. `jevmanic/local_brain.py` does
  this with `mlx-lm` on this computer (`--local`, install with
  `uv sync --extra local`). The model gets the same instructions, options,
  and JSON state as jev. Qwen3-8B in 4-bit form takes approximately 1.2 s
  for one decision, with no cost.
  - On the 261 recorded jev decisions, Qwen3-4B selects a "nearer" move in
    210 of 226 (jev: 85 %), the key move in 16 of 16, and the same move as
    jev in 157 of 261. Unlike Laya, it reads the full request.
  - Real games, one run each (the model is deterministic): Qwen3-4B got 1,
    2, and 0 keys in caverns 1, 2, and 3. Qwen3-8B got 0 and 2 keys, and
    **completed The Menagerie** in 64 decisions (jev: approximately 80).
  - The model is very sure (1.0 against 0.0), thus when it makes a loop it
    repeats the loop until the run ends. Jev gives soft probabilities, and
    its answers vary, thus it gets out of a loop. A temperature with a
    sampled answer (`LOCAL_TEMPERATURE=2`, 2 runs each) gave Central Cavern
    3.5 keys, The Cold Room 1.5, and The Menagerie 2, with no complete run.
    A temperature of 4 was worse. A temperature of 1.5 gave Central Cavern
    4.5 keys and **The Cold Room complete in 1 of 2 runs** (55 decisions),
    but The Menagerie 2 keys. The soft answers of jev are not only noise:
    they are calibrated, and a flat distribution is not the same thing.
- **The target order is the open problem.** In The Cold Room, the full
  difference between promptB (9 of 10) and promptA (4 to 6 of 10) is
  the order of the keys. We measured two prompt changes for it, 10 runs each:

  | Change to the target text | Cavern 1 | Cavern 2 | Cavern 3 | Cavern 4 | Cavern 16 |
  | --- | --- | --- | --- | --- | --- |
  | None (the normal text) | 10 | 4 to 6 | 10 | 0, 4.0 keys | 0, 1.7 keys |
  | + the meaning of `one_way_trip` | 8 | 0 | 10 | - | - |
  | The three target rules of promptB | 7 | 8 | 9 | 0, 0 keys | 0, 2.0 keys |

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
- **An error in the saved game states, now corrected.** The dead end check
  and the start states of the caverns used the same emulator slots. A live
  run wrote over the start state of caverns 1 to 5. This had an effect only
  when one process played more than one run (the viewer, and
  `--until-complete`). The measurements were not affected, because each
  measured run has a new emulator. A test now checks the slots.

## Limits

- The code reads vertical guardians, Eugene, and the switches. The state has no
  facts about vertical guardians, because they made the results worse. We did not measure the switch facts. The column and the rows of
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
| `jevmanic/describe.py` | the state: the map, the key facts, and the move facts |
| `jevmanic/brain.py` | questions and the jev calls |
| `jevmanic/instructions/` | the instruction texts: `promptA/`, `promptB/`, and your own folders |
| `jevmanic/llm_brain.py` | an LLM as the decision maker, for comparison |
| `jevmanic/laya_brain.py` | Laya, a local typed decision model, as the decision maker, for comparison |
| `jevmanic/local_brain.py` | a local LLM as the decision maker, with the answer read from its logits, for comparison |
| `jevmanic/runner.py` | the settings, live run, log file, replay |
| `jevmanic/options.py` | the run options of the terminal and the measurement |
| `jevmanic/server.py`, `jevmanic/web/` | viewer |
| `jevmanic/lab.py` | the key decision lab of the viewer |
| `jevmanic/key_orders.py` | the optimum key order of each cavern |
| `jevmanic/cli.py` | live run in the terminal |
| `experiments/` | measurement, diagnosis, and tests of how well jev reads a state |
| `experiments/results/` | the summaries of the measurements in this document |
| `docs/planner-subagent.md` | the test with a reasoning model as the planner |
| `demo/` | recorded complete runs, in git |
| `runs/` | log files of your runs (JSON Lines), not in git |

The header of a log file has the macro version (`macros: 2` = with the
conveyor hold). A log file with no version replays with the old macros.
A log file has one header line, then one line for each jev request (a
"target" record or a "decision" record with its state and answers), then one
end line.

The emulator core comes from the esp32-zxspectrum project, which took it from
[OpenVegaPlus](https://github.com/alvaroalea/OpenVegaPlus).
