# jev plays Manic Miner

This project uses [jev](https://docs.typesafe.ai/introduction) to play Manic
Miner. Jev is the System One model from TypeSafe. Jev does not write text. It
gets a state and typed questions, and it gives typed answers with
probabilities.

The game runs on a ZX Spectrum emulator. A web page shows the game, each
decision of jev, and all data that goes to jev.

![The page Watch: a replay of The Cold Room, stopped before decision 13](docs/screenshots/watch.jpg)

The project is standalone. It contains the emulator sources and the game
snapshot.

## The rule of this project

The decisions come from jev. The code gives facts and knowledge of the game.
The code does not tell jev what to select. The code also does not offer a
decision that we know is not valid: a move that kills Willy, a move into a
dead end, or a move with no effect.

An instruction set is the text that jev gets with each question. Each set is
a folder in `jevmanic/instructions/<name>/` with three plain text files:
`move.txt`, `key.txt`, and `key_facts_only.txt`. The files have no markup,
because the jev documentation says that instructions are a string or JSON,
and that jev reads the words as they are. Jev gets the same state, the same
options, and the same schedule of requests with each set. Thus the text is
the only difference between two sets.

- `promptA` is the normal set. It has three parts: the goal, the meaning of
  each fact, and knowledge of the game (for example "a crumbling floor breaks
  a little each time Willy stands on it"). It does not have instructions of
  the form "select X when Y".
- `promptB` is for comparison only. It is a numbered list of rules of the
  form "select X when Y". With promptB, jev follows a procedure that we
  wrote. Most of the success of promptB comes from that procedure.
- `promptC` is the short text for Laya (see "Laya in the place of jev").

To try a new text, copy a folder, change the files, and run with
`--instructions <name>`. The viewer can also make a new set (see "The
viewer").

## Result

A run is complete when Willy has all keys and goes into the portal. The
table gives promptA, with 10 live runs for each cavern. The column "First
measurement" is the first measurement of all caverns (200 runs). That
measurement was before the corrections of the prompt text and of the valid
moves.

| Cavern | Complete runs | Mean keys | First measurement |
| --- | --- | --- | --- |
| 1 Central Cavern | 10 of 10 | 5 of 5 | 1 of 10, 2.5 keys |
| 2 The Cold Room | 4 to 6 of 10 | 3.0 to 4.1 of 5 | 6 of 10, 4.1 keys |
| 3 The Menagerie | 10 of 10 | 5 of 5 | 2 of 10, 2.3 keys |
| 4 Abandoned Uranium Workings | 0 of 10 | 4.0 of 5 | 0 of 10, 1.8 keys |
| 5 Eugene's Lair | 0 of 10 | 0.5 of 5 | 0 of 10, 1.9 keys |
| 6 Processing Plant | 0 of 10 | 2.6 of 5 (after a correction, see below) | 0 of 10, 3.6 keys |
| 7 The Vat | 1 of 10 | 0.5 of 5 | 4 of 10, 2.9 keys |
| 8 Miner Willy meets the Kong Beast | 0 of 10 | 0.7 of 4 | 0 of 10, 1.8 keys |
| 9 Wacky Amoebatrons | 10 of 10 | 1 of 1 | 10 of 10 |
| 10 The Endorian Forest | 0 of 10 | 2.2 of 5 | 0 of 10, 1.8 keys |
| 11 Attack of the Mutant Telephones | 5 of 10 | 3.8 of 5 | 0 of 10, 2.3 keys |
| 12 Return of the Alien Kong Beast | 0 of 10 | 0.0 of 5 | 0 of 10, 0.8 keys |
| 13 Ore Refinery | 0 of 10 | 1.0 of 5 | 0 of 10, 1.0 keys |
| 14 Skylab Landing Bay | 0 of 10 | 0.4 of 4 | 0 of 10, 0.9 keys |
| 15 The Bank | 0 of 10 | 1.8 of 3 | 0 of 10, 2.0 keys |
| 16 The Sixteenth Cavern | 0 of 10 | 1.7 of 4 | 0 of 10, 1.6 keys |
| 17 The Warehouse | 0 of 10 | 0.7 of 5 | 0 of 10, 0.0 keys |
| 18 Amoebatrons' Revenge | 8 of 10 | 0.8 of 1 | 3 of 10 |
| 19 Solar Power Generator | 0 of 10 | 1.0 of 3 | 0 of 10, 0.9 keys |
| 20 The Final Barrier | 0 of 10 | 4.2 of 5 | 0 of 10, 2.5 keys |

Jev completes 4 caverns in 8 or more of 10 runs (1, 3, 9, 18), and 2 caverns
in approximately half of the runs (2, 11). It completed caverns 4 and 7 one
time each. 12 caverns have no complete run.

The changes after the first measurement helped caverns 1, 3, 4, 11, 18, and
20. They made caverns 5, 6, 7, and 8 worse (fewer keys).

Three changes came after the table:

- The key decision now uses the map of the cavern. We measured this on 5
  caverns, 10 runs each: Central Cavern 9 of 10, The Menagerie 9 of 10,
  cavern 12 from 0.0 to 1.6 keys, and cavern 8 with no change. The Cold Room
  went to 1 of 10 (before: 4 to 6 of 10). In The Cold Room, the first two key
  decisions are good (D, E). The third decision is key C in 9 of 10 runs. Key
  C is in the shaft, and Willy cannot come back from the shaft. The option
  `--facts-only-keys` gives the key decision with the facts only.
- We corrected the `way_down` fact (see "What we learned about jev"). After
  the correction, Central Cavern is complete in 40 of 40 runs (two
  measurements of 20 runs), and The Menagerie in 17 of 20.
- The dead end check now looks 4 moves ahead. The table used 12 moves. 4
  moves is a smaller help from the code. With 4 moves, Central Cavern is
  complete in 19 to 20 of 20 runs, The Cold Room in 2 of 20, and The
  Menagerie in 12 of 20.

Cavern 6: we found the cause of the failures after the table. The state gave
the way down on one side, and the `progress` measure used a way down on the
other side. The measure changed sides each time Willy moved one cell. Thus
Willy went left and right between two columns in each run. Now the two facts
use the same side, and cavern 6 collects 2.4 keys (before: 0.0). It is still
0 of 10 complete. The way down also refuses a fall of 5 rows or more, because
such a fall kills Willy. That second correction gave no change that we can
measure (2.6 keys).

We found the causes in two more caverns. We did not correct them yet:

- Cavern 8: Willy jumps into the small space between two walls where the
  closed portal is. A walk has no effect there. The only way out is a jump to
  the left, onto the level of a guardian. The look-ahead removes that jump
  each time that the guardian makes it deadly. Then the only valid move is
  `wait`, and the run stops after 30 decisions with no new place. When the
  guardian is away, the jump to the left gets Willy out.
- Cavern 17: Willy moves between the two columns of the start platform. The
  only way forward is `walk_right`, which is "nearer". Jev selects
  `walk_left` with a confidence of 0.31.

One complete run costs approximately $0.004 to $0.010. The summaries of all
measurements are in `experiments/results/`.

### A random player for comparison

The random player gets the same valid moves as jev: the same look-ahead, and
the same dead end check of 12 moves. It selects one of the valid moves at
random. It makes no jev call. 10 runs for each cavern:

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

The random player completed 0 of 200 runs. It collected 0.3 keys in a run
(the mean of all caverns). Jev completed 48 to 50 of 200 runs and collected
2.0 keys. Thus the look-ahead alone does not complete a cavern. The decisions
of jev complete it. In 3 caverns, jev is not better than the random player:
cavern 5 (0.5 and 0.6 keys), cavern 12 (0.0 and 0.5 keys), and cavern 14
(0.4 and 0.1 keys, no complete run). An earlier measurement with 30 random
runs for each of caverns 1, 2, and 3 gave 0, 1, and 0 complete runs.

### PromptB compared with promptA

We wrote the rules of promptB with caverns 1 and 2. Caverns 3, 4, and 16 are
a fair test, because they have horizontal guardians only, and we did not use
them to write a rule. The two sets ran at the same time with the same code.
10 live runs for each cavern and each set:

| Cavern | PromptA | PromptB |
| --- | --- | --- |
| 1 Central Cavern (rules written with it) | 10 of 10 | 10 of 10 |
| 2 The Cold Room (rules written with it) | 6 of 10 | 9 of 10 |
| 3 The Menagerie (fair test) | 8 of 10, 4.7 keys | 1 of 10, 1.4 keys |
| 4 Abandoned Uranium Workings (fair test) | 0 of 10, 3.0 keys | 0 of 10, 1.3 keys |
| 16 The Sixteenth Cavern (fair test) | 0 of 10, 1.7 keys | 0 of 10, 1.0 keys |

In the code of that table, promptB got no map for the key decision. Now the
instructions are the only difference between the two sets. With the present
code (dead end check of 4 moves), 20 runs each:

| Cavern | promptA | promptB |
| --- | --- | --- |
| 1 Central Cavern (rules written with it) | 19 to 20 | 20 |
| 2 The Cold Room (rules written with it) | 2 to 4 | 19 |
| 3 The Menagerie (fair test) | 12 to 17 | 2 |

The result did not change. In The Cold Room, rule 1 of the key text puts the
one-way key last.

The rules are better on the caverns that we used to write them, and worse on
the other caverns. The rules fit caverns 1 and 2 too closely. Thus promptA is
the normal set. A rule can be a correct change to a prompt, but the rule must
be general. We must also measure it on caverns that we did not use to write
it.

### Summary of the measurements

- The safety part works. A run ends when Willy makes no progress, or when
  the air ends. A run does not end because of a move that the look-ahead
  found safe.
- Jev makes good single decisions, but it does not plan a route. When a move
  goes nearer to the target, jev selects such a move in 85 % of the
  decisions. Jev fails when the direct way is closed and Willy must first go
  away from the target. Jev also uses crumbling floors that Willy needs
  later.
- Jev does not always give the same answer for the same state. When two
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

Open http://127.0.0.1:8000. The menu has three pages: **Runs**, **Watch**,
and **Experiment**. Each page fills the window, and only the panels scroll.
The button **?** tells how the viewer works.

A replay is free. It makes no jev calls, and it needs no API key. The
emulator is deterministic, thus a replay is always the same game. A live run
and a question in the lab call jev.

#### Runs

The page Runs (`/`) shows all recorded runs.

![The page Runs: all groups, with The Cold Room and promptA selected](docs/screenshots/runs.jpg)

- The filters are the group, the cavern, the decision maker (for example
  `promptA`), and the result. The address of the page keeps the filters.
  Thus a reload or a link shows the same runs.
- There are three types of group:
  - **Saved example runs**: complete runs in the folder `demo/`. The page
    shows this group first.
  - **Your live runs**: the runs that you start (folder `runs/`).
  - **Measurement: name**: the runs of one measurement (folder
    `runs/name/`). A failed run shows where and why jev failed.
- **Totals for each cavern** has one row for each cavern and one column for
  each decision maker. A cell gives the complete runs, all runs, and the mean
  number of keys. The totals use only the group filter. Click a cell to show
  those runs.
- The list of runs gives the result, the keys, the decisions, the cost, and
  the settings of each run. Click a column title to sort the list. Click a
  run to watch it. To compare two runs, tick them and click **Compare 2
  runs**.

#### Watch

The page Watch (`/watch?file=...`) shows one run. The game screen is on the
left. The controls, the statistics, and the timeline are below the game
screen. The data of jev is on the right.

- The timeline has one column for each move decision. The colour of a column
  is the selected move. The height is the confidence. The marks:
  - a red column: Willy died;
  - a green dot: Willy collected a key;
  - a yellow diamond: a key decision;
  - a grey line: Willy was at this place before. A series of grey lines shows
    that Willy goes back and forth.
- In a replay, the page gets all decisions from the log file first. Thus the
  timeline is complete at the start. Click the timeline, or drag along it, to
  go to a decision. The server plays the run up to that decision with no
  delay, and the game stops there. In a live run, a click on the timeline
  shows an earlier decision.
- The controls are **Back**, **Pause**, **Step**, **Stop**, and **Speed**.
  The game stops after a decision and before its move. Thus you see the
  selection of jev before the move occurs. A pause starts at the next
  decision. The line above the game tells when the game stops.
- The keys: Space pauses or resumes. The right arrow runs one move. The left
  arrow goes back one decision (a replay only). F sets full screen.
- **possible moves**: during a pause, the game screen shows the path of Willy
  for each of the 6 macros. Each path is a line of faded figures of Willy in
  the colour of the macro, one figure for each 2 game ticks. The selected
  macro is the brightest, and it has the mark ▶. A red cross marks a move
  that kills Willy. Each label goes to a free place near the end of its path.
  The paths are for the viewer only. They do not go to jev or to the log
  file.

The two tabs on the right show all data that goes to jev:

- **Move decision**: the probability of each macro, the selected macro, and
  the confidence. Each macro that jev did not get, with the cause. The time
  of the jev call and the input tokens. The state and the move question.
- **Key decision**: the key or switch that jev selected as the target (a
  yellow box in the game), and the probability of each key. The state (with
  the map as rows) and the key question.

![The tab Key decision: the probabilities, the legend, and the map that jev got](docs/screenshots/watch-key-decision.jpg)

The page shows each field of a state with its value, so that a person can
read it. The exact JSON is below it. A question shows its instructions as a
paragraph and its options, with the exact JSON below them.

#### Compare

The page Compare (`/compare?a=...&b=...`) shows two recorded runs, A and B.

![The page Compare: promptA and promptB in Central Cavern](docs/screenshots/compare.jpg)

- The result, the keys, and the settings of each run.
- The differences between the runs: the settings, the questions, and the
  first decision where jev got a different state or selected a different
  move. For that decision, the page gives the probabilities of the two moves.
- The path of Willy on the cavern for each run, with the collected keys and
  the place of a death.
- The two timelines, and a table with the decisions of the two runs side by
  side. Click a move to watch that decision in its run.

#### Experiment

On the page Experiment (`/experiment`), select the cavern, the instruction
set, and the map setting at the top. Then you can do one of two things.

![The page Experiment: the key decision lab in The Cold Room](docs/screenshots/experiment.jpg)

- **Ask jev: which key next?** asks the key question of a live run for a
  situation that you set up. This is the key decision lab. One question is
  one jev call (approximately $0.0001).
  - Click a key to mark it as collected. Click a different place to put
    Willy there.
  - The page shows the probabilities, the state with the map, the question,
    and the next key of the optimum order for comparison.
  - In the tab **Key text**, you can change the instruction text and see how
    the answer changes. The page does not save the change.
  - Limits: the cavern is in its start condition, and jev has no memory of
    earlier decisions.
- **Start a live run…** opens the settings that only a live run uses. One
  run costs approximately $0.005.
  - Who selects the next key: jev, or a fixed order. The fixed order starts
    with the optimum order of the cavern.
  - The depth of the dead end check. The default is 4 moves.
  - The run starts on the page Watch. A reload of that page replays the run.
    It does not start a second live run.

**Read or write sets →** opens the page Instruction sets (`/instructions`).

![The page Instruction sets: promptA compared with promptB](docs/screenshots/instruction-sets.jpg)

- The page shows the 3 texts of each set: the move question (`move.txt`),
  the key question with the map (`key.txt`), and the key question with the
  facts only (`key_facts_only.txt`). It also gives the word count and the
  options of the question.
- **Compare with** shows a second set on the right, as the one paragraph that
  jev gets. **mark the differences** gives a colour to the words that are
  only in one of the two texts.
- The sets `promptA`, `promptB`, and `promptC` are fixed, because the results
  in this document come from them. You cannot change a fixed set. **Copy as a
  new set** makes a copy that you can change.
- **Save as a new set** writes a new folder in `jevmanic/instructions/`. Then
  the live run, the lab, the terminal, and the measurement can use the new set
  (`--instructions NAME`). Measure a new set before you use it (see
  "Measurement").
- If you try to leave the page with a change that is not saved, the browser
  asks you first.

### The terminal

```sh
uv run python -m jevmanic.cli --cavern 2
uv run python -m jevmanic.cli --cavern 2 --until-complete
uv run python -m jevmanic.cli --cavern 2 --instructions promptB   # comparison only
uv run python -m jevmanic.cli --help                      # all options
```

The cavern number starts at 1. With `--until-complete`, the script plays
again until a run is complete (10 runs at most). Each live run writes a log
file in `runs/`. The viewer can replay it.

### Measurement

```sh
uv run python -m experiments.measure --caverns 1,2 --runs 10 --label my-test
uv run python -m experiments.measure --caverns 1,2 --runs 10 --label rules --instructions promptB
uv run python -m experiments.diagnose runs/my-test/<file>.jsonl
```

`experiments/measure.py` plays many live games at the same time. Then it
prints a table with the complete runs, the keys, the decisions, the tokens,
and the rate of decisions with a confidence below 0.5. The terminal and the
measurement have the same 6 run options. Each option changes one part of the
design, so that we can measure the effect of that part:

| Option | Effect |
| --- | --- |
| `--instructions NAME` | the instruction set: `promptA` (default) or `promptB` (comparison) |
| `--facts-only-keys` | the key decision gets the facts only, and no map |
| `--key-every N` | repeat the key decision after N decisions (default 25, 0 = no repeat) |
| `--depth N` | the moves that the dead end check looks ahead (default 4, 0 = off) |
| `--key-order LETTERS` | the code sets the key order, and there is no key request. `optimum` gives the optimum order of the cavern (`jevmanic/key_orders.py`). |
| `--random-moves` | a base for comparison: a random choice from the valid moves |

The log files go to `runs/<label>/`. The viewer shows them as the group
"Measurement: label". `experiments/diagnose.py` prints the map, the last
positions, and the last state of one run. The summaries of the measurements
in this document are in `experiments/results/`. Some of them used options
that we removed, because those options gave no gain.

## How it works

Each decision has these steps:

1. The code reads the game data from the emulator memory: Willy, the
   guardians (horizontal and vertical), the keys, the switches, the portal,
   the tiles, and the air.
2. Look-ahead: the code tries each of the 6 macros in the emulator, and then
   puts the game back. This gives the true result of each macro.
3. The code makes the state: a JSON object with words and small numbers.
4. Jev gets the state and the questions in one request. A Choice question
   selects the macro.
5. The emulator runs the macro. Then the next decision starts.

The 6 macros are `walk_left`, `walk_right` (1 cell), `jump_left`,
`jump_right`, `jump_up`, and `wait`. A macro ends when Willy is on the ground
and in line with the cell grid.

A conveyor moves Willy. In the game, Willy stands still on a conveyor only
if the opposite direction is held when he drops onto it, and only while it
is held. After a jump in the direction of the conveyor, or after one tick
with no key, Willy cannot stop again. The macros use this. A fall onto a
conveyor holds against it, and `wait` on a conveyor holds against it ("do
not move"). A walk in the direction of the conveyor lets the conveyor move
Willy.

A second request is less frequent: jev selects the target. The target is a
key, or a switch in the two caverns that have switches. The code sends this
request at the start, after each collected key, and again after 25
decisions.

### Valid moves

Jev gets only the valid moves. A move is not valid in three cases:

1. The move kills Willy.
2. The move is a dead end: Willy is alive after it, but then he cannot avoid
   a death. To find a dead end, the code looks for one sequence of 4 macros
   that keeps Willy alive. If there is no such sequence, the move is a dead
   end. Example: a guardian follows Willy 1 cell behind him toward a wall.
   Each step is safe, but after 5 steps no move is safe. This check asks only
   "can Willy stay alive?". It does not look at keys or at the portal, and it
   does not select a move. Of all parts of the design, this check is the
   nearest to a search.
3. The move has no effect: Willy stays in the same place. `wait` is valid
   only when something can change: a guardian is near, or Willy is on a
   crumbling floor or on a conveyor.

If no valid move is left, jev gets the best moves that remain, in this
sequence: the moves with no effect, then the dead end moves (with a
warning), and then all moves. The first version of this filter had an error:
it gave jev all 6 moves too early. The first measurement used that version.

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
instructions is in `jevmanic/instructions/`. The code that makes the state is
in `jevmanic/describe.py`. The viewer shows the exact state and questions of
each request.

### Request 1: the key decision

Jev gets this request at the start, when Willy collects a key, and again
after 25 decisions. The state has the map of the cavern with its legend. It
also has one entry with facts for each key that is left, and for each switch
that is not flipped. This example shows 2 of the keys and 3 legend entries:

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

On the map, each key has its own letter, and it keeps that letter for the
full run. A conveyor is `<` or `>`: the direction in which it moves Willy.
The legend tells what each symbol means for Willy.

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

The answer in the example is `key_D`, with a confidence of 0.47. This request
used 1638 input tokens.

A test showed that the text must name the map. When the state has the map
and the text does not name it, jev selects the same key as with no map.

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
| `guardians` | the position of each horizontal guardian relative to Willy, and its direction. For a guardian on the level of Willy: is Willy in its patrol area, and where the patrol area ends. The code can also give facts about vertical guardians, but they are off, because they made the results worse. |
| `air` | plenty, low, or critical |
| `progress_measures` | the place that `progress` measures the distance to: the target (same level), the way up (higher floor), or the way down (lower floor) |
| `moves` | the true result of each valid macro, from the look-ahead |
| `moves.*.movement` | where Willy is after the macro |
| `moves.*.progress` | nearer, farther, or same |
| `moves.*.place` | new place, visited before, or visited many times (memory) |
| `moves.*.tried_from_here` | did Willy select this macro at this place before (memory) |
| `moves.*.ends_on`, `collects_key`, `completes_cavern`, `warning` | only when they apply. `ends_on` and `willy.standing_on` give the condition of a crumbling floor: new, partly gone, or almost gone. The code reads it from the pixels of the tile. |
| `moves_not_offered` | each macro that jev does not get, with the cause: it kills Willy (guardian, nasty, fall, or dead end), or it has no effect |

The request has 4 questions. Only the first question controls Willy.

The question `move` is a Choice. The options are the valid macros. The
instructions:

> Willy is a miner in a platform game. The goal: Willy must collect all keys, then go into the exit portal, and he must stay alive. The target is the key that Willy goes to now, or the portal when no key is left. Select the move that is the best for Willy now. `moves` gives the true result of each possible move. All moves in `moves` are safe and have an effect. `moves_not_offered` gives the moves that Willy cannot make now, with the cause. The meaning of the facts: `progress` tells if a move gets Willy nearer to the place that `progress_measures` names. `place` tells how frequently Willy was at the place where the move ends. `tried_from_here` tells if Willy made this move from this place before. `collects_key` tells that Willy gets a key with this move. `completes_cavern` tells that Willy goes into the portal with this move and the cavern is complete. `ends_on` tells that Willy stands on a crumbling floor after this move, and how much of that floor is left. `warning` tells that no move is safe after this move. Knowledge of the game: Willy can climb only 2 rows with one jump. If Willy comes back to the same places again and again, the direct way is closed, and he must go a different way, also if that way goes away from the target first. A crumbling floor breaks a little each time Willy stands on it. It can be the only way up, and it is also a way down. A nasty does not move: if it stops a jump, a jump from a different cell can go over it. A guardian moves along its patrol area: Willy can wait for it to go away, jump over it, or go out of its patrol area.

The criteria of the options:

- `jump_right`: Jump to the right. The result is in `moves.jump_right`.
- `jump_left`: Jump to the left. The result is in `moves.jump_left`.
- `walk_right`: Walk 1 cell to the right. The result is in `moves.walk_right`.
- `walk_left`: Walk 1 cell to the left. The result is in `moves.walk_left`.
- `jump_up`: Jump straight up. The result is in `moves.jump_up`.
- `wait`: Do not move. The result is in `moves.wait`.

The answer in the example is `walk_right`, with a confidence of 0.64. The
probabilities are `walk_right` 0.74, `walk_left` 0.11, `jump_left` 0.08, and
`wait` 0.07. This request used 1524 input tokens and took 288 ms.

The code makes no jev call when only one macro is valid. It also makes no
call when all valid macros have the same result (Willy is in the air).

## What we learned about jev

### Give jev the goal and the meaning of each fact

In Central Cavern, the state said that `jump_left` had `collects_key: true`,
and jev selected `walk_left` (0.51 against 0.44). The instructions did not
say that Willy must collect keys. They also did not say what `collects_key`
means. We added the goal and the meaning to the text, with no rule about
what to select. Then the cavern went from 3 of 10 to 10 of 10 complete runs.
A run needed 74 decisions. Our procedure in promptB needs 70.

### The dead end check gives much help

Complete runs of 10, with the configuration of that time:

| Moves of the dead end check | Central Cavern | The Cold Room | The Menagerie |
| --- | --- | --- | --- |
| 0 (off) | 6 | 0 | 0 |
| 1 | 7 | 1 | 0 |
| 2 | 10 | 4 | 1 |
| 4 | - | - | 6 |
| 6 | - | - | 9 |
| 8 | - | - | 9 |
| 12 (the default of that time) | 10 | 4 | 10 |

A second measurement of Central Cavern with the present code, 20 runs each,
gave 7 of 20 with the check off, 9 with 1 move, 17 with 2 moves, and 20 with
4 moves. All 26 deaths are at one place. Willy lands on the conveyor behind
the guardian, the conveyor moves him, and the guardian turns. With the check
off, Willy is still alive at the end of each move that jev gets, because the
look-ahead of 1 move removes each move that kills him directly.

The default is now 4 moves. It is sufficient for Central Cavern, and it is a
smaller help from the code than 12 moves. The results in this document
before this change used 12 moves. 20 runs each, with the present code:

| Moves of the dead end check | Central Cavern | The Cold Room | The Menagerie |
| --- | --- | --- | --- |
| 4 (the default) | 19 to 20 | 2 | 12 |
| 6 | - | 4 | 15 |
| 12 | 20 | 2 to 3 | 15 to 19 |

With 4 moves, The Menagerie completes fewer runs: 6 of its 8 failed runs are
deaths. Use `--depth 12` to get the earlier results again.

A check of 1 move gives almost no gain. 2 moves are sufficient for Central
Cavern and The Cold Room. The Menagerie needs 6 moves.

In The Menagerie with a check of 2 moves, all 9 deaths are at the same
place. Each death comes after 4 to 6 decisions with no real choice: it is
one trap that is 6 moves deep. The deep check removes the first step into
the trap. Thus the code, and not jev, does a large part of "stay alive".

### A shorter prompt was worse

We wrote the move text again with the same content, in short sentences and
in the form "field: meaning" (190 words, not 293). Central Cavern needed 89
decisions, not 71. The Menagerie went from 10 of 10 to 4 of 10. Jev reads
full sentences better than a short list. We removed the short text.

### One reference from the code can be better than two facts

In cavern 4, the code selects a single tile in a corner as "the way up".
`progress` points to that tile, and Willy goes into that trap in each run. We
gave jev the way up on the left and on the right as two facts, and
`progress` measured the distance to the target. Cavern 4 got its first
complete run. But Central Cavern went from 10 of 10 to 5 of 10, and The
Menagerie from 10 of 10 to 1 of 10. Thus the one reference that the code
selects is important. We removed the two facts.

### A target that jev can change helped

Jev now gets the target question again when Willy collects a key, lands on a
different floor level, or makes no progress. Jev can keep or change the
target, and each key has a short memory (`decisions_used_for_it`,
`gave_up_on_it`). The Menagerie went from 9 of 10 to 10 of 10, and cavern 4
from 3.5 to 4.0 keys. Jev kept the target in 363 of 421 requests.

### More memory made the results worse

We gave jev the last 4 moves with their results (`recent_moves`,
`came_from`). The movement from left to right and back did not change: 32 %
of the decisions, with and without the memory. But with the memory, jev
selected a move that collects a key in 67 % of the cases. Without it, jev
did this in 89 % of the cases. The Menagerie went from 9 of 10 to 5 of 10.
More text in the state takes weight away from the important facts. We
removed this memory.

The memory facts that stay are not necessary. Central Cavern is 9 of 10 with
no memory facts, and 10 of 10 with them.

### Jev cannot count the cells on an ASCII map

`experiments/probe_gap.py` shows a map row with Willy, N empty cells, and a
nasty. It asks "are there exactly 2 empty cells?". From the map, jev says yes
with 0.61, 0.75, and 0.60 for N = 1, 2, and 3. From a number, jev says yes
with 0.03, 0.91, and 0.03. A jump over a nasty is safe only at exactly 2
cells. Thus the code must give distances as numbers.

### Rules for the facts

- Use clear field names. Jev read `"rows_higher": 0` as "same level" when the
  thing was lower. One clear field is better than two fields.
- Two facts must agree. When "nearer to the portal" said right and "way down"
  said left, Willy went left and right with no end.
- A true fact can cause a loop. We gave the fact "after this move, these
  moves are safe". Then `jump_left` made `jump_right` safe, and `jump_right`
  took Willy back to the same place. We removed the fact.
- Give the cause of a result. With only "this move kills Willy", jev waited
  at a nasty for 30 decisions. The cause (guardian or nasty) tells jev if a
  wait can help.

One move request uses approximately 1400 input tokens. It takes
approximately 300 ms from our computer.

### Designs that we removed

These designs were not better than promptA on caverns 1 to 4:

- one Noul question for each move (1 of 12 complete);
- a question in which jev selects the next platform from the map (1 of 18
  complete);
- a "route mode". The code searched sequences of up to 32 macros to find the
  platforms that Willy can get to. Jev selected one platform, and the code
  walked the path. This mode completed caverns 2 and 3 in 9 and 10 of 10
  runs. But the code walked 3459 macros, and jev selected only 175 single
  moves. Thus the result came from the search, and not from jev.

`experiments/probe_target.py` compares target rules with a free choice.

## Open work

### The key order

The map of the cavern gives jev a better key decision in a test with no
game. `experiments/probe_key_order.py` asks "which key next?" in 13
situations of caverns 1 to 4. The reference is the key order of the complete
recorded runs. The correct next key: facts only 5 of 13, map only 8, map and
facts 12. In Central Cavern, jev selects key E first with the map. That is
the known good order (E, A, C, D, B). With the facts only, jev selects D
first and E last.

In play, with the map in the key decision, Willy has all 5 keys of Central
Cavern at decision 35 to 39. With the facts only, he has them at decision 62
to 66. But the complete runs went from 10 of 10 to 7 of 10. The better key
order is not the cause. In a test, the code sets the key order (option
`--key-order EACDB`, no key request, no change to the movement). This test
gives 10 of 10 with the order E A C D B, and 9 of 10 with the order A C D B
E. We then changed one thing at a time, in Central Cavern, 10 runs each:

| Configuration | Complete | Decisions |
| --- | --- | --- |
| The code sets the order E A C D B (the known good order) | 10 | 80 |
| The code sets the order A C D B E (the order of the facts-only runs) | 9 | 74 |
| Test A: jev selects the key with the map, at the start and at each collected key, with the normal text | 7 | 94 |
| The code sets the targets that jev selected in test A: E, then D, then B | 8 | 109 |

The movement completes the good order with no problem. The text of the key
request is not the cause. The cause is the second key decision. With the
map, jev selects E first, which is correct. After E, jev selects D with a
confidence of 0.86, because D is only 5 cells away and A is 20 cells away.
But Willy can get to the top floor only at its left end, thus A is the
correct next key. To see this, jev must follow the route on the map across
four floors. That is a task of more than one step, and the jev documentation
says that jev is weak at such tasks. With D as the target, the route along
the top floor is different, and 2 or 3 of 10 runs then fail after the keys.

The map has a letter for each key, `<` or `>` for a conveyor, and a legend
that tells what each symbol means for Willy.

In The Cold Room, the order of the keys is the full difference between
promptB (9 of 10) and promptA (4 to 6 of 10). We measured two changes to
the target text, 10 runs each:

| Change to the target text | Cavern 1 | Cavern 2 | Cavern 3 | Cavern 4 | Cavern 16 |
| --- | --- | --- | --- | --- | --- |
| None (the normal text) | 10 | 4 to 6 | 10 | 0, 4.0 keys | 0, 1.7 keys |
| + the meaning of `one_way_trip` | 8 | 0 | 10 | - | - |
| The three target rules of promptB | 7 | 8 | 9 | 0, 0 keys | 0, 2.0 keys |

With the sentence about `one_way_trip`, jev did not select the shaft key too
early. But a different order problem then ended the runs: Willy used the one
crumbling way up two times. The target rules correct the order in cavern 2,
and they make caverns 1 and 4 worse. A good key order needs a plan of the
route. Jev gets facts relative to Willy, and a rule about those facts fits
one cavern but not the next one.

### Measurements of the key decision

- A switch as a target made no difference. In the two Kong Beast caverns (8
  and 12), a switch is a target that jev can select. With and without the
  switch targets, the two caverns are 0 of 10, with the same number of keys
  (0.7 and 0.8 in cavern 8, 0.0 in cavern 12). The runs fail before the
  switches are important.
- A repeated key decision with the map gave no gain in play. Jev gets the key
  decision, with the map, at the start and when Willy collects a key. The
  option `--key-every 25` repeats the key decision after 25 decisions. This
  is now the default. Caverns 1 to 4, complete runs of 10: 7, 0, 7, 0 with no
  repeat, and 9, 2, 6, 0 with the repeat. (The normal configuration gives
  10, 4 to 6, 10, 0.) The key decisions are good. The runs fail in the move
  decisions, because the better key order needs moves that the move facts do
  not support well.
- A key decision before each move gave no gain, at 2 times the cost.
  `--key-every 1`, 20 runs each, caverns 1, 2, 3: 20, 0, 17 (the base: 19, 2,
  12). Jev kept the target in 97 % of 5640 key requests, and the key orders
  did not change.
- The word "optimum" in the key question gave no gain. With the text "Select
  the optimum key or switch for Willy to get next", the results were 20, 4,
  13. We put the earlier text back.
- The optimum key order helps one cavern and makes a different cavern worse.
  The code sets the order (`--key-order optimum`), and jev makes each move
  decision. 20 runs each: Central Cavern 20 (80 decisions, not 100), The
  Cold Room 12 (the base: 2 to 4), The Menagerie 3 (the base: 12 to 17, all
  other runs "stuck: no progress"). In The Cold Room, the optimum order has
  the one-way key C last, and jev selects C third. In The Menagerie, the
  optimum order is a route that the move facts do not support.

### Measurements of the move facts

- Facts about vertical guardians made the results worse. The code reads the
  vertical guardians. The state can give their column, their direction, and
  if their column crosses the level of Willy. Caverns 9 and 18 have 4
  vertical guardians each. Complete runs of 10: 9 and 2 with the facts, 10
  and 8 without them. With the facts, a run needs more decisions (109 and not
  73 in cavern 9), and more decisions have a low confidence. The look-ahead
  already removes each move that a vertical guardian makes deadly. Thus the
  facts add text but no safety. We removed them.
- A correction must be true in each cavern. After the last key of Central
  Cavern, Willy stands on the crumbling floor that is his way down. There,
  `progress` said that a walk toward the portal is nearer. Jev gave the two
  walks almost the same probability (0.45 and 0.44). The walk to the right
  ends in a place with no way out. This was the cause of 4 of 5 failed runs.
  The first correction ("to leave the way down is farther") gave Central
  Cavern 19 of 20, but The Menagerie went to 0 of 20. In The Menagerie,
  Willy must walk along a long crumbling floor to the place above the last
  key, and each cell of that floor is a way down. The correction that is true
  in the two caverns: if Willy stands on a crumbling floor, the way down is
  the safe fall place on that floor that is nearest to the target.
  `way_down` and `progress` use that place. Result: Central Cavern 20 of 20
  and 20 of 20, The Menagerie 17 of 20, The Cold Room 2 of 10 (no change).
- The condition of a crumbling floor did no harm and gave no gain that we
  can measure. The game keeps no counter. It moves the pixels of the tile
  down while Willy stands on it, and one walk across a tile uses
  approximately half of it. The move facts now give the condition as a word.
  20 runs each: Central Cavern 20 (before: 40 of 40), The Cold Room 2
  (before: 3 of 20), The Menagerie 19 (before: 17). We kept it, because it
  is true, and it corrects `ends_on` for a tile that is gone after the move.
  We also gave the condition to the key decision: a symbol `-` on the map
  for a tile that is almost gone, and the condition in `floor_below_key`. The
  key orders did not change (Central Cavern E D B in 20 of 20 runs, The Cold
  Room D E C in 17 of 20), and the results were 20, 2, and 16 of 20. We
  removed it from the key decision.
- A guardian fact for each move made the results worse. With a short dead
  end check, all deaths are at the conveyor of Central Cavern, behind the
  guardian. We gave each move the fact `guardian_after`: where the guardian
  on the level of Willy is after the move, and if it moves toward him.
  Central Cavern, 20 runs: 4 and not 7 with the check off, 14 and not 17
  with 2 moves. The Menagerie with the default check: 7 of 20, not 17 to 19.
  We removed it. Here too, more text in the state took weight away from the
  important facts.
- The conveyor hold is true to the game, but it gave no gain that we can
  measure. Before this change, a conveyor always moved Willy, and `wait` let
  the conveyor move him. Central Cavern, 20 runs: 4 and not 7 with the dead
  end check off, 20 and not 17 with 2 moves, 20 of 20 with the default. The
  Menagerie: 15 of 20. At the deadly place of Central Cavern (the conveyor
  behind the guardian), Willy gets onto the conveyor with a jump, and then no
  key can stop him. Jev can select a drop there (`walk_left`, then Willy
  stands still). But jev selects `jump_left` with 0.54 to 0.57, because the
  state gives no cause to prefer the walk. The dead end check of 2 to 4 moves
  is necessary at this place, and we found no fact that can replace it.

### The spread of the results

10 runs are not sufficient to compare two configurations with near results.
The same configuration (the code sets the order E A C D B in Central Cavern)
gave 10 of 10 in one measurement and 7 of 10 in the next one. A second
example: after a cleanup of the code, Central Cavern gave 6 of 10, and then
19 of 20 with the same code. Thus a difference such as 7 of 10 against 10 of
10 can be chance. This makes some conclusions in this document weaker, for
example "the second key decision is the cause". Large differences, such as
10 of 10 against 1 of 10, are real.

### Other decision makers, for comparison

#### An LLM in the place of jev

The decision maker `jevmanic/llm_brain.py` calls Claude Haiku through the
`claude` command line tool. It gets the same instructions, the same options,
and the same state as jev, with no tools and no project files. One run of
Central Cavern, with the default configuration:

| | jev | Claude Haiku |
| --- | --- | --- |
| Result | complete in 8 to 10 of 10 runs | complete (1 run) |
| Decisions | 70 to 75 | 123 |
| All 5 keys at decision | 37 to 42 | 87 |
| Time for the decisions of one run | 24 seconds | 39 minutes |
| Time for one call | 0.3 seconds | 17.8 seconds |
| Cost of one run | $0.004 | $1.30 |

Haiku collected the first key at decision 13 (jev: 14). Then it went left and
right on a lower platform for approximately 60 decisions before it found the
way up. Haiku reasons before each answer, thus one call is slow. This is one
run only. It shows that an LLM can do the task with the same facts. For each
decision, jev is 100 times quicker and 300 times cheaper. Command:
`uv run python -m jevmanic.cli --cavern 1 --llm haiku`.

#### A reasoning model as the planner, and jev as the player

A new subagent (a reasoning model) got only the map, the legend, the guardian
limits, and the game mechanics. It gave a key order for caverns 1 to 4, with
reasons. An example of a reason: "the top floor can only be reached from the
far left, and E is on the only way up". For Central Cavern, it gave E A C D
B, the known good order. For The Cold Room, it gave the most frequent order
of our complete runs. We used only its key order (option `--key-order`), and
jev made each move decision. Complete runs of 10, caverns 1 to 4: 7, 6, 9, 0.
The default gives 8 to 10, 4 to 6, 10, 0. The runs need fewer decisions (The
Cold Room 76, not 95 to 122; The Menagerie 54, not 66), but no more runs are
complete. The full record (the input, the answer with the reasons and the
route plans, and the measurement) is in
[docs/planner-subagent.md](docs/planner-subagent.md).

#### Laya in the place of jev

[Laya](https://github.com/mizorewww/laya-mlx) is a typed decision model
(421M parameters). It runs on an Apple Silicon computer with MLX. Its
request has the same form as a jev request (`--laya`, install with
`uv sync --extra laya`). One request takes approximately 50 ms, with no
network call and no cost. The answers are deterministic, thus 10 runs are
the same as one run. Laya follows the facts, but it completes no cavern.

- The same request as jev (promptA, the JSON state) gave 0 of 30 runs, and no
  key. The probabilities are almost equal. Laya reads only 256 tokens of the
  instructions and the options together, and it cuts the rest with no
  message. The 6 move options use 130 tokens, and promptA has 402 tokens. The
  full input has 1024 tokens at most. `LayaBrain.cut_report()` gives the
  text that Laya cut.
- We measured what Laya can read on the 261 recorded decisions of three
  complete jev runs. The question was "does Laya select a move whose
  `progress` is nearer?". With nested JSON: 26 to 41 of 62. With one short
  sentence for each option ("walk_right is nearer."): 56 of 62. A longer
  instruction, a condition ("if there is none, select…"), or a second fact
  in each sentence made the result worse. Laya prefers the first option. The
  mean of the probabilities for 6 different option orders removes this
  effect (215 of 226; jev has 85 %). One yes or no question for each move was
  worse.
- The form that we use for Laya is in `jevmanic/laya_brain.py`, with
  `--instructions promptC --key-order optimum`. Each move has the text
  "jump_right is nearer and new.". The options are the names with no text.
  The instruction is "Select the move that is nearer. A move that collects a
  key is the best.". The answer is the mean of 6 orders. The key decision
  does not work (Laya selects the first key), thus the code sets the key
  order.
- In real games, Laya got 4 of 5 keys in The Cold Room, and no key in
  caverns 1, 3, 4, 9, and 18. No cavern is complete. Laya follows `progress`,
  but it cannot compare `progress` with the loop facts. Thus Willy walks the
  same path again and again.
- The other checkpoints are not better. The checkpoint that we use
  (`laya-typed-decisions`) is a ModernBERT-large encoder, trained for four
  business tasks. The general checkpoint (`laya`) and the multilingual
  checkpoint select a "nearer" move in 198 and 130 of 226 decisions. The
  checkpoint that we use selects it in 212. `RLAgent` in the package is only
  a second name for `Agent`, and the package has no training code. The model
  is an encoder that matches the words of the question with the words of the
  options. It does not compare two facts. A model of this type must be
  trained on this task to do more.
- The Snake demo of Laya uses a different method. Its code finds the best
  move with a planner, and writes "Safe. Best route to food." into the text
  of that option. The model then matches the word "best". That is against
  the rule of this project, thus we did not do it.

#### A local LLM with the answer read from its logits

Two open projects, [jevfire](https://github.com/kikoncuo/jevfire) and
[SemIf](https://github.com/TheoLeeCJ/SemIf), copy the jev interface with an
open LLM. The model gets the state and the question in one chat prompt, and
each option has a one-letter label. The code reads the probability of each
label at the first output position. One forward pass is one decision, with
no text generation. `jevmanic/local_brain.py` does this with `mlx-lm` on this
computer (`--local`, install with `uv sync --extra local`). The model gets
the same instructions, options, and JSON state as jev. Qwen3-8B in 4-bit
form takes approximately 1.2 s for one decision, with no cost.

- On the 261 recorded jev decisions, Qwen3-4B selects a "nearer" move in 210
  of 226 (jev: 85 %), the key move in 16 of 16, and the same move as jev in
  157 of 261. Qwen3-4B reads the full request, but Laya does not.
- In real games, one run each (the model is deterministic), Qwen3-4B got 1,
  2, and 0 keys in caverns 1, 2, and 3. Qwen3-8B got 0 and 2 keys, and it
  completed The Menagerie in 64 decisions (jev: approximately 80).
- The model is very sure (1.0 against 0.0). Thus, when it makes a loop, it
  repeats the loop until the run ends. Jev gives probabilities that are not
  0 or 1, and its answers change, thus it gets out of a loop. A temperature
  with a sampled answer (`LOCAL_TEMPERATURE=2`, 2 runs each) gave Central
  Cavern 3.5 keys, The Cold Room 1.5, and The Menagerie 2, with no complete
  run. A temperature of 4 was worse. A temperature of 1.5 gave Central
  Cavern 4.5 keys, The Cold Room complete in 1 of 2 runs (55 decisions), and
  The Menagerie 2 keys. The probabilities of jev are calibrated. A flat
  distribution does not give the same result.

### Other open items

- The depth of the dead end check (see the tables above). The options are to
  keep 12, to use a smaller depth, or to replace the search with experience
  (a memory of the places where Willy died in earlier runs).
- Cavern 4: each run ends in a trap in the top left corner, because the code
  selects a single tile as "the way up".
- The saved game states had an error, which is now corrected. The dead end
  check and the start states of the caverns used the same emulator slots. A
  live run wrote over the start state of caverns 1 to 5. This had an effect
  only when one process played more than one run (the viewer, and
  `--until-complete`). The measurements were correct, because each measured
  run has a new emulator. A test now checks the slots.

## Limits

- The code reads the vertical guardians, Eugene, and the switches. The state
  has no facts about vertical guardians, because they made the results
  worse. We did not measure the switch facts. The column and the rows of
  Eugene are an assumption.
- The state has no facts about the Kong Beast, the Skylabs, and the light
  beam of cavern 19. The look-ahead still removes a move that they make
  deadly, because the look-ahead runs the real game.
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
| `jevmanic/brain.py` | the questions and the jev calls |
| `jevmanic/instructions/` | the instruction sets: `promptA/`, `promptB/`, `promptC/`, and your own folders |
| `jevmanic/llm_brain.py` | an LLM as the decision maker, for comparison |
| `jevmanic/laya_brain.py` | Laya, a local typed decision model, as the decision maker, for comparison |
| `jevmanic/local_brain.py` | a local LLM as the decision maker, with the answer read from its logits, for comparison |
| `jevmanic/runner.py` | the settings, the live run, the log file, and the replay |
| `jevmanic/options.py` | the run options of the terminal and the measurement |
| `jevmanic/server.py`, `jevmanic/web/` | the viewer |
| `jevmanic/lab.py` | the key decision lab of the viewer |
| `jevmanic/key_orders.py` | the optimum key order of each cavern |
| `jevmanic/cli.py` | a live run in the terminal |
| `experiments/` | measurement, diagnosis, and tests of how well jev reads a state |
| `experiments/results/` | the summaries of the measurements in this document |
| `docs/planner-subagent.md` | the test with a reasoning model as the planner |
| `docs/screenshots/` | the pictures of the viewer in this document |
| `demo/` | recorded complete runs, in git |
| `runs/` | the log files of your runs (JSON Lines), not in git |

A log file has one header line. Then it has one line for each jev request (a
"target" record, or a "decision" record with its state and answers). The last
line is the end record. The header has the macro version (`macros: 2` = with
the conveyor hold). A log file with no version replays with the old macros.
Older log files and measurement labels use the names "free mode" for promptA
and "rules mode" for promptB.

The emulator core comes from the esp32-zxspectrum project, which took it from
[OpenVegaPlus](https://github.com/alvaroalea/OpenVegaPlus).
