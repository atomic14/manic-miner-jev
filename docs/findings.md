# What we learned about jev

This document records the measurements behind the design of this project.
The [README](../README.md) explains the project, the terms, and the main
result.

The code on `main` has only the present design. The git tag
`research-2026-09` has the code for the measurements in this document, with
all the states, texts, and rules that they tested. To repeat a measurement,
check out that tag. These parts exist only in the tag:

- the options `--progress`, `--move-facts`, and `--rule nearer-new`;
- the instruction sets `promptB`, `promptA-no-progress`, `promptD-plain`,
  and `promptM-...`;
- the scripts `experiments/probe_gap.py`, `probe_key_order.py`, and
  `probe_target.py`.

On `main`, `experiments/results/` has only the summaries behind the README
tables and behind "What jev needs: tests in Central Cavern". The summaries
for the other measurements in this document are in the tag.

## How to read the numbers

Each measurement changes one thing and compares the result with a base. We
measured the base at the same time, with the same code. The code changed
between measurements, so one cavern can have different numbers in two
sections. Compare numbers only within one section.

Each section gives its settings:

- the instruction set (promptA, unless the section names a different set);
- the key decision: with the map, or with the facts only;
- the depth of the dead-end check;
- the number of runs for each cavern.

"10 of 10" means 10 complete runs out of 10. "4 to 6 of 10" means that two
or more measurements with the same settings gave 4, 5, or 6. Jev does not
always give the same answer for the same state, so a measurement changes a
little each time. 10 runs show only large differences (see "The spread of
the results").

## The instructions

### Give jev the goal and the meaning of each fact

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

In Central Cavern, the state said that `jump_left` had `collects_key: true`,
but jev selected `walk_left` (0.51 against 0.44). The instructions did not
say that Willy must collect keys, and they did not say what `collects_key`
means. We added the goal and the meaning of each fact to the text, but no
instruction about what to select. Central Cavern then went from 3 of 10 to
10 of 10. A run needed 74 decisions. With the promptB instructions, a run
needs 70.

### A shorter text was worse

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

We wrote the move text again with the same content, in short sentences and
in the form "field: meaning". The short text had 190 words, and the move text
at that time had 293 words. With the short text, Central Cavern needed 89
decisions instead of 71, and The Menagerie went from 10 of 10 to 4 of 10.
Jev reads full sentences better than a short list.

### Plain-English corrections to promptD made no measurable difference

Settings: promptD, key decision with the map, dead-end check of 4 moves, 10
runs. Measured on 28 September 2026.

We corrected three phrases that jev reads:

- the move facts say "1 cell" and "1 row" instead of "1 cells" and "1 rows";
- the move text says "even if that way goes away from the target" instead
  of "also if";
- the key text says "so a way across a crumbling floor can be open only
  once" instead of "thus a way that goes across a crumbling floor can be
  open only one time".

| Cavern | Old text | New text |
| --- | --- | --- |
| 1 Central Cavern | 9 of 10 | 10 of 10 |
| 2 The Cold Room | 1 of 10 | 3 of 9 |
| 3 The Menagerie, first measurement | 7 of 10 | 1 of 2 |
| 3 The Menagerie, second measurement | 2 of 10 | 2 of 10 |

In the first measurement, jev API errors (timeouts and 503 responses) ended
9 runs of the new text: 8 in The Menagerie and 1 in The Cold Room. The table
leaves them out. The repeat of The Menagerie gave 2 of 10 for the old text,
2 of 10 for all three corrections, and 2 of 10 for the two move-side
corrections alone. So the corrections have no effect that 10 runs can show,
and we kept them. The old text itself gave 7 of 10 and then 2 of 10 in The
Menagerie: 10 runs of one cavern can spread this widely.

### Instructions of the form "select X when Y" fit only the caverns they come from

promptB added instructions of the form "select X when Y". We wrote them
from caverns 1 and 2. The Menagerie (cavern 3) is a fair test, because we
did not use it to write them. The two sets got the same code and the same
settings (the key decision with the map, and a dead-end check of 4 moves).
20 runs each:

| Cavern | promptA: complete runs of 20 | promptB: complete runs of 20 |
| --- | --- | --- |
| 1 Central Cavern (used to write promptB) | 19 to 20 | 20 |
| 2 The Cold Room (used to write promptB) | 2 to 4 | 19 |
| 3 The Menagerie (fair test) | 12 to 17 | 2 |

"19 to 20" means that two or more measurements gave 19 or 20. In The Cold
Room, the first sentence of the promptB key text puts the key in the shaft
last. promptB is better in the caverns that we used to write it, and much
worse in The Menagerie. So promptA stayed the normal set. An instruction of
this form can be a correct change to a text, but it must be general, and we
must measure it in caverns that we did not use to write it.

## The facts in the state

### Jev cannot count the cells on a text map

`experiments/probe_gap.py` shows a map row with Willy, N empty cells, and a
nasty. It asks "are there exactly 2 empty cells?".

| N | Jev says yes (from the map) | Jev says yes (from a number) |
| --- | --- | --- |
| 1 | 0.61 | 0.03 |
| 2 | 0.75 | 0.91 |
| 3 | 0.60 | 0.03 |

A jump over a nasty is safe only when the gap is exactly 2 cells. So the
code gives distances as numbers.

We repeated the test on 28 September 2026, with one request for each gap
and each form. The map row was the packed form of the real map (`WW..X..`).

| N | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| From the map row | 0.45 | 0.60 | 0.63 | 0.56 | 0.32 | 0.19 | 0.20 |
| From a number | 0.02 | 0.03 | 0.89 | 0.03 | 0.03 | 0.02 | 0.03 |

This time the correct gap did not stand out from the map row. The two
measurements agree that the map row separates near from far, but not an
exact count. Each value comes from a single request.

### One reference from the code can be better than two facts

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

In cavern 4, the code selects a single tile in a corner as "the way up".
`progress` points to that tile, and Willy goes into that trap in each run.
We tried a different design: jev got the way up on the left and on the right
as two facts, and `progress` measured the distance to the target. Cavern 4
got its first complete run. But Central Cavern went from 10 of 10 to 5 of
10, and The Menagerie from 10 of 10 to 1 of 10. The single reference that
the code selects is important.

### More memory made the results worse

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

We gave jev the last 4 moves with their results (`recent_moves`,
`came_from`). Willy's movement from left to right and back did not change:
it was 32 % of the decisions, with and without this memory. But when a
valid move collected a key, jev selected that move in 67 % of the cases with
this memory, and in 89 % without it. The Menagerie went from 9 of 10 to 5
of 10. More text in the state takes weight away from the important facts.

The memory facts in the present state (`place`, `tried_from_here`) are not
necessary here. Central Cavern gives 9 of 10 without them and 10 of 10 with
them.

### Facts about vertical guardians made the results worse

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

The code reads the vertical guardians. The state can give each one's column
and direction, and whether its column crosses Willy's level. Caverns 9 and
18 have 4 vertical guardians each.

| Cavern | Complete runs with the facts | Complete runs without them |
| --- | --- | --- |
| 9 | 9 of 10 | 10 of 10 |
| 18 | 2 of 10 | 8 of 10 |

With the facts, a run needs more decisions (109 instead of 73 in cavern 9),
and more decisions have a low confidence. The look-ahead already removes
each move that a vertical guardian makes deadly. The facts add text but no
safety.

### A guardian fact for each move made the results worse

Settings: key decision with the map, 20 runs.

With a short dead-end check, all deaths in Central Cavern happen at the
conveyor behind the guardian. We gave each move the fact `guardian_after`:
where the guardian on Willy's level is after the move, and whether it moves
toward him.

| Cavern | Dead-end check | With `guardian_after` | Without it |
| --- | --- | --- | --- |
| Central Cavern | off | 4 of 20 | 7 of 20 |
| Central Cavern | 2 moves | 14 of 20 | 17 of 20 |
| The Menagerie | 12 moves | 7 of 20 | 17 to 19 of 20 |

### Lessons about the facts

- Two facts must agree. When "nearer to the portal" pointed right and "way
  down" pointed left, Willy went left and right with no end.
- A true fact can cause a loop. We gave the fact "after this move, these
  moves are safe". Then `jump_left` made `jump_right` safe, and
  `jump_right` took Willy back to the same place.
- Give the cause of a result. With only "this move kills Willy", jev waited
  at a nasty for 30 decisions. The cause (guardian or nasty) tells jev
  whether a wait can help.

### The way down must be true in each cavern

Settings: key decision with the map, dead-end check of 12 moves, 20 runs
(The Cold Room: 10 runs).

After the last key in Central Cavern, Willy stands on the crumbling floor
that is his way down. There, `progress` said that a walk toward the portal
is nearer. Jev gave the two walks almost the same probability (0.45 and
0.44). The walk to the right ends in a place with no way out. This caused 4
of the 5 failed runs.

The first correction said "to leave the way down is farther". It gave
Central Cavern 19 of 20, but The Menagerie 0 of 20. In The Menagerie, Willy
must walk along a long crumbling floor to the place above the last key, and
each cell of that floor is a way down.

The present definition is true in both caverns: if Willy stands on a
crumbling floor, the way down is the safe place to fall on that floor that
is nearest to the target. `way_down` and `progress` use that place. Result:
Central Cavern 20 of 20 in two measurements, The Menagerie 17 of 20, and The
Cold Room 2 of 10 (no change).

### The way down and `progress` must use the same side

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

In cavern 6, the state gave the way down on one side, and `progress`
measured the distance to a way down on the other side. That side changed
each time Willy moved one cell, so Willy went left and right between two
columns in each run. With one side for both facts, cavern 6 collects 2.4
keys instead of 0.0. It is still 0 of 10.

The way down also excludes a fall of 5 rows or more, because such a fall
kills Willy. That limit gave no change that we can measure (2.6 keys).

### The condition of a crumbling floor

Settings: key decision with the map, dead-end check of 12 moves, 20 runs.

The game keeps no counter for a crumbling floor. It moves the tile's pixels
down while Willy stands on it, and one walk across a tile uses about half
of it. The move facts give the condition as a word: new, partly gone, or
almost gone.

| Cavern | With the condition | Without it |
| --- | --- | --- |
| Central Cavern | 20 of 20 | 40 of 40 (two measurements) |
| The Cold Room | 2 of 20 | 3 of 20 |
| The Menagerie | 19 of 20 | 17 of 20 |

This gain is too small to measure. We keep the condition because it is true,
and because it corrects `ends_on` for a tile that is gone after the move.

In the key decision, the condition gave no gain. We used the symbol `-` on
the map for a tile that is almost gone, and the condition in
`floor_below_key`. The key orders did not change (Central Cavern E D B in
20 of 20 runs, The Cold Room D E C in 17 of 20), and the results were 20, 2,
and 16 of 20.

### The conveyor hold

Settings: key decision with the map, 20 runs.

In the game, Willy stands still on a conveyor only if the opposite direction
is held when he drops onto it. The moves do this (see "The conveyor hold" in
[design.md](design.md)). Without the hold, a conveyor always moves Willy.

| Cavern | Dead-end check | With the hold | Without it |
| --- | --- | --- | --- |
| Central Cavern | off | 4 of 20 | 7 of 20 |
| Central Cavern | 2 moves | 20 of 20 | 17 of 20 |
| Central Cavern | 12 moves | 20 of 20 | - |
| The Menagerie | 12 moves | 15 of 20 | - |

This gain is too small to measure, but the hold matches the game.

At the deadly place in Central Cavern (the conveyor behind the guardian),
Willy gets onto the conveyor with a jump. After that, no input can stop him.
Jev can select a drop there (`walk_left`, after which Willy stands still).
But jev selects `jump_left` with 0.54 to 0.57, because the state gives no
reason to prefer the walk. A dead-end check of 2 to 4 moves is necessary at
this place. We found no fact that can replace it.

## The dead-end check

Settings: key decision with the map, 20 runs. The first table used the
moves from before the conveyor hold (see "The conveyor hold").

| Dead-end check in Central Cavern | off | 1 move | 2 moves | 4 moves |
| --- | --- | --- | --- | --- |
| Complete runs of 20 | 7 | 9 | 17 | 20 |

With the check off, Willy is still alive at the end of each valid move,
because the look-ahead removes each move that kills him directly.

| Moves of the dead-end check | Central Cavern | The Cold Room | The Menagerie |
| --- | --- | --- | --- |
| 4 (the default) | 19 to 20 | 2 | 12 |
| 6 | - | 4 | 15 |
| 12 | 20 | 2 to 3 | 15 to 19 |

The default is 4 moves. That is enough for Central Cavern, and it gives
less help from the code than a deeper check. With 4 moves, 6 of the 8
failed runs in The Menagerie are deaths. The Menagerie needs 6 moves.

With a check of 2 moves (key decision with the facts only, 10 runs), all 9
deaths in The Menagerie happen at the same place. Each death comes after 4
to 6 decisions with no real choice: it is one trap that is 6 moves deep.
The deep check removes the first step into the trap. So the code, and not
jev, does a large part of the work to keep Willy alive.

## The key decision

### The map gives a better key decision in a test, but not more complete runs

`experiments/probe_key_order.py` asks "which key next?" in 13 situations
from caverns 1 to 4, with no game. The reference is the key order of the
complete recorded runs. The correct next key: facts only 5 of 13, map only
8, map and facts 12. In Central Cavern, with the map, jev selects key E
first. That is the start of the optimum order (E A C D B). With the facts
only, jev selects D first and E last.

In play (dead-end check of 12 moves, 10 runs), with the map in the key
decision, Willy has all 5 keys in Central Cavern at decision 35 to 39. With
the facts only, he has them at decision 62 to 66. But the complete runs went
from 10 of 10 to 7 of 10. We then changed one thing at a time in Central
Cavern, 10 runs each:

| Configuration | Complete | Decisions |
| --- | --- | --- |
| The code sets the order E A C D B (the optimum order) | 10 | 80 |
| The code sets the order A C D B E (the order from the runs with the facts only) | 9 | 74 |
| Jev makes each key decision with the map, at the start and after each collected key | 7 | 94 |
| The code sets the order that jev selected in the row above: E, then D, then B | 8 | 109 |

The move decisions complete the optimum order with no problem, and the key
text is not the cause. The cause is the second key decision. After E, jev
selects D with a confidence of 0.86, because D is only 5 cells away and A
is 20 cells away. But Willy can get to the top floor only at its left end,
so A is the correct next key. To see this, jev must follow the route on the
map across four floors. That task has more than one step, and the jev
documentation says that jev is weak at such tasks. With D as the target, the
route along the top floor is different, and 2 or 3 of 10 runs then fail
after the keys.

### The Cold Room needs a plan of the route

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

In The Cold Room, the key order explains the full difference between
promptB (9 of 10) and promptA (4 to 6 of 10). We measured two changes to the
key text:

| Change to the key text | Cavern 1 | Cavern 2 | Cavern 3 | Cavern 4 | Cavern 16 |
| --- | --- | --- | --- | --- | --- |
| None (the normal text) | 10 | 4 to 6 | 10 | 0 (4.0 keys) | 0 (1.7 keys) |
| + the meaning of `one_way_trip` | 8 | 0 | 10 | - | - |
| The three key sentences of promptB | 7 | 8 | 9 | 0 (0 keys) | 0 (2.0 keys) |

The numbers are complete runs out of 10. When no run is complete, the mean
keys are in brackets. With the sentence about `one_way_trip`, jev did not
select the shaft key too early. But a different order problem then ended
the runs: Willy used the only crumbling way up twice. The promptB key
sentences correct the order in cavern 2, and they make caverns 1 and 4
worse. Jev gets facts relative to Willy, and an instruction about those
facts fits one cavern but not the next.

### A key decision that jev can change

Settings: key decision with the facts only, dead-end check of 12 moves, 10
runs.

With the facts only, jev also gets the key decision after 12 decisions with
no new place, and after a change of floor level. Jev can keep or change the
target, and each key has a short memory (`decisions_used_for_it`,
`gave_up_on_it`). The Menagerie went from 9 of 10 to 10 of 10, and cavern 4
from 3.5 to 4.0 keys. Jev kept the target in 363 of 421 requests.

### How often to repeat the key decision

- With the map, after 25 decisions (`--key-every 25`, the default).
  Settings: dead-end check of 12 moves, 10 runs. Complete runs in caverns 1
  to 4: 9, 2, 6, 0 with the repeat, and 7, 0, 7, 0 with no repeat. The
  repeat is the default because it gives 17 complete runs, against 14. This
  difference is small (see "The spread of the results"). The runs fail in
  the move decisions, not in the key decisions.
- Before each move (`--key-every 1`). Settings: dead-end check of 4 moves,
  20 runs. Caverns 1, 2, 3: 20, 0, 17 (the default: 19, 2, 12). Jev kept the
  target in 97 % of 5640 requests, and the key orders did not change. This
  costs twice as much and gives no gain.

### Other changes to the key decision

- The word "optimum" in the key text ("Select the optimum key or switch for
  Willy to get next") gave no gain. Settings: dead-end check of 4 moves, 20
  runs. Caverns 1, 2, 3: 20, 4, 13.
- A switch as a target made no difference. Settings: key decision with the
  facts only, dead-end check of 12 moves, 10 runs. In the two Kong Beast
  caverns (8 and 12), a switch is a target that jev can select. With and
  without the switch targets, both caverns are 0 of 10, with the same number
  of keys (0.7 and 0.8 in cavern 8, 0.0 in cavern 12). The runs fail before
  the switches matter.
- The optimum key order helps one cavern and makes a different cavern worse.
  Settings: dead-end check of 4 moves, 20 runs. The code sets the order
  (`--key-order optimum`), and jev makes each move decision:

  | Cavern | Optimum order | Jev's own key decisions (the default) |
  | --- | --- | --- |
  | Central Cavern | 20, with 80 decisions | 100 decisions |
  | The Cold Room | 12 | 2 to 4 |
  | The Menagerie | 3 (all other runs end with "stuck: no progress") | 12 to 17 |

  In The Cold Room, the optimum order has the one-way key C last, and jev
  selects C third. In The Menagerie, the optimum order is a route that the
  move facts do not support.

## Jev and the simple rules

Settings: the defaults, 10 runs of each cavern. The README section "Results"
gives the table for each cavern.

The rule `nearer` selects a move that completes the cavern or collects a
key, else a move that goes nearer, else any valid move. In 15086 move
decisions (jev with its own key order), jev selected a move that the rule
could also select in 13986 (93 %). A random valid move would do this in
54 % of the same decisions. The share is 85 % to 100 % in each cavern.
`experiments/agreement.py` computes both numbers from the log files. When jev did not follow the rule, its move went farther:

- to a new place (417 decisions);
- to a place visited before (384);
- to a place visited many times (228).

So the `progress` fact decides most moves.

With the same key order (the optimum order), jev completed 26 of 200 runs
(1.5 keys in a run), and the rule `nearer` 24 of 200 (1.3 keys).

The rule `nearer-new` also prefers a new place: first a nearer move to a new
place, then any nearer move, then a move to a new place. It completed only
18 of 200 runs. A preference for new places does not help the rule.

## Jev and the rules: a like-for-like comparison

Settings: promptD, key decision with the map, dead-end check of 4 moves, 10
runs of each cavern for each arm. Measured on 28 September 2026, with the
same code for all arms. We ran every arm twice. No run had an API error.

The measurement in "Jev and the simple rules" gave the rule a fixed key
order that jev did not need, and it ran each arm once. Here the new setting
`--key-rule nearest` lets a rule choose the keys too: it selects the key
nearest to Willy, in cells. With it, jev and the rule get the same key rule,
and only the move decision differs. The rule `nearer-memory` is the rule
`nearer` plus the memory facts: it prefers a nearer move that Willy did not
try from this place, then any nearer move, then any move not tried from this
place. It ran once.

| Arm | Complete runs of 200: first run | Second run |
| --- | --- | --- |
| jev, its own key decisions | 32 | 35 |
| jev, the optimum key order | 39 | 33 |
| rule `nearer`, the optimum key order | 19 | 20 |
| rule `nearer-memory`, the optimum key order | - | 19 |
| jev, key rule `nearest` | 34 | 27 |
| rule `nearer`, key rule `nearest` | 16 | 18 |
| rule `nearer-memory`, key rule `nearest` | - | 25 |
| jev, move sampled from its probabilities (`--sample-moves`) | 5 | 7 |
| random valid move, the optimum key order | 0 | 0 |

Over the two runs, jev completes about twice as many runs as the rule
`nearer` with the same key choice: 72 of 400 against 39 with the optimum
order (Fisher p = 0.001), and 61 of 400 against 34 with the key rule
`nearest` (p = 0.004). All of the difference is in two caverns:

| Cavern | jev, optimum order | rule `nearer`, optimum order | rule `nearer-memory`, optimum order |
| --- | --- | --- | --- |
| 9 Wacky Amoebatrons | 9, 8 | 1, 2 | 4 |
| 18 Amoebatrons' Revenge | 6, 7 | 0, 1 | 2 |

In the other 18 caverns there is no measurable difference: 42 of 360
against 35 (p = 0.47) with the optimum order, and 38 against 32 (p = 0.53)
with the key rule `nearest`. The rule `nearer-memory` does better than
`nearer` in the two caverns, but not nearly as well as jev, and not better
in total.

In Wacky Amoebatrons, the rule `nearer` died in 6 of 10 runs of the first
run (key rule `nearest`: 7 of 10). It reached column 20, row 13 of the
bottom floor in 9 or 10 of its 10 runs, and moved back and forth there until
no move was safe. The dead-end check of 4 moves did not see this trap early
enough. Jev also reached that place in 3 to 5 of its runs, but it moved on
and did not die there. The state has no facts about the vertical guardians
(see "Facts about vertical guardians made the results worse"), but both
caverns also have horizontal guardians, and jev gets facts about those (see
"Jev without the guardian facts"). In Amoebatrons' Revenge, the rule
`nearer` ended with "stuck: no progress" in 7 of 10 runs (key rule
`nearest`: 10 of 10).

A move sampled from jev's probabilities completes only 5 and 7 runs. Jev's
selected move is much better than its probability distribution suggests.

With jev's moves from the first run, `experiments/agreement.py` gives 91.5 %
agreement with the rule `nearer` (optimum order) and 92.1 % (jev's own key
decisions). A random valid move gives 55.5 %.

### Jev without the guardian facts

Settings: the same, with the optimum key order and `--no-guardian-facts`:
the move decision's state has no `guardians` field. The look-ahead still
removes each deadly move. Two runs of each cavern. (Caverns 13 to 20 of the
first attempt ended with a jev API error, "no available credits", and we
ran them again.)

| Cavern (2 × 10 runs) | jev, no guardian facts | jev, with guardian facts | rule `nearer` |
| --- | --- | --- | --- |
| 1 Central Cavern | 20 | 19 | 17 |
| 2 The Cold Room | 15 | 12 | 15 |
| 3 The Menagerie | 7 | 7 | 3 |
| 9 Wacky Amoebatrons | 7 | 17 | 3 |
| 18 Amoebatrons' Revenge | 6 | 13 | 1 |
| All 20 caverns | 56 of 400 | 72 of 400 | 39 of 400 |

In 18 caverns, the guardian facts make no measurable difference: the
look-ahead removes the deadly moves. In the two caverns where jev does
better than the rule, the guardian facts about double jev's result (Wacky
Amoebatrons: Fisher p = 0.003; Amoebatrons' Revenge: p = 0.06). Without
them, jev still does better than the rule in these two caverns (7 against 3,
and 6 against 1).

### A difference from the first measurement

On 26 September, jev with the optimum order completed 26 runs, and the rule
24. Most of the difference from 28 September is in Wacky Amoebatrons: jev
with the optimum order completed 1 of 10 runs on 26 September, and 6 to 9 of
10 in each arm on 28 September. The rule, which makes no jev request, gave 2
and then 1 and 2 of 10 in the same cavern. Two measurements on 28 September
looked for the cause, and found none:

- The instruction set: promptA and promptD gave 36 and 34 complete runs.
- The move wording ("1 cell" instead of "1 cells", see "Plain-English
  corrections to promptD made no measurable difference"): caverns 9 and 18,
  promptA, 13 of 20 with the old wording and 14 of 20 with the new wording.

The model version was `jev-1.13.0` on both days. We do not know the cause.

### Are jev's single decisions better where it disagrees with the rule?

`experiments/paired_rollouts.py` takes 300 decisions where jev's move was
not a move of the rule `nearer`. At each one, it plays two branches from the
same game state: jev's move, or a move of the rule. After that first move,
the rule plays both branches for 60 decisions, 6 times each. A branch counts
the keys collected while Willy is alive. (A first version counted the keys
after a death, when the game had already put them back. Its numbers were
wrong, and we removed them.)

| Decisions from | Mean keys: jev's move first | Rule's move first | Difference (95 % interval) | Willy died: jev / rule |
| --- | --- | --- | --- | --- |
| 26 September runs (jev's own key decisions) | 0.286 | 0.253 | +0.033 (+0.003 to +0.068) | 16.7 % / 15.3 % |
| 28 September runs (the optimum key order) | 0.322 | 0.283 | +0.039 (+0.001 to +0.078) | 24.1 % / 26.2 % |

In both sets, jev's move leads to slightly more keys, and the interval is
just above zero. The death rates differ in opposite directions, and neither
difference is significant. One different decision changes little; the
effect of jev builds up over a full run.

## Jev without `progress`

Settings: the defaults, with `--no-progress --instructions
promptA-no-progress`, 10 runs of each cavern. The state has no `progress`
and no `progress_measures`, and the text does not name them. Jev still gets
the target, the way up or down, and the result of each move (for example
"Willy moves 3 cells to the right and 2 rows higher").

Jev completed 5 of 200 runs (The Menagerie 1, Wacky Amoebatrons 2,
Amoebatrons' Revenge 2), against 31 with `progress`. It collected almost as
many keys (1.3 in a run, against 1.4). In Central Cavern, it collected all 5
keys in 7 of 10 runs, but then it did not find the way down to the portal,
and each of those runs ended with "stuck: no progress". Jev can move toward
a key that it sees in the facts, but the route across the floors comes from
`progress`. One run ended with a server error from the jev API.

## What jev needs: tests in Central Cavern

These tests change one thing at a time in Central Cavern, with 20 runs each.
The settings: the key decision with the map, a dead-end check of 4 moves.
The key decision is the same in each test. A measurement of the defaults at
the time of these tests, on the same day, gave 20 of 20.

The goal facts are `collects_key` and `completes_cavern`. The memory facts
are `place` and `tried_from_here`. Each test has its own text, which
explains only the fields of its state (the instruction sets `promptD-plain`
and `promptM-...`).

### The direction of each move

| Test | Complete runs | Mean keys |
| --- | --- | --- |
| The full state, with the text `promptD` | 18 of 20 | 4.5 |
| Plain distances instead of `progress` (`--progress plain`) | 0 of 20 | 1.7 |
| The rule `plain` on the plain distances (no jev request) | 0 of 20 | 0.3 |
| The rule `nearer` (no jev request) | 17 of 20 | 4.6 |
| The rule `nearer` with no random choice (`--rule nearer-fixed`) | 0 of 20 | 0.0 |

- `progress` is not a plain measurement. The code makes two adjustments to
  it: a move that uses the way up or the way down is "nearer", and a move
  that leaves the target's level is "farther". Plain distances have no such
  adjustments, and they mislead. A jump onto a higher platform often ends
  past the way up, so its plain distance is "farther". When the target was
  higher, 512 of the 759 moves that go higher ended past the way up. Jev
  followed the facts: it selected 75 % of the "nearer" moves up, and 23 %
  of the "farther" ones. 14 of 20 runs ended with 1 key. So the route
  knowledge is in the two adjustments of `progress`.
- The rule `nearer` with no random choice selects the first move that
  passes a test. It completed 0 of 20, against 17 of 20 with the random
  choice. The random choice takes the rule out of loops.

### Fewer facts (`--move-facts NAME`)

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

- With only `progress`, jev follows "nearer" in each decision and goes
  around in a loop. When a move was "nearer", jev selected such a move in
  1975 of 1983 decisions (100 %). All 20 runs ended with no key and
  "stuck: no progress": Willy walked left and right at the same place.
- With `progress` and the goal facts, jev again followed "nearer" in each
  decision. 19 of 20 runs stopped with 1 key, at the same place.
- With the memory facts added, jev followed "nearer" in 94 % of the
  decisions. Each run collected all 5 keys, and 18 runs then stopped at the
  top right of the cavern, with no way down to the portal. The states
  between this one and the full state also collected all 5 keys and then
  stopped at the top right, where the way to the portal goes down. Jev gives
  almost the same answer each time in the same situation, so it needs the
  memory facts to leave a loop. The rule uses its random choice instead.
- One sentence of the text decides the result in this cavern: "If Willy
  comes back to the same places again and again, the direct way is closed,
  and he must go a different way, also if that way goes away from the target
  first." Without it, jev collects all keys but does not find the way down
  to the portal (0 of 20). With it, 20 of 20, 73 decisions, and 21 % of the
  decisions with a confidence below 0.5. The sentence about crumbling floors
  alone does not help (0 of 20). This sentence is close to the limit of the
  project principle, because it tells jev when it can leave "nearer".
- The sentence about loops needs the other facts. With only `progress`, the
  goal facts, and the memory facts, it makes the result worse (0 keys): with
  so few facts, the permission to leave "nearer" takes Willy the wrong way.
- The guardian facts are not necessary in this cavern. Without `guardians`
  and `air`, jev completes each run with 75 decisions, against 18 of 20 and
  107 decisions for the full state. The look-ahead already removes each move
  that a guardian makes deadly. We did not test this in the other caverns.
- The text `promptD` is promptA with correct statements about the moves in
  `moves` (see "The project principle" in the [README](../README.md)). It
  gave 18 of 20, against 20 of 20 for promptA. This difference can be
  chance.

### A map after each move (`--move-facts maps`)

Each valid move gets the map of the cavern at the end of the move. The map
comes from the snapshot that the look-ahead makes at that time: Willy, the
guardians, the keys that are left, and the condition of each crumbling tile
(`~` new, `-` partly gone, `_` almost gone, `.` gone). The state also names
the target key and has the goal and memory facts. The text has the sentence
about loops. A request has a median of 1773 tokens (the maps and
`progress`: 1834).

| Test | Complete runs | Mean keys | Decisions | Confidence below 0.5 |
| --- | --- | --- | --- | --- |
| The maps, no `progress` | 1 of 20 | 1.1 | 137 | 85 % |
| The maps and `progress` | 11 of 20 | 3.2 | 118 | 75 % |
| For comparison: no guardians, the sentence about loops | 20 of 20 | 5.0 | 73 | 21 % |

- A map after each move does not replace `progress`. Without `progress`,
  jev does not find the route in the maps: 9 runs got no key, 8 runs got
  only 1 key, and 6 runs ended when the air ran out, after 156 to 196
  decisions.
- With `progress`, the maps make the result worse than the compact facts.
  With the maps, jev is uncertain. A route over several floors is a task of
  several steps, and jev does not do it from a map.
- A first version of this test drew the guardians where they were before the
  move, and it did not show the crumbling floors breaking. It gave 1 and 12
  of 20. We removed its results. The request checks in `jevmanic/checks.py`
  now find both errors.

## The order of the options

`experiments/probe_option_order.py` asks jev 200 recorded move decisions
again (each with 3 or more options), in four forms:

| Form | Same answer as recorded | Selects the first option |
| --- | --- | --- |
| The same order, no change | 184 of 200 | 51 of 200 |
| The options in the reverse order | 172 of 200 | 23 of 200 |
| The options in a random order | 174 of 200 | 51 of 200 |
| The options and the entries of `moves` in the reverse order | 144 of 200 | 24 of 200 |

By chance, the first option is selected in 51 of 200. The option order has a
small effect, and jev does not prefer the first option. The order of the
facts in the state has a larger effect: the recorded answer's probability
changes by 0.11 on average, against 0.05 for the option order. The changed
answers go in no single direction. The test cost $0.05.

## Designs that we did not keep

These designs were not better than promptA in caverns 1 to 4:

- One Noul question for each move (1 of 12 complete). A Noul question asks
  jev for the probability that a statement is true.
- A question in which jev selects the next platform from the map (1 of 18
  complete).
- A "route mode". The code searched sequences of up to 32 moves to find the
  platforms that Willy can get to. Jev selected one platform, and the code
  walked the path. This mode completed caverns 2 and 3 in 9 and 10 of 10
  runs. But the code played 3459 moves, and jev selected only 175. So the
  result came from the search, not from jev.

`experiments/probe_target.py` compares fixed ways to choose the target with
jev's free choice.

## The spread of the results

10 runs are not enough to compare two configurations with close results.
One configuration (the code sets the order E A C D B in Central Cavern) gave
10 of 10 in one measurement and 7 of 10 in the next. In a second example,
with the same code, Central Cavern gave 6 of 10 in one measurement and 19 of
20 in the next. So a difference such as 7 of 10 against 10 of 10 can be
chance. This weakens some conclusions in this document, for example "the
second key decision is the cause". Large differences, such as 10 of 10
against 1 of 10, are real.

## Other decision makers

### An LLM instead of jev

The decision maker `jevmanic/llm_brain.py` calls Claude Haiku through the
`claude` command line tool. It gets the same instructions, the same options,
and the same state as jev, with no tools and no project files. One run of
Central Cavern, with the defaults at that time:

| | jev | Claude Haiku |
| --- | --- | --- |
| Result | complete in 8 to 10 of 10 runs | complete (1 run) |
| Decisions | 70 to 75 | 123 |
| All 5 keys at decision | 37 to 42 | 87 |
| Time for the decisions of one run | 24 seconds | 39 minutes |
| Time for one call | 0.3 seconds | 17.8 seconds |
| Cost of one run | $0.004 | $1.30 |

Haiku collected the first key at decision 13 (jev: 14). Then it went left
and right on a lower platform for about 60 decisions before it found the way
up. Haiku reasons before each answer, so one call is slow. This is one run
only. It shows that an LLM can do the task with the same facts. For one
run, jev is about 100 times faster and 300 times cheaper. For one call, jev
is about 60 times faster. Command:
`uv run python -m jevmanic.cli --cavern 1 --llm haiku`.

### A reasoning model as the planner, and jev as the player

Settings: the code sets the key order, dead-end check of 12 moves, 10 runs.

A separate Claude session with a reasoning model got only the map, the
legend, the guardians' limits, and the game mechanics. It gave a key order
for caverns 1 to 4, with reasons. An example reason: "the top floor can
only be reached from the far left, and E is on the only way up". For
Central Cavern, it gave E A C D B, the optimum order. For The Cold Room, it
gave the most frequent order in our complete runs. We used only its key
order (option `--key-order`), and jev made each move decision.

| | Cavern 1 | Cavern 2 | Cavern 3 | Cavern 4 |
| --- | --- | --- | --- | --- |
| The planner's key order | 7 of 10 | 6 of 10 | 9 of 10 | 0 of 10 |
| Jev's own key decisions | 8 to 10 | 4 to 6 | 10 | 0 |

The runs need fewer decisions (The Cold Room 76 instead of 95 to 122, The
Menagerie 54 instead of 66), but no more runs are complete. The full record
(the input, the answer with the reasons and the route plans, and the
measurement) is in [planner-subagent.md](planner-subagent.md).

### Laya instead of jev

[Laya](https://github.com/mizorewww/laya-mlx) is a typed decision model with
421 million parameters. It runs on an Apple Silicon computer with MLX
(Apple's machine learning library). Its request has the same form as a jev
request (`--laya`; install it with `uv sync --extra laya`). One request
takes about 50 ms, with no network call and no cost. Its answers are
deterministic: the same state always gives the same answer. Laya follows the
facts, but it completes no cavern.

- The same request as jev (promptA, the JSON state, dead-end check of 4
  moves). 10 runs in each of caverns 1, 2, and 3 gave no complete run, and
  a mean of 0, 0, and 1 key. The options' probabilities are almost equal.
  Laya reads only 256 tokens of the instructions and the options together,
  and it silently cuts the rest. The 6 move options use 130 tokens, and
  promptA has 402 tokens. The full input has 1024 tokens at most.
  `LayaBrain.cut_report()` reports how much text Laya cut.
- What Laya can read. We used 261 recorded decisions from three complete jev
  runs. In 226 of them, a valid move goes nearer to the target. The question
  was: does Laya select a move whose `progress` is "nearer"? A first test
  used 62 of these decisions. With nested JSON, Laya did this in 26 to 41 of
  62. With one short sentence for each option ("walk_right is nearer."), it
  did this in 56 of 62. A longer instruction, a condition ("if there is
  none, select…"), or a second fact in each sentence made the result worse.
  Laya prefers the first option. The mean of the probabilities for 6
  different option orders removes this effect: 215 of 226 (jev: 85 %). One
  yes-or-no question for each move was worse.
- The form that we use for Laya is in `jevmanic/laya_brain.py`, with
  `--instructions promptC --key-order optimum`. Each move has the text
  "jump_right is nearer and new.". The options are the names with no text.
  The instruction is "Select the move that is nearer. A move that collects a
  key is the best.". The answer is the mean of 6 orders. The key decision
  does not work (Laya selects the first key), so the code sets the key
  order.
- In real games (one run for each cavern, because the answers are
  deterministic), Laya got 4 of 5 keys in The Cold Room, and no key in
  caverns 1, 3, 4, 9, and 18. Laya follows `progress`, but it cannot weigh
  `progress` against the facts that show a loop. So Willy walks the same
  path again and again.
- The other versions of the model are not better. The version that we use
  (`laya-typed-decisions`) is a ModernBERT-large encoder, trained for four
  business tasks. The general version (`laya`) and the multilingual version
  select a "nearer" move in 198 and 130 of 226 decisions. The version that
  we use selects it in 212. `RLAgent` in the package is only a second name
  for `Agent`, and the package has no training code. The model matches the
  words of the question with the words of the options. It does not compare
  two facts. A model of this type must be trained on this task to do more.
- Laya's Snake demo uses a different method. Its code finds the best move
  with a planner, and writes "Safe. Best route to food." into the text of
  that option. The model then matches the word "best". That breaks the
  project principle, so we did not do it.

### A local LLM with the answer read from its logits

Two open projects, [jevfire](https://github.com/kikoncuo/jevfire) and
[SemIf](https://github.com/TheoLeeCJ/SemIf), copy the jev interface with an
open LLM. The model gets the state and the question in one chat prompt, and
each option has a one-letter label. The code reads the logits (the model's
score for each possible next token) at the first output position, and turns
them into a probability for each label. One pass through the model is one
decision, with no text generation. `jevmanic/local_brain.py` does this with
`mlx-lm` on this computer (`--local`; install it with
`uv sync --extra local`). The model gets the same instructions, options,
and JSON state as jev. Qwen3-8B in 4-bit form takes about 1.2 s for one
decision, with no cost.

- On the 261 recorded jev decisions, Qwen3-4B selects a "nearer" move in
  210 of 226 (jev: 85 %), the move that collects a key in 16 of 16, and the
  same move as jev in 157 of 261. Qwen3-4B reads the full request. Laya does
  not.
- In real games (dead-end check of 4 moves, one run for each cavern, because
  the model is deterministic), Qwen3-4B got 1, 2, and 0 keys in caverns 1,
  2, and 3. Qwen3-8B got 0 and 2 keys in caverns 1 and 2, and it completed
  The Menagerie in 64 decisions (jev: about 80).
- The model is very sure (1.0 against 0.0). When it makes a loop, it repeats
  the loop until the run ends. Jev gives probabilities between 0 and 1, and
  its answers change, so it can get out of a loop. We sampled the model's
  answer with a temperature (`LOCAL_TEMPERATURE`, 2 runs for each cavern):

  | Temperature | Central Cavern | The Cold Room | The Menagerie |
  | --- | --- | --- | --- |
  | 1.5 | 4.5 keys | complete in 1 of 2 runs (55 decisions) | 2 keys |
  | 2 | 3.5 keys | 1.5 keys | 2 keys |

  A temperature of 4 was worse. A random spread of the answers does not give
  jev's result. The spread of jev's probabilities carries information about
  the options.

## Open work

- The defaults are worse in some caverns. With the defaults (the key
  decision with the map, a dead-end check of 4 moves, 10 runs), cavern 4
  collects 0.0 keys, cavern 9 completes 4 of 10 runs, cavern 11 collects 0.0
  keys, and 9 of 10 runs in cavern 20 end with a death at decision 10. With
  the key decision with the facts only and a dead-end check of 12 moves,
  these caverns gave 4.0 keys, 10 of 10, 5 of 10 (3.8 keys), and 4.2 keys.
  We did not measure which of the two settings causes each difference.
- The key order. A good key order needs a plan of the route across the map
  (see "The key decision"). Jev selects the next key well from facts near
  Willy, but it does not plan a route.
- The depth of the dead-end check. Try a different depth, or replace the
  search with experience: a memory of the places where Willy died in other
  runs.
- Cavern 4. Each run ends in a trap in the top left corner, because the code
  selects a single tile as "the way up".
- Cavern 8. Willy jumps into the small space between two walls where the
  closed portal is. A walk has no effect there. The only way out is a jump
  to the left, onto a guardian's level. The look-ahead removes that jump
  each time the guardian makes it deadly. Then the only valid move is
  `wait`, and the run ends with "stuck: no progress" after 30 decisions.
  When the guardian is away, the jump to the left gets Willy out.
- Cavern 17. Willy moves between the two columns of the start platform. The
  only way forward is `walk_right`, which is "nearer", but jev selects
  `walk_left` with a confidence of 0.31.
