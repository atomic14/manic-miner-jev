# jev plays Manic Miner

Manic Miner is a platform game for the ZX Spectrum computer (1983). In each
of its 20 caverns, Miner Willy must collect all keys and then go into the
exit portal. He must not touch an enemy, fall too far, or use up his air.

[Jev](https://docs.typesafe.ai/introduction) is a decision model from
TypeSafe. Jev does not write text. It gets a state (a JSON object) and a
typed question, for example a Choice between a set of options. It gives a
probability for each option, and it selects one option. See "Jev" below.

This project asks one question: if the code only describes the game, can jev
make the decisions? The code runs the game in an emulator and tells jev the
facts of each situation. Jev selects each move of Willy, and each key that
Willy goes to next.

## The answer in short: you do not need jev to play this game

We replaced jev with a rule of three lines that uses the same facts. With the
same key order, the rule completes almost as many runs as jev, with no model
and at no cost. 10 runs of each of the 20 caverns, 200 runs for each line:

| Decision maker | Key order | Complete runs | Caverns with a complete run | Mean keys in a run | Cost of 200 runs |
| --- | --- | --- | --- | --- | --- |
| jev | jev selects | 31 of 200 | 5 | 1.4 | $0.91 |
| jev | the optimum order | 26 of 200 | 6 | 1.5 | $0.85 |
| rule `nearer` | the optimum order | 24 of 200 | 4 | 1.3 | $0 |
| jev, without the fact `progress` | jev selects | 5 of 200 | 3 | 1.3 | $0.84 |
| random valid move | the optimum order | 0 of 200 | 0 | 0.3 | $0 |

- The rule `nearer`: select a move that completes the cavern or collects a
  key; else a move whose `progress` is "nearer"; else any valid move.
- With the same key order, jev completes 26 runs and the rule 24. With 10
  runs for each cavern, this difference can be chance.
- Jev selects a move that the rule can also select in 93 % of its decisions.
- Without the fact `progress`, jev completes only 5 runs. The code computes
  `progress` toward the target, the way up, or the way down. Thus the route
  knowledge is in the code, not in jev.
- A random choice from the same valid moves completes 0 runs. Thus the facts
  are important, not only the valid moves.
- The rule needs its random choice. When two moves are "nearer", or none is,
  the rule selects one at random, and this takes Willy out of a loop. The
  same rule with no random choice completes 0 of 20 runs in Central Cavern
  (with the random choice: 17 of 20).
- Jev needs more than `progress`. With `progress` only, jev follows
  "nearer" in each decision, but it goes around in a loop and completes 0 of
  20 runs in Central Cavern. Jev leaves loops with the memory facts (`place`,
  `tried_from_here`), and it finds the portal with the other facts of the
  state and one sentence of the text about loops (see "What jev needs: tests
  in Central Cavern"). A map after each move does not replace `progress`.

The code (the "harness") does most of the work: it removes each move that
kills Willy, and it tells which move goes nearer. The direction from the code
and a random choice to leave loops do almost as well as jev. Jev adds a
little: it does better than the rule in some caverns (Amoebatrons' Revenge 6
or 8 of 10, against 0 of 10 for the rule), and worse in others. This is one
game and one harness. We did not test the game demos of other people. But the
test is easy to repeat for any demo: replace the model with a simple rule on
the same facts, and compare. If the results are near, the harness does the
work.

![A replay of The Cold Room, stopped before decision 37](docs/screenshots/hero.jpg)

The picture shows a replay, stopped before decision 37. On the game screen,
the coloured figures show where each of the 6 moves takes Willy. A red cross
marks a move that kills him. On the right, each bar is the probability that
jev gave to a move. Jev selected `walk_right` (0.62). `jump_up` is not
valid, because it kills Willy.

## Quick start

You need `uv`, `clang++`, and `make`. You do not need an API key to watch the
recorded runs.

```sh
uv sync
uv run make -C emulator                 # build the emulator module
uv run python -m jevmanic.server        # start the viewer
```

Open http://127.0.0.1:8000, and click a run in the list. The page Watch
replays the run: the game, each decision of jev, and all data that jev got. A
replay makes no jev call and costs nothing.

To let jev play a new game (a live run), you need a TypeSafe API key:

```sh
echo "TYPESAFE_API_KEY=your-key" > .env
```

Then click **Experiment** in the viewer, or use the terminal (see "Live
runs and measurements"). One live run costs approximately $0.005.

To run the tests (no jev calls): `uv run pytest`.

## How it works

### The game

| Term | Meaning |
| --- | --- |
| cavern | one level of the game. The caverns have numbers 1 to 20 and names, for example 1 Central Cavern, 2 The Cold Room, 3 The Menagerie. The table in "Result" gives all names. |
| Willy | the miner that the player controls |
| cell | the cavern is a grid of 32 × 16 cells. Willy is 2 cells wide and 2 cells high. |
| key | an item that Willy must collect. A cavern has 1 to 5 keys. This project gives them the letters A to E. |
| switch | a lever in caverns 8 and 12. Willy can flip it to change the cavern. |
| portal | the exit. It opens when Willy has all keys. |
| air | a supply that goes down all the time. When it ends, Willy dies. |
| guardian | an enemy that moves along a fixed path, horizontally or vertically. It kills Willy on contact. |
| nasty | a hazard that does not move, for example a plant. It kills Willy on contact. |
| crumbling floor | a floor that breaks a little each time Willy stands on it, and then is gone |
| conveyor | a floor that moves Willy to the left or to the right |

Willy can walk and jump. One jump gets him at most 2 rows higher. A fall of 5
rows or more kills him.

### One decision

A **macro** is one move of Willy: `walk_left`, `walk_right` (1 cell),
`jump_left`, `jump_right`, `jump_up`, or `wait`. A macro ends when Willy is
on the ground and in line with the cell grid. The code stops the game before
each macro. Then:

1. The code reads the game data from the memory of the emulator: Willy, the
   guardians, the keys, the switches, the portal, the tiles, and the air.
2. **Look-ahead**: the code tries each of the 6 macros in the emulator, and
   then puts the game back. This gives the true result of each macro.
3. The code removes each macro that is not valid (see below).
4. The code makes the state: a JSON object with words and small numbers.
5. Jev gets the state and the question, and it selects one macro. This is a
   **move decision**.
6. The emulator runs the macro. Then the next decision starts.

The **target** is the key that Willy goes to now, or the portal when no key
is left. Jev selects the target in a second, less frequent request: the
**key decision**. Jev gets it at the start, after each collected key or
flipped switch, and again 25 decisions after the last key decision. It has
one option for each key and switch that is left.

A conveyor moves Willy. In the game, Willy stands still on a conveyor only if
the opposite direction is held when he drops onto it, and only while it is
held. The macros use this. A fall onto a conveyor holds against it, and
`wait` on a conveyor holds against it. A walk in the direction of the
conveyor lets the conveyor move Willy.

### Valid moves

Jev gets only the valid moves. A move is not valid in three cases:

1. The move kills Willy.
2. The move goes into a dead end: Willy is alive after it, but then he cannot
   avoid a death. The **dead end check** finds this. It looks for one
   sequence of 4 macros that keeps Willy alive. If there is no such sequence,
   the move goes into a dead end. Example: a guardian follows Willy 1 cell
   behind him toward a wall. Each step is safe, but after 5 steps no move is
   safe. The check asks only "can Willy stay alive?". It does not look at
   keys or at the portal, and it does not select a move.
3. The move has no effect: Willy stays in the same place. `wait` is valid
   only when something can change: a guardian is near, or Willy is on a
   crumbling floor or on a conveyor.

If no valid move is left, jev gets the best moves that remain, in this
sequence: the moves with no effect, then the moves into a dead end (with a
warning), and then all moves.

| The code | Jev |
| --- | --- |
| Reads positions and changes them into facts | Selects the target |
| Tries each macro and gives its true result | Selects each move |
| Does not offer a move that is not valid | |
| Remembers the places and the moves that Willy tried | |

### How a run ends

- **complete**: Willy has all keys and goes into the portal.
- **Willy died**: an enemy, a nasty, a fall, or the end of the air.
- **no progress**: Willy visited no new place and collected no key in 30
  decisions. This rule stops a run that goes nowhere, so that it costs
  nothing more.
- **decision limit**: the run used 400 decisions.

### The rule of this project

The decisions come from jev. The code gives facts and knowledge of the game.
The code does not tell jev what to select. The code also does not offer a
decision that we know is not valid.

An **instruction set** is the text that jev gets with each question. Each set
is a folder in `jevmanic/instructions/<name>/` with three plain text files:
`move.txt`, `key.txt`, and `key_facts_only.txt`. The files have no markup,
because the jev documentation says that jev reads the words as they are. Jev
gets the same state, the same options, and the same schedule of requests with
each set. Thus the text is the only difference between two sets.

- `promptA` is the normal set. It gives the goal, the meaning of each fact,
  and knowledge of the game (for example "a crumbling floor breaks a little
  each time Willy stands on it"). It does not have instructions of the form
  "select X when Y".
- `promptB` is for comparison only. It has rules of the form "select X when
  Y": 7 rules in the move text and 3 rules in the key text. With promptB, jev
  follows a procedure that we wrote. Most of the success of promptB comes from
  that procedure.
- `promptC` is a very short text for Laya, a different decision model (see
  [docs/findings.md](docs/findings.md)).
- `promptA-no-progress` is promptA without the sentence about `progress` and
  `progress_measures`, for the test without that fact.
- `promptD` is promptA with correct statements about the moves in `moves`.
  PromptA says that each move in `moves` is safe and has an effect. That is
  not always true: `wait` stays when something can change while Willy waits,
  and a move after which Willy cannot stay alive stays when no move is safe.
- `promptD-plain` and the three sets `promptM-...` are the texts for the
  tests in Central Cavern (see "Result"). Each text names only the fields
  that its state has.

### Jev

TypeSafe published jev in September 2026
([the announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev)).
The facts in this section come from TypeSafe. We did not test them, except
where this document gives a measurement.

- TypeSafe calls jev a "System One model": a model that makes fast,
  structured decisions that software can use directly. It is not a text
  generator: the possible answers and their structure are set before the
  request.
- A request has one or more typed questions. This project uses the type
  **Choice**: jev selects one option from a list. A different type, **Noul**,
  gives the probability that a statement is true.
- Jev gives a probability for each option. TypeSafe says that these
  probabilities are calibrated, and that it trains jev with reinforcement
  learning for this purpose.
- TypeSafe gives a response time of 70 to 500 ms. In the measurement of the
  defaults (15110 move decisions), the median time from our computer was
  268 ms, and 90 % of the decisions took 344 ms or less.
- The price is $0.042 for one million input tokens. The output costs
  nothing. One move decision uses a median of 1358 input tokens.
- This project uses the model version `jev-1.13.0`.

Jev also gives a **confidence** for the
answer. The confidence is not the probability of the selected option. The
jev documentation says that TypeSafe computes the confidence from how the
probability is spread across the options: all probability on one option
gives 1.0, and the more evenly it spreads, the lower the confidence. In the
picture above, `walk_right` has 0.62, and the confidence is 0.52. In a key
decision of the same run, `key_B` has 0.39, `key_E` 0.37, and `key_C` 0.24.
The confidence of that answer is only 0.08.

## Result

Settings for all columns: the key decision uses the map, and the dead end
check looks 4 moves ahead. 10 live runs for each cavern. The columns:

- **jev**: jev selects each move and each key, with promptA.
- **jev, optimum order**: the code sets the key order
  (`--key-order optimum`), and jev selects each move.
- **jev, no `progress`**: the state has no `progress` and no
  `progress_measures`, and the text does not name them (`--no-progress
  --instructions promptA-no-progress`). Jev selects each move and each key.
- **rule `nearer`**: a move that completes the cavern or collects a key; else
  a move whose `progress` is "nearer"; else any valid move
  (`--rule nearer`). The optimum key order. No jev call.
- **rule `nearer-new`**: the same, but first a nearer move to a new place,
  and then a move to a new place (`--rule nearer-new`). The optimum key
  order. No jev call.
- **random**: a random valid move (`--random-moves`). The optimum key order.
  No jev call.

If more than one move passes a test of a rule, the rule selects one of them
at random. Each cell gives the complete runs of 10, then the mean number of
keys in a run.

| Cavern | jev | jev, optimum order | jev, no `progress` | rule `nearer` | rule `nearer-new` | random |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Central Cavern (5 keys) | 10 · 5.0 | 10 · 5.0 | 0 · 4.4 | 10 · 5.0 | 8 · 4.2 | 0 · 0.0 |
| 2 The Cold Room (5 keys) | 1 · 2.3 | 7 · 4.3 | 0 · 1.8 | 7 · 4.0 | 4 · 3.0 | 0 · 0.6 |
| 3 The Menagerie (5 keys) | 8 · 4.7 | 1 · 2.3 | 1 · 2.0 | 5 · 3.1 | 4 · 2.6 | 0 · 0.2 |
| 4 Abandoned Uranium Workings (5 keys) | 0 · 0.0 | 0 · 0.0 | 0 · 2.5 | 0 · 0.0 | 0 · 0.0 | 0 · 0.4 |
| 5 Eugene's Lair (5 keys) | 0 · 2.2 | 0 · 1.9 | 0 · 0.2 | 0 · 2.1 | 0 · 2.4 | 0 · 0.8 |
| 6 Processing Plant (5 keys) | 0 · 2.8 | 0 · 2.7 | 0 · 4.5 | 0 · 0.2 | 0 · 0.0 | 0 · 0.8 |
| 7 The Vat (5 keys) | 0 · 0.0 | 0 · 0.0 | 0 · 1.2 | 0 · 0.0 | 0 · 0.0 | 0 · 0.0 |
| 8 Miner Willy meets the Kong Beast (4 keys) | 0 · 0.4 | 0 · 1.2 | 0 · 0.3 | 0 · 0.4 | 0 · 2.0 | 0 · 0.2 |
| 9 Wacky Amoebatrons (1 key) | 4 · 0.4 | 1 · 0.1 | 2 · 0.2 | 2 · 0.2 | 2 · 0.3 | 0 · 0.0 |
| 10 The Endorian Forest (5 keys) | 0 · 1.0 | 0 · 2.3 | 0 · 0.5 | 0 · 2.2 | 0 · 2.0 | 0 · 0.9 |
| 11 Attack of the Mutant Telephones (5 keys) | 0 · 0.0 | 1 · 2.2 | 0 · 0.0 | 0 · 1.3 | 0 · 1.7 | 0 · 0.0 |
| 12 Return of the Alien Kong Beast (5 keys) | 0 · 1.0 | 0 · 1.0 | 0 · 1.8 | 0 · 0.7 | 0 · 0.7 | 0 · 0.2 |
| 13 Ore Refinery (5 keys) | 0 · 0.9 | 0 · 1.0 | 0 · 0.9 | 0 · 1.0 | 0 · 1.0 | 0 · 0.1 |
| 14 Skylab Landing Bay (4 keys) | 0 · 1.2 | 0 · 0.1 | 0 · 1.2 | 0 · 1.0 | 0 · 1.0 | 0 · 0.2 |
| 15 The Bank (3 keys) | 0 · 1.4 | 0 · 1.6 | 0 · 2.0 | 0 · 1.2 | 0 · 1.0 | 0 · 0.1 |
| 16 The Sixteenth Cavern (4 keys) | 0 · 1.9 | 0 · 2.3 | 0 · 1.4 | 0 · 0.3 | 0 · 0.4 | 0 · 0.0 |
| 17 The Warehouse (5 keys) | 0 · 2.0 | 0 · 0.0 | 0 · 0.0 | 0 · 0.9 | 0 · 1.0 | 0 · 0.0 |
| 18 Amoebatrons' Revenge (1 key) | 8 · 0.8 | 6 · 0.6 | 2 · 0.2 | 0 · 0.0 | 0 · 0.0 | 0 · 0.0 |
| 19 Solar Power Generator (3 keys) | 0 · 0.0 | 0 · 1.0 | 0 · 0.0 | 0 · 0.9 | 0 · 1.0 | 0 · 0.2 |
| 20 The Final Barrier (5 keys) | 0 · 0.2 | 0 · 0.0 | 0 · 1.3 | 0 · 1.8 | 0 · 1.4 | 0 · 0.4 |
| All caverns | 31 · 1.4 | 26 · 1.5 | 5 · 1.3 | 24 · 1.3 | 18 · 1.3 | 0 · 0.3 |

What this shows:

- A random choice from the valid moves completes no cavern. Thus the choice
  between the valid moves is important.
- The rule `nearer` does almost as well as jev. The rule `nearer-new`, which
  also prefers new places, does worse (18 complete runs). Thus the fact
  `progress` alone is a strong guide.
- The key order changes the result of each cavern in a different way. With
  the optimum order, jev completes The Cold Room in 7 of 10 runs (with its own
  keys: 1), but The Menagerie in 1 of 10 (with its own keys: 8).
- Without `progress`, jev collects almost as many keys (1.3 in a run), but it
  completes only 5 runs. For example, in Central Cavern it collected all 5
  keys in 7 of 10 runs. Then it did not find the way down to the portal, and
  the runs ended with no progress.
- In caverns 4, 7, and 11, jev with the default settings collected no key.
- In cavern 20, 9 of 10 runs of jev end with a death at decision 10. Before
  the death, only one move is valid for two decisions, and then each move
  kills Willy. A dead end check of 4 moves does not find this trap early
  enough. The default is 4 moves, and not 12, because a deeper check does
  more of the work for jev (see "The dead end check" in
  [docs/findings.md](docs/findings.md)).
- One run of "jev, no `progress`" ended with a server error of the jev API.

Some caverns got better results with different settings: the key decision with
the facts only, and a dead end check of 12 moves. Cavern 9 completed 10 of 10
runs (with the defaults: 4), cavern 11 completed 5 of 10 (with the defaults:
0), and cavern 4 collected 4.0 keys (with the defaults: 0.0). We did not
measure which of the two settings causes the difference. See "Open work" in
[docs/findings.md](docs/findings.md).

### What jev needs: tests in Central Cavern

These tests change one thing at a time, in Central Cavern, with 20 runs each.
The key decision is the same in each test. The measurement of today's
defaults gave 20 of 20 on the same day. The goal facts are `collects_key` and
`completes_cavern`. The memory facts are `place` and `tried_from_here`. Each
test has its own text, which explains only the fields of its state (the text
sets `promptD-plain` and `promptM-...`).

**The direction of each move.**

| Test | Complete runs | Mean keys |
| --- | --- | --- |
| The full state, with the text `promptD` (see below) | 18 of 20 | 4.5 |
| Plain distances in place of `progress` (`--progress plain`) | 0 of 20 | 1.7 |
| The rule `plain` on the plain distances (no jev call) | 0 of 20 | 0.3 |
| The rule `nearer` (no jev call) | 17 of 20 | 4.6 |
| The rule `nearer` with no random choice (`--rule nearer-fixed`) | 0 of 20 | 0.0 |

**Fewer facts** (`--move-facts NAME`).

| Test | Complete runs | Mean keys | Decisions |
| --- | --- | --- | --- |
| Only `progress` | 0 of 20 | 0.0 | - |
| `progress` and the goal facts | 0 of 20 | 0.9 | - |
| `progress`, the goal facts, and the memory facts | 2 of 20 | 5.0 | - |
| The same, and `target` | 0 of 20 | 5.0 | - |
| The same, and `to_the_left`, `to_the_right` | 0 of 20 | 4.6 | - |
| The same, and the result of each move (`movement`, `ends_on`, `warning`, `moves_not_offered`) | 1 of 20 | 5.0 | 79 |
| The full state without `guardians` and `air`, with the full text | 20 of 20 | 5.0 | 75 |
| The same state, with a text that explains the fields and has no knowledge of the game | 0 of 20 | 5.0 | - |
| The same, and only the sentence about crumbling floors | 0 of 20 | 5.0 | - |
| The same, and only the sentence about loops | 20 of 20 | 5.0 | 73 |
| `progress`, the goal facts, the memory facts, and only the sentence about loops | 0 of 20 | 0.0 | - |

**A map after each move** (`--move-facts maps`). Each valid move gets the map
of the cavern at the end of the move, from the snapshot that the look-ahead
makes: Willy, the guardians, the keys that are left, and the condition of each
crumbling tile. The state also names the target key, and it has the goal and
memory facts, and the sentence about loops.

| Test | Complete runs | Mean keys | Decisions | Confidence below 0.5 |
| --- | --- | --- | --- | --- |
| The maps, no `progress` | 1 of 20 | 1.1 | 137 | 85 % |
| The maps and `progress` | 11 of 20 | 3.2 | 118 | 75 % |
| For comparison: no guardians, the sentence about loops | 20 of 20 | 5.0 | 73 | 21 % |

What these tests show:

- `progress` is not a plain measurement. It has two rules of the code: a
  move that uses the way up or the way down is "nearer", and a move that
  leaves the level of the target is "farther". Plain distances have no such
  rules, and they mislead: a jump onto a higher platform often ends past the
  way up, and then its plain distance is "farther". With plain distances,
  jev and the rule complete no run. Thus the route knowledge is in the two
  rules of `progress`.
- With `progress` only, jev follows "nearer" in each decision, and it goes
  around in a loop. The rule with no random choice does the same. The random
  choice of the rule, or the memory facts for jev, take Willy out of a loop.
- One sentence of the text decides the result in this cavern: "If Willy
  comes back to the same places again and again, the direct way is closed,
  and he must go a different way, also if that way goes away from the target
  first." Without it, jev collects all keys but does not find the way down to
  the portal (0 of 20). With it, 20 of 20. The other knowledge of the game in
  the text is not necessary here. This sentence is near to the limit of the
  rule of this project: it tells jev when it can leave "nearer".
- The sentence about loops needs the other facts. With only `progress`, the
  goal facts, and the memory facts, it makes the result worse (0 keys).
- The facts about the guardians are not necessary in this cavern. Without
  them, jev completes each run with 75 decisions in place of 107. The
  look-ahead already removes each move that a guardian makes deadly. We did
  not test this in the other caverns.
- A map after each move does not replace `progress`. Without `progress`,
  jev does not find the route in the maps (1 of 20). With `progress`, the
  maps make the result worse than the compact facts (11 of 20, against 20 of
  20). With the maps, jev is uncertain: 75 % to 85 % of its decisions have a
  confidence below 0.5. A route over several floors is a task of several
  steps, and jev does not do it from a map.
- The text `promptD` is promptA with correct statements about the moves in
  `moves` (see "The rule of this project"). It gave 18 of 20, against 20 of
  20 for promptA. This difference can be chance.

### What the measurements show

- Jev makes good single decisions, but it does not plan a route. When a move
  goes nearer to the target, jev selects such a move in 85 % of the
  decisions. Jev fails when the direct way is closed and Willy must first go
  away from the target. Jev also uses crumbling floors that Willy needs
  later.
- The look-ahead removes each move that kills Willy directly. A death comes
  from a trap that is deeper than the dead end check, as in cavern 20.
- Jev does not always give the same answer for the same state. When two
  options are near (for example 0.47 and 0.44), two runs go different ways.
  Thus 10 runs for each cavern show only large differences.
- A key decision with a good order needs a plan of the route on the map. Jev
  is weak at tasks of more than one step.

[docs/findings.md](docs/findings.md) gives each measurement behind these
statements, with its settings.

### PromptB compared with promptA

We wrote the rules of promptB with caverns 1 and 2. The Menagerie (cavern 3)
is a fair test, because we did not use it to write a rule. The two sets got
the same code and the same settings (the key decision with the map, and a
dead end check of 4 moves). 20 runs each:

| Cavern | promptA: complete runs of 20 | promptB: complete runs of 20 |
| --- | --- | --- |
| 1 Central Cavern (rules written with it) | 19 to 20 | 20 |
| 2 The Cold Room (rules written with it) | 2 to 4 | 19 |
| 3 The Menagerie (fair test) | 12 to 17 | 2 |

"19 to 20" means that two or more measurements gave 19 or 20. In The Cold
Room, rule 1 of the key text puts the key in the shaft last. The rules are
better on the caverns that we used to write them, and much worse on The
Menagerie. Thus promptA is the normal set. A rule can be a correct change to
a prompt, but the rule must be general, and we must measure it on caverns
that we did not use to write it.

### Other decision makers

We also gave the task to other models. Each got the same instructions,
options, and state as jev. These are small tests, with the settings of their
time and few runs. They show the character of each model, not an exact
ranking. [docs/findings.md](docs/findings.md) gives the details.

| Decision maker | What it is | Test | Result | One decision | One run |
| --- | --- | --- | --- | --- | --- |
| jev (`jev-1.13.0`) | System One model from TypeSafe, through its API | 10 runs of each cavern (see "Result") | 31 of 200 complete | 0.27 s | $0.005 |
| Claude Haiku | an LLM that reasons before each answer, through the `claude` command | 1 run of Central Cavern | complete, in 123 decisions (jev: 70 to 75) | 17.8 s | $1.30 |
| Qwen3-8B, 4-bit | an open LLM on this computer; the code reads the answer from its logits | 1 run of each of caverns 1 to 3 | The Menagerie complete (64 decisions); 0 and 2 keys in caverns 1 and 2 | 1.2 s | $0 |
| Laya | a small typed decision model (421 million parameters) on this computer | 10 runs of each of caverns 1 to 3 with the jev request | no complete run; it cannot read the full request | 0.05 s | $0 |
| A reasoning model as the planner, jev as the player | the planner gives the key order, and jev selects each move | 10 runs of each of caverns 1 to 4 | 7, 6, 9, 0 complete (jev alone: 8 to 10, 4 to 6, 10, 0) | - | - |

Claude Haiku can also complete a cavern with the same facts, but it is much
slower and more expensive. The local models are very sure of each answer
(1.0 against 0.0), thus they repeat a loop until the run ends. A good key
order from the planner did not give more complete runs.

## Questions and criticisms

These are the questions that people ask about game demos with jev, and our
answers from the measurements in this project.

**Does the code do the work, and not jev?** Mostly, yes. See "The answer in
short". The code removes each move that kills Willy or goes into a dead end,
and it computes `progress` toward the target, the way up, or the way down.
With the same key order, a rule on these facts completes 24 runs and jev 26.
Without `progress`, jev completes 5. The rule also needs a random choice to
leave loops (see "What jev needs: tests in Central Cavern"). When jev does not
follow the rule (7 % of its decisions), it mostly selects a move that goes
farther, often to a place that Willy visited before.

**Does the state mark the correct answer?** Not directly, but `progress` is
near to a mark. The state does not say which move is the best. But `progress`
has two rules of the code about the way up and the way down, thus it contains
the route. With plain distances in its place, jev completes no run in Central
Cavern. The rule shows what the "nearer" fact alone gives. The code also does
not offer moves that we know are not valid (see "Valid moves").

**Is each decision really from jev?** Each move decision is one jev request,
except when only one move is valid, or when all valid moves have the same
result (Willy is in the air). Then the code makes no jev call, and the log
and the viewer mark the decision "no jev call". The log file of a run has
each request: the state, the question, and the answer.

**Did you select the good runs?** The result tables give all runs of each
measurement. The summaries are in `experiments/results/`. The example runs
in `demo/` are complete runs: they show what jev can do, not what it does
each time. Most runs are not complete.

**Does jev see the game?** No. Jev reads text only. The code reads the game
from the memory of the emulator, and it gives jev facts relative to Willy.
Jev gets no picture.

**Is the time of a jev call a problem?** No. The game stops before each move
and waits for the decision. A move decision takes a median of 268 ms.

**Why not an LLM, a search, or a trained agent?** The question of this
project is what jev can do with facts only. A search or a trained agent can
play better, but then the search or the training makes the decisions. Claude
Haiku completed Central Cavern with the same facts, but one decision took
17.8 s and the run cost $1.30 (see "Other decision makers").

**Does jev give the same answer each time?** Mostly. We asked jev 200
recorded move decisions again, with no change: 184 answers were the same as
before. When two options are near (for example 0.47 and 0.44), the answer
can change, and two runs of the same cavern go different ways. Thus we give
results of 10 or 20 runs, and not of one run.

**Does the order of the options change the answer?** A little. With the
options in a different order, 172 to 174 of the 200 answers were the same as
before (184 with no change). Jev does not prefer the first option: with the
normal order, it selected the first option in 51 of 200 decisions, the same
as by chance. When we also put the facts in `moves` in the reverse order,
only 144 of 200 answers were the same. These changed answers go in no single
direction. The code always gives the moves in the same order.
`experiments/probe_option_order.py` makes this test (approximately $0.05).

**Are the probabilities of jev calibrated?** TypeSafe says that they are. We
did not test this. We only saw that the spread of the jev probabilities
helps: a local model that is always very sure repeats a loop until the run
ends (see "Other decision makers").

**Is jev an LLM?** TypeSafe says that jev is not a language model, because
it does not generate language. It has not published the architecture.

## The viewer

```sh
uv run python -m jevmanic.server
```

Open http://127.0.0.1:8000. The menu of the viewer has three pages:

- **Runs**: all recorded runs, with filters, and the complete runs for each
  cavern. Select two runs to compare them.
- **Watch**: one run. The game, each decision of jev with its probabilities,
  and all data that jev got. Click the timeline to go to a decision.
- **Experiment**: ask jev one key question for a situation that you set up,
  start a live run, or write a new instruction set.

Two more pages open from these pages: **Compare** (from Runs) and
**Instruction sets** (from Experiment). [docs/viewer.md](docs/viewer.md)
describes each page, with pictures.

## Live runs and measurements

A live run needs the API key in `.env` (see "Quick start").

```sh
uv run python -m jevmanic.cli --cavern 2
uv run python -m jevmanic.cli --cavern 2 --until-complete
uv run python -m jevmanic.cli --cavern 2 --instructions promptB   # comparison only
uv run python -m jevmanic.cli --help                      # all options
```

The cavern number is 1 to 20. With `--until-complete`, the script plays again
until a run is complete (10 runs at most). Each live run writes a log file in
`runs/`. The viewer can replay it.

A measurement plays many live runs at the same time and prints a table: the
complete runs, the keys, the decisions, the tokens, and the rate of decisions
with a confidence below 0.5. Jev does not always give the same answer for the
same state. Thus one run tells little, and 10 runs for each cavern show only
large differences.

```sh
uv run python -m experiments.measure --caverns 1,2 --runs 10 --label my-test
uv run python -m experiments.measure --caverns 1,2 --runs 10 --label rules --instructions promptB
uv run python -m experiments.diagnose runs/my-test/<file>.jsonl
```

The terminal and the measurement have the same run options. Each option
changes one part of the design, so that you can measure the effect of that
part:

| Option | Effect |
| --- | --- |
| `--instructions NAME` | the instruction set: `promptA` (default) or `promptB` (comparison) |
| `--facts-only-keys` | the key decision gets the facts only, and no map |
| `--key-every N` | repeat the key decision after N decisions (default 25, 0 = no repeat) |
| `--depth N` | the moves that the dead end check looks ahead (default 4, 0 = off) |
| `--key-order LETTERS` | the code sets the key order, and there is no key decision. `optimum` gives the optimum order of the cavern. |
| `--random-moves` | a random choice from the valid moves, for comparison |
| `--rule NAME` | a simple rule in the place of jev, for comparison (no jev call): `nearer`, `nearer-new`, `nearer-fixed` (no random choice), or `plain` (for `--progress plain`) (see "Result") |
| `--progress route\|plain\|none` | the facts about the direction of each move: `progress` with the two rules of the code (default), plain distances (`to_target`, `to_way_up`, `to_way_down`; use `--instructions promptD-plain`), or none (use `--instructions promptA-no-progress`). `--no-progress` is the same as `--progress none`. |
| `--move-facts NAME` | the move state: `full` (default), or a smaller state for a test: `progress`, `progress-goal`, `progress-goal-memory`, `pgm-target`, `pgm-target-sides`, `pgm-target-sides-result`, `no-guardians`, `maps` (a map after each move), or `maps-progress`. Use the text set `promptM-NAME` (the table `TEXT_STATE` in `jevmanic/checks.py` gives each pair). |

The **optimum order** of each cavern is in `jevmanic/key_orders.py`. It is a
good key order that we use as a reference. The project does not prove that
it is the best order.

With the facts only (`--facts-only-keys`), jev also gets the key decision
after 12 decisions with no new place, and after a change of floor level.

Before the runs start, the measurement tool checks the requests
(`jevmanic/checks.py`). It replays three recorded runs, builds the request
states with the settings of the measurement, and stops with no run if:

- a text names a field in back quotes that the state never has;
- a fact of a move (`movement`, `collects_key`, or a map after the move) does
  not agree with the game at the end of that move.

The tests (`tests/test_checks.py`) run the same checks for each text set, and
they prove that each check finds a known problem. The checks have two limits.
They check the names of the fields, not their place in the state: `warning`
passes if any part of the state has it. They also cannot check that a sentence
of a text is true. `--skip-checks` starts a measurement with no checks.

The log files go to `runs/<label>/`. The viewer shows them as the group
"Measurement: label". `experiments/diagnose.py` prints the map, the last
positions, and the last state of one run. The summaries of the measurements
are in `experiments/results/`.

## The data that we give to jev

Jev reads text only. It cannot read a screenshot. Jev is weak with
coordinates, with counts, and with large states. Thus the state gives
positions relative to Willy, in words and small numbers.

All examples below are from the recorded run
`demo/cavern-02-the-cold-room-promptA.jsonl` (The Cold Room, promptA). The
exact text of all instructions is in `jevmanic/instructions/`. The code that
makes the state is in `jevmanic/describe.py`. The viewer shows the exact state
and questions of each request.

### Request 1: the key decision

Jev gets this request at the start, after each collected key or flipped
switch, and again 25 decisions after the last key decision. The state has the
map of the cavern with its legend. It also has one entry with facts for each
key that is left, and for each switch that is not flipped. This example shows
the full legend and 2 of the 5 keys:

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

The answer in the example is `key_D`, with a probability of 0.50 and a
confidence of 0.37. `key_E` has 0.32, `key_A` 0.11, `key_C` 0.06, and `key_B`
0.01. This request used 1638 input tokens.

A test showed that the text must name the map. When the state has the map
and the text does not name it, jev selects the same key as with no map.

### Request 2: the move

The state of decision 6 of the same run, as the present code makes it:

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
      "movement": "Willy moves 1 cells to the left and 2 rows lower",
      "progress": "nearer",
      "place": "new place",
      "tried_from_here": "no"
    },
    "walk_right": {
      "movement": "Willy moves 1 cells to the right",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no",
      "ends_on": "crumbling floor, partly gone"
    },
    "jump_left": {
      "movement": "Willy moves 4 cells to the left and 1 rows higher",
      "progress": "farther",
      "place": "new place",
      "tried_from_here": "no"
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
    "jump_right": "kills Willy: fall or other cause",
    "jump_up": "no effect: Willy stays in the same place"
  }
}
```

| Field | Meaning |
| --- | --- |
| `willy` | the direction that Willy looks in, and the tile below him |
| `target` | the key or switch that jev selected, or the portal. When the target is on a higher floor, it has a `way_up`: the nearest place where a jump gets to a higher platform. When the target is on a lower floor, it has a `way_down`: the nearest safe edge or crumbling floor. If Willy stands on a crumbling floor, it is the safe fall place on that floor that is nearest to the target. A `warning` tells when Willy must not wait at a place. |
| `to_the_left`, `to_the_right` | the first thing in the path of Willy on his level: wall, nasty, edge, or nothing, with the distance in cells |
| `guardians` | the position of each horizontal guardian relative to Willy, and its `direction` (toward Willy or away from him). For a guardian on the level of Willy: is Willy in its patrol area, and where the patrol area ends. The code can also give facts about vertical guardians, but they are off, because they made the results worse. |
| `air` | plenty, low, or critical |
| `progress_measures` | the place that `progress` measures the distance to: the target (same level), the way up (higher floor), or the way down (lower floor) |
| `moves` | the true result of each valid macro, from the look-ahead |
| `moves.*.movement` | where Willy is after the macro |
| `moves.*.progress` | nearer, farther, or same |
| `moves.*.place` | new place, visited before, or visited many times (memory) |
| `moves.*.tried_from_here` | did Willy select this macro at this place before (memory) |
| `moves.*.ends_on`, `collects_key`, `completes_cavern`, `warning` | only when they apply. `ends_on` and `willy.standing_on` give the condition of a crumbling floor: new, partly gone, or almost gone. The code reads it from the pixels of the tile. |
| `moves_not_offered` | each macro that jev does not get, with the cause: it kills Willy (guardian, nasty, fall, or dead end), or it has no effect |

The request has one question, `move`. It is a Choice, and its options are
the valid macros. The instructions:

> Willy is a miner in a platform game. The goal: Willy must collect all keys, then go into the exit portal, and he must stay alive. The target is the key that Willy goes to now, or the portal when no key is left. Select the move that is the best for Willy now. `moves` gives the true result of each possible move. All moves in `moves` are safe and have an effect. `moves_not_offered` gives the moves that Willy cannot make now, with the cause. The meaning of the facts: `progress` tells if a move gets Willy nearer to the place that `progress_measures` names. `place` tells how frequently Willy was at the place where the move ends. `tried_from_here` tells if Willy made this move from this place before. `collects_key` tells that Willy gets a key with this move. `completes_cavern` tells that Willy goes into the portal with this move and the cavern is complete. `ends_on` tells that Willy stands on a crumbling floor after this move, and how much of that floor is left. `warning` tells that no move is safe after this move. Knowledge of the game: Willy can climb only 2 rows with one jump. If Willy comes back to the same places again and again, the direct way is closed, and he must go a different way, also if that way goes away from the target first. A crumbling floor breaks a little each time Willy stands on it. It can be the only way up, and it is also a way down. A nasty does not move: if it stops a jump, a jump from a different cell can go over it. A guardian moves along its patrol area: Willy can wait for it to go away, jump over it, or go out of its patrol area.

The criteria of the options:

- `jump_right`: Jump to the right. The result is in `moves.jump_right`.
- `jump_left`: Jump to the left. The result is in `moves.jump_left`.
- `walk_right`: Walk to the right. The result is in `moves.walk_right`.
- `walk_left`: Walk to the left. The result is in `moves.walk_left`.
- `jump_up`: Jump straight up. The result is in `moves.jump_up`.
- `wait`: Do not move. The result is in `moves.wait`.

The answer in the example is `walk_left`, with a probability of 0.57 and a
confidence of 0.44. `jump_left` has 0.25, `walk_right` 0.15, and `wait` 0.03.
This request used 1406 input tokens and took 233 ms.

The code makes no jev call when only one macro is valid. It also makes no
call when all valid macros have the same result (Willy is in the air).

## Limits

- The state has no facts about the special enemies of some caverns: Eugene
  (cavern 5), the Kong Beast (caverns 8 and 12), the Skylabs (cavern 14), and
  the light beam of cavern 19. The look-ahead still removes a move that they
  make deadly, because the look-ahead runs the real game.
- The code reads the vertical guardians, but the state has no facts about
  them, because those facts made the results worse. We did not measure the
  facts about the switches.
- The cause of a death (guardian or nasty) is an estimate from the positions
  at the death.
- The results come from 10 runs for each cavern. They are not exact.

## Files

| Path | Content |
| --- | --- |
| `emulator/` | ZX Spectrum emulator (C++) and the pybind11 binding `env.cpp` |
| `roms/ManicMiner.z80` | game snapshot |
| `jevmanic/game.py` | start of a cavern, memory reads, macros, look-ahead, dead end check |
| `jevmanic/describe.py` | the state: the map, the key facts, and the move facts |
| `jevmanic/brain.py` | the questions and the jev calls |
| `jevmanic/instructions/` | the instruction sets: `promptA/`, `promptB/`, `promptC/`, and your own folders |
| `jevmanic/llm_brain.py`, `laya_brain.py`, `local_brain.py` | other decision makers, for comparison (see docs/findings.md) |
| `jevmanic/runner.py` | the settings, the live run, the log file, and the replay |
| `jevmanic/options.py` | the run options of the terminal and the measurement |
| `jevmanic/server.py`, `jevmanic/web/` | the viewer |
| `jevmanic/lab.py` | the key decision lab of the viewer |
| `jevmanic/key_orders.py` | the optimum key order of each cavern |
| `jevmanic/cli.py` | a live run in the terminal |
| `jevmanic/checks.py` | the checks of the requests before a measurement |
| `experiments/` | measurement, diagnosis, and tests of how well jev reads a state |
| `experiments/results/` | the summaries of the measurements |
| `docs/findings.md` | the measurements behind the design |
| `docs/viewer.md` | the pages of the viewer |
| `docs/planner-subagent.md` | the test with a reasoning model as the planner |
| `docs/screenshots/` | the pictures of the viewer |
| `demo/` | one complete recorded run for each cavern that jev completed, in git |
| `runs/` | the log files of your runs (JSON Lines), not in git |

A log file has one header line. Then it has one line for each jev request (a
"target" record for a key decision, or a "decision" record with its state
and answers). The last line is the end record. The header has the macro
version (`macros: 2` = with the conveyor hold). A log file with no version
replays with the macros of version 1.

The emulator core comes from the esp32-zxspectrum project, which took it from
[OpenVegaPlus](https://github.com/alvaroalea/OpenVegaPlus).
