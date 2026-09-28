# What we learned about jev

This document gives the measurements behind the design of this project. The
[README](../README.md) explains the project, the terms, and the main result.

## How to read the numbers

Each measurement changes one thing and compares the result with a base. We
measured the base at the same time, with the same code. The code changed
between measurements. Thus one cavern can have different numbers in two
sections. Compare the numbers in one section only.

Each section gives its settings in this form:

- the instruction set (promptA, unless the section says a different set);
- the key decision: with the map, or with the facts only;
- the depth of the dead end check;
- the number of runs for each cavern.

"10 of 10" means 10 complete runs of 10. "4 to 6 of 10" means that two or
more measurements of the same settings gave 4, 5, or 6. Jev does not always
give the same answer for the same state, thus the result of a measurement
changes a little each time. 10 runs show only large differences (see "The
spread of the results").

## The instructions

### Give jev the goal and the meaning of each fact

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

In Central Cavern, the state said that `jump_left` had `collects_key: true`,
but jev selected `walk_left` (0.51 against 0.44). The instructions did not
say that Willy must collect keys. They also did not say what `collects_key`
means. We added the goal and the meaning of each fact to the text, with no
rule about what to select. Then Central Cavern went from 3 of 10 to 10 of 10.
A run needed 74 decisions. The rules of promptB need 70.

### A shorter text was worse

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

We wrote the move text again with the same content, in short sentences and in
the form "field: meaning". The short text had 190 words. The move text of
that time had 293 words. With the short text, Central Cavern needed 89
decisions, not 71, and The Menagerie went from 10 of 10 to 4 of 10. Jev reads
full sentences better than a short list.

### Rules fit only the caverns that they come from

See "PromptB compared with promptA" in the README. The rules of promptB are
better on the caverns that we used to write them, and worse on the other
caverns.

## The facts in the state

### Jev cannot count the cells on a text map

`experiments/probe_gap.py` shows a map row with Willy, N empty cells, and a
nasty. It asks "are there exactly 2 empty cells?". From the map, jev says yes
with a probability of 0.61, 0.75, and 0.60 for N = 1, 2, and 3. From a
number, jev says yes with 0.03, 0.91, and 0.03. A jump over a nasty is safe
only at exactly 2 cells. Thus the code gives distances as numbers.

### One reference from the code can be better than two facts

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

In cavern 4, the code selects a single tile in a corner as "the way up".
`progress` points to that tile, and Willy goes into that trap in each run. We
gave jev the way up on the left and on the right as two facts, and
`progress` measured the distance to the target. Cavern 4 got its first
complete run. But Central Cavern went from 10 of 10 to 5 of 10, and The
Menagerie from 10 of 10 to 1 of 10. Thus the one reference that the code
selects is important.

### More memory made the results worse

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

We gave jev the last 4 moves with their results (`recent_moves`,
`came_from`). The movement from left to right and back did not change: 32 %
of the decisions, with and without this memory. But with this memory, jev
selected a move that collects a key in 67 % of the cases. Without it, jev did
this in 89 % of the cases. The Menagerie went from 9 of 10 to 5 of 10. More
text in the state takes weight away from the important facts.

The memory facts in the present state (`place`, `tried_from_here`) are not
necessary. Central Cavern is 9 of 10 without them, and 10 of 10 with them.

### Facts about vertical guardians made the results worse

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

The code reads the vertical guardians. The state can give their column, their
direction, and if their column crosses the level of Willy. Caverns 9 and 18
have 4 vertical guardians each. Complete runs: 9 and 2 of 10 with the facts,
10 and 8 of 10 without them. With the facts, a run needs more decisions (109,
not 73, in cavern 9), and more decisions have a low confidence. The
look-ahead already removes each move that a vertical guardian makes deadly.
Thus the facts add text but no safety.

### A guardian fact for each move made the results worse

Settings: key decision with the map, 20 runs.

With a short dead end check, all deaths are at the conveyor of Central
Cavern, behind the guardian. We gave each move the fact `guardian_after`:
where the guardian on the level of Willy is after the move, and if it moves
toward him. Central Cavern: 4 of 20, not 7, with the check off; 14 of 20, not
17, with 2 moves. The Menagerie with a check of 12 moves: 7 of 20, not 17 to
19.

### Rules for the facts

- Two facts must agree. When "nearer to the portal" said right and "way down"
  said left, Willy went left and right with no end.
- A true fact can cause a loop. We gave the fact "after this move, these
  moves are safe". Then `jump_left` made `jump_right` safe, and `jump_right`
  took Willy back to the same place.
- Give the cause of a result. With only "this move kills Willy", jev waited
  at a nasty for 30 decisions. The cause (guardian or nasty) tells jev if a
  wait can help.

### The way down must be true in each cavern

Settings: key decision with the map, dead end check of 12 moves, 20 runs
(The Cold Room: 10 runs).

After the last key of Central Cavern, Willy stands on the crumbling floor
that is his way down. There, `progress` said that a walk toward the portal is
nearer. Jev gave the two walks almost the same probability (0.45 and 0.44).
The walk to the right ends in a place with no way out. This was the cause of
4 of 5 failed runs.

The first correction said "to leave the way down is farther". It gave Central
Cavern 19 of 20, but The Menagerie 0 of 20. In The Menagerie, Willy must walk
along a long crumbling floor to the place above the last key, and each cell
of that floor is a way down.

The present rule is true in the two caverns: if Willy stands on a crumbling
floor, the way down is the safe fall place on that floor that is nearest to
the target. `way_down` and `progress` use that place. Result: Central Cavern
20 of 20 in two measurements, The Menagerie 17 of 20, The Cold Room 2 of 10
(no change).

### The way down and `progress` must use the same side

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

In cavern 6, the state gave the way down on one side, and `progress` measured
the distance to a way down on the other side. That side changed each time
Willy moved one cell. Thus Willy went left and right between two columns in
each run. With one side for the two facts, cavern 6 collects 2.4 keys, not
0.0. It is still 0 of 10. The way down also refuses a fall of 5 rows or more,
because such a fall kills Willy. That rule gave no change that we can
measure (2.6 keys).

### The condition of a crumbling floor

Settings: key decision with the map, dead end check of 12 moves, 20 runs.

The game keeps no counter for a crumbling floor. It moves the pixels of the
tile down while Willy stands on it, and one walk across a tile uses
approximately half of it. The move facts give the condition as a word: new,
partly gone, or almost gone. With the condition: Central Cavern 20 of 20,
The Cold Room 2, The Menagerie 19. Without it: 40 of 40 (two measurements), 3
of 20, and 17 of 20. This is no gain that we can measure, but we keep the
condition, because it is true, and it corrects `ends_on` for a tile that is
gone after the move.

In the key decision, the condition gave no gain. We used a symbol `-` on the
map for a tile that is almost gone, and the condition in `floor_below_key`.
The key orders did not change (Central Cavern E D B in 20 of 20 runs, The
Cold Room D E C in 17 of 20), and the results were 20, 2, and 16 of 20.

### The conveyor hold

Settings: key decision with the map, 20 runs.

In the game, Willy stands still on a conveyor only if the opposite direction
is held when he drops onto it. The macros do this (see "How it works" in the
README). Without the hold, a conveyor always moves Willy. With the hold,
Central Cavern gave 4 of 20 (without it: 7) with the dead end check off, 20
(without it: 17) with 2 moves, and 20 of 20 with 12 moves. The Menagerie gave
15 of 20 with 12 moves. This is no gain that we can measure, but the hold is
true to the game.

At the deadly place of Central Cavern (the conveyor behind the guardian),
Willy gets onto the conveyor with a jump, and then no key can stop him. Jev
can select a drop there (`walk_left`, and then Willy stands still). But jev
selects `jump_left` with 0.54 to 0.57, because the state gives no cause to
prefer the walk. The dead end check of 2 to 4 moves is necessary at this
place. We found no fact that can replace it.

## The dead end check

Settings: key decision with the map, 20 runs. The first paragraph used the
macros without the conveyor hold (see "The conveyor hold").

Central Cavern: 7 of 20 with the check off, 9 with 1 move, 17 with 2 moves,
and 20 with 4 moves. With the check off, Willy is still alive at the end of
each move that jev gets, because the look-ahead removes each move that kills
him directly.

| Moves of the dead end check | Central Cavern | The Cold Room | The Menagerie |
| --- | --- | --- | --- |
| 4 (the default) | 19 to 20 | 2 | 12 |
| 6 | - | 4 | 15 |
| 12 | 20 | 2 to 3 | 15 to 19 |

The default is 4 moves. It is sufficient for Central Cavern, and it is a
smaller help from the code than a deeper check. With 4 moves, 6 of the 8
failed runs of The Menagerie are deaths. The Menagerie needs 6 moves.

With a check of 2 moves (key decision with the facts only, 10 runs), all 9
deaths in The Menagerie are at the same place. Each death comes after 4 to 6
decisions with no real choice: it is one trap that is 6 moves deep. The deep
check removes the first step into the trap. Thus the code, and not jev, does
a large part of "stay alive".

## The key decision

### The map gives a better key decision in a test, but not more complete runs

`experiments/probe_key_order.py` asks "which key next?" in 13 situations of
caverns 1 to 4, with no game. The reference is the key order of the complete
recorded runs. The correct next key: facts only 5 of 13, map only 8, map and
facts 12. In Central Cavern, with the map, jev selects key E first. That is
the start of the optimum order (E A C D B). With the facts only, jev selects
D first and E last.

In play (dead end check of 12 moves, 10 runs), with the map in the key
decision, Willy has all 5 keys of Central Cavern at decision 35 to 39. With
the facts only, he has them at decision 62 to 66. But the complete runs went
from 10 of 10 to 7 of 10. We then changed one thing at a time, in Central
Cavern, 10 runs each:

| Configuration | Complete | Decisions |
| --- | --- | --- |
| The code sets the order E A C D B (the optimum order) | 10 | 80 |
| The code sets the order A C D B E (the order of the runs with the facts only) | 9 | 74 |
| Jev selects each key with the map, at the start and after each collected key | 7 | 94 |
| The code sets the order that jev selected in the row above: E, then D, then B | 8 | 109 |

The movement completes the optimum order with no problem, and the text of the
key question is not the cause. The cause is the second key decision. After E,
jev selects D with a confidence of 0.86, because D is only 5 cells away and A
is 20 cells away. But Willy can get to the top floor only at its left end,
thus A is the correct next key. To see this, jev must follow the route on the
map across four floors. That is a task of more than one step, and the jev
documentation says that jev is weak at such tasks. With D as the target, the
route along the top floor is different, and 2 or 3 of 10 runs then fail
after the keys.

### The Cold Room needs a plan of the route

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

In The Cold Room, the order of the keys is the full difference between
promptB (9 of 10) and promptA (4 to 6 of 10). We measured two changes to the
key text:

| Change to the key text | Cavern 1 | Cavern 2 | Cavern 3 | Cavern 4 | Cavern 16 |
| --- | --- | --- | --- | --- | --- |
| None (the normal text) | 10 | 4 to 6 | 10 | 0 (4.0 keys) | 0 (1.7 keys) |
| + the meaning of `one_way_trip` | 8 | 0 | 10 | - | - |
| The three key rules of promptB | 7 | 8 | 9 | 0 (0 keys) | 0 (2.0 keys) |

The numbers are complete runs of 10, with the mean keys in brackets when no
run is complete. With the sentence about `one_way_trip`, jev did not select
the shaft key too early. But a different order problem then ended the runs:
Willy used the one crumbling way up two times. The key rules of promptB
correct the order in cavern 2, and they make caverns 1 and 4 worse. Jev gets
facts relative to Willy, and a rule about those facts fits one cavern but not
the next one.

### A key decision that jev can change

Settings: key decision with the facts only, dead end check of 12 moves, 10
runs.

With the facts only, jev also gets the key question after 12 decisions with
no new place, and after a change of floor level. Jev can keep or change the
target, and each key has a short memory (`decisions_used_for_it`,
`gave_up_on_it`). The Menagerie went from 9 of 10 to 10 of 10, and cavern 4
from 3.5 to 4.0 keys. Jev kept the target in 363 of 421 requests.

### How often to ask the key question

- With the map, after 25 decisions (`--key-every 25`, the default).
  Settings: dead end check of 12 moves, 10 runs. Caverns 1 to 4: 9, 2, 6, 0
  complete runs with the repeat, and 7, 0, 7, 0 with no repeat. The repeat
  is the default, because it gives 17 complete runs and no repeat gives 14.
  This difference is small (see "The spread of the results"). The runs fail
  in the move decisions, not in the key decisions.
- Before each move (`--key-every 1`). Settings: dead end check of 4 moves, 20
  runs. Caverns 1, 2, 3: 20, 0, 17 (the default: 19, 2, 12). Jev kept the
  target in 97 % of 5640 key requests, and the key orders did not change.
  This costs 2 times more and gives no gain.

### Other changes to the key decision

- The word "optimum" in the key question ("Select the optimum key or switch
  for Willy to get next") gave no gain. Settings: dead end check of 4 moves,
  20 runs. Caverns 1, 2, 3: 20, 4, 13.
- A switch as a target made no difference. Settings: key decision with the
  facts only, dead end check of 12 moves, 10 runs. In the two Kong Beast
  caverns (8 and 12), a switch is a target that jev can select. With and
  without the switch targets, the two caverns are 0 of 10, with the same
  number of keys (0.7 and 0.8 in cavern 8, 0.0 in cavern 12). The runs fail
  before the switches are important.
- The optimum key order helps one cavern and makes a different cavern worse.
  Settings: dead end check of 4 moves, 20 runs. The code sets the order
  (`--key-order optimum`), and jev makes each move decision. Central Cavern
  20 (80 decisions, not 100), The Cold Room 12 (the default: 2 to 4), The
  Menagerie 3 (the default: 12 to 17; all other runs end with no progress).
  In The Cold Room, the optimum order has the one-way key C last, and jev
  selects C third. In The Menagerie, the optimum order is a route that the
  move facts do not support.

## Jev and the simple rules

Settings: the defaults, 10 runs of each cavern. The README ("Result") gives
the table for each cavern.

The rule `nearer` selects a move that completes the cavern or collects a
key, else a move that goes nearer, else any valid move. In 15086 move
decisions of jev (with its own key order), jev selected a move that the rule
can also select in 13986 (93 %). This is 85 % to 100 % in each cavern. When
jev did not follow the rule, its move went farther to a new place (417),
farther to a place visited before (384), or farther to a place visited many
times (228). Thus the `progress` fact decides most moves.

With the same key order (the optimum order), jev completed 26 of 200 runs
(1.5 keys in a run), and the rule `nearer` 24 of 200 (1.3 keys).

The rule `nearer-new` also prefers a new place: first a nearer move to a new
place, then any nearer move, then a move to a new place. It completed only
18 of 200 runs. A preference for new places does not help the rule.

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
and each run ended with no progress. Thus jev can move toward a key that it
can see in the facts, but the route across the floors comes from `progress`.
One run ended with a server error of the jev API.

## What jev needs in Central Cavern

Settings: the key decision with the map, a dead end check of 4 moves, 20 runs
of Central Cavern for each test. The README ("What jev needs: tests in
Central Cavern") gives the table.

- Plain distances in place of `progress`. When the target was higher, 512 of
  the 759 moves that go higher ended past the way up, thus their plain
  distance to the way up was "farther". Jev followed the facts: it selected
  75 % of the "nearer" moves up, and 23 % of the "farther" ones. 14 of 20
  runs ended with 1 key.
- Only `progress`. When a move was "nearer", jev selected such a move in 1975
  of 1983 decisions (100 %). All 20 runs ended with no key and no progress:
  Willy walked left and right at the same place.
- Only `progress` and the goal facts. Jev again followed "nearer" in each
  decision. 19 of 20 runs stopped with 1 key, at the same place.
- `progress`, the goal facts, and the memory facts. Jev followed "nearer" in
  94 % of the decisions. Each run collected all 5 keys, and 18 runs then
  stopped at the top right of the cavern, with no way down to the portal.
- The rule `nearer` completed 17 of 20 runs. The same rule with no random
  choice (it selects the first move that passes a test) completed 0 of 20.
  Thus the random choice takes the rule out of loops, and jev, which gives
  almost the same answer each time in the same situation, needs the memory
  facts for this.

## The smallest state in Central Cavern

Settings: the key decision with the map, a dead end check of 4 moves, 20 runs
of Central Cavern for each test. The README gives the tables.

- The runs of the states between `progress-goal-memory` and the full state
  collected all 5 keys, and then stopped with no progress at the top right of
  the cavern. The way to the portal goes down there.
- The full state without `guardians` and `air` completed 20 of 20, with 75
  decisions (the full state: 18 of 20, 107 decisions).
- With the same state and a text that explains only the fields: 0 of 20.
  With only the sentence about crumbling floors added: 0 of 20. With only
  the sentence about loops added: 20 of 20, 73 decisions, and 21 % of the
  decisions with a confidence below 0.5.
- `progress`, the goal facts, the memory facts, and the sentence about loops:
  0 of 20, and no key. With so few facts, the permission to leave "nearer"
  takes Willy the wrong way.

## A map after each move

Settings: the same. Each valid move gets the map of the cavern at the end of
the move. The map comes from the snapshot that the look-ahead makes at the
end of the move: Willy, the guardians, and the keys where they are then, and
the condition of each crumbling tile (`~` new, `-` partly gone, `_` almost
gone, `.` gone). The state also names the target key, and it has the goal and
memory facts. The text has the sentence about loops. A request has a median of
1773 tokens (the maps and `progress`: 1834).

- The maps with no `progress`: 1 of 20. 9 runs got no key, and 8 runs got
  only 1 key. 6 runs ended when the air ran out, after 156 to 196 decisions.
  85 % of the decisions had a confidence below 0.5.
- The maps and `progress`: 11 of 20. 75 % of the decisions had a confidence
  below 0.5.
- A first version of this test drew the guardians where they were before the
  move, and it showed no erosion. It gave 1 and 12 of 20. We removed its
  results. The checks in `jevmanic/checks.py` now find both errors.

## The order of the options

`experiments/probe_option_order.py` asks jev 200 recorded move decisions
again (3 or more options each), in four forms:

| Form | Same answer as recorded | Selects the first option |
| --- | --- | --- |
| The same order, no change | 184 of 200 | 51 of 200 |
| The options in the reverse order | 172 of 200 | 23 of 200 |
| The options in a random order | 174 of 200 | 51 of 200 |
| The options and the entries of `moves` in the reverse order | 144 of 200 | 24 of 200 |

By chance, the first option is selected in 51 of 200. The order of the
options has a small effect, and jev does not prefer the first option. The
order of the facts in the state has a larger effect: the mean change of the
probability of the recorded answer is 0.11, against 0.05 for the order of
the options. The changed answers go in no single direction. The test cost
$0.05.

## Designs that we did not keep

These designs were not better than promptA on caverns 1 to 4:

- One Noul question for each move (1 of 12 complete). A Noul question asks
  jev for the probability that a statement is true.
- A question in which jev selects the next platform from the map (1 of 18
  complete).
- A "route mode". The code searched sequences of up to 32 macros to find the
  platforms that Willy can get to. Jev selected one platform, and the code
  walked the path. This mode completed caverns 2 and 3 in 9 and 10 of 10
  runs. But the code walked 3459 macros, and jev selected only 175 single
  moves. Thus the result came from the search, and not from jev.

`experiments/probe_target.py` compares rules for the target with a free
choice.

## The spread of the results

10 runs are not sufficient to compare two configurations with near results.
One configuration (the code sets the order E A C D B in Central Cavern) gave
10 of 10 in one measurement and 7 of 10 in the next one. A second example:
with the same code, Central Cavern gave 6 of 10 in one measurement and 19 of
20 in the next one. Thus a difference such as 7 of 10 against 10 of 10 can
be chance. This makes some conclusions in this document weaker, for example
"the second key decision is the cause". Large differences, such as 10 of 10
against 1 of 10, are real.

## Other decision makers

### An LLM in the place of jev

The decision maker `jevmanic/llm_brain.py` calls Claude Haiku through the
`claude` command line tool. It gets the same instructions, the same options,
and the same state as jev, with no tools and no project files. One run of
Central Cavern, with the default configuration of that time:

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
run only. It shows that an LLM can do the task with the same facts. For one
run, jev is approximately 100 times quicker and 300 times cheaper. For one
call, jev is approximately 60 times quicker. Command:
`uv run python -m jevmanic.cli --cavern 1 --llm haiku`.

### A reasoning model as the planner, and jev as the player

Settings: key decision set by the code, dead end check of 12 moves, 10 runs.

A separate Claude session with a reasoning model got only the map, the
legend, the limits of the guardians, and the rules of the game. It gave a key
order for caverns 1 to 4, with reasons. An example of a reason: "the top
floor can only be reached from the far left, and E is on the only way up".
For Central Cavern, it gave E A C D B, the optimum order. For The Cold Room,
it gave the most frequent order of our complete runs. We used only its key
order (option `--key-order`), and jev made each move decision. Complete runs,
caverns 1 to 4: 7, 6, 9, 0 of 10. Jev with its own key decision gave 8 to
10, 4 to 6, 10, 0. The runs need fewer decisions (The Cold Room 76, not 95 to
122; The Menagerie 54, not 66), but no more runs are complete. The full
record (the input, the answer with the reasons and the route plans, and the
measurement) is in [planner-subagent.md](planner-subagent.md).

### Laya in the place of jev

[Laya](https://github.com/mizorewww/laya-mlx) is a typed decision model with
421 million parameters. It runs on an Apple Silicon computer with MLX (the
machine learning library of Apple). Its request has the same form as a jev
request (`--laya`, install with `uv sync --extra laya`). One request takes
approximately 50 ms, with no network call and no cost. Its answers are
deterministic: the same state always gives the same answer. Laya follows the
facts, but it completes no cavern.

- The same request as jev (promptA, the JSON state, dead end check of 4
  moves). 10 runs in each of caverns 1, 2, and 3 gave no complete run, and a
  mean of 0, 0, and 1 key. The probabilities of the options are almost equal.
  Laya reads only 256 tokens of the instructions and the options together,
  and it cuts the rest with no message. The 6 move options use 130 tokens,
  and promptA has 402 tokens. The full input has 1024 tokens at most.
  `LayaBrain.cut_report()` gives the text that Laya cut.
- What Laya can read. We used 261 recorded decisions of three complete jev
  runs. In 226 of them, a valid move goes nearer to the target. The question
  was "does Laya select a move whose `progress` is nearer?". A first test
  used 62 of these decisions: with nested JSON, Laya did this in 26 to 41 of
  62; with one short sentence for each option ("walk_right is nearer."), in
  56 of 62. A longer instruction, a condition ("if there is none,
  select…"), or a second fact in each sentence made the result worse. Laya
  prefers the first option. The mean of the probabilities for 6 different
  orders of the options removes this effect: 215 of 226 (jev: 85 %). One yes
  or no question for each move was worse.
- The form that we use for Laya is in `jevmanic/laya_brain.py`, with
  `--instructions promptC --key-order optimum`. Each move has the text
  "jump_right is nearer and new.". The options are the names with no text.
  The instruction is "Select the move that is nearer. A move that collects a
  key is the best.". The answer is the mean of 6 orders. The key decision
  does not work (Laya selects the first key), thus the code sets the key
  order.
- In real games (one run for each cavern, because the answers are
  deterministic), Laya got 4 of 5 keys in The Cold Room, and no key in
  caverns 1, 3, 4, 9, and 18. Laya follows `progress`, but it cannot compare
  `progress` with the facts that show a loop. Thus Willy walks the same path
  again and again.
- The other versions of the model are not better. The version that we use
  (`laya-typed-decisions`) is a ModernBERT-large encoder, trained for four
  business tasks. The general version (`laya`) and the multilingual version
  select a "nearer" move in 198 and 130 of 226 decisions. The version that we
  use selects it in 212. `RLAgent` in the package is only a second name for
  `Agent`, and the package has no training code. The model matches the words
  of the question with the words of the options. It does not compare two
  facts. A model of this type must be trained on this task to do more.
- The Snake demo of Laya uses a different method. Its code finds the best
  move with a planner, and writes "Safe. Best route to food." into the text
  of that option. The model then matches the word "best". That is against
  the rule of this project, thus we did not do it.

### A local LLM with the answer read from its logits

Two open projects, [jevfire](https://github.com/kikoncuo/jevfire) and
[SemIf](https://github.com/TheoLeeCJ/SemIf), copy the jev interface with an
open LLM. The model gets the state and the question in one chat prompt, and
each option has a one-letter label. The code reads the logits (the scores of
the model for each possible next token) at the first output position, and
changes them into a probability for each label. One pass through the model
is one decision, with no text generation. `jevmanic/local_brain.py` does this
with `mlx-lm` on this computer (`--local`, install with
`uv sync --extra local`). The model gets the same instructions, options, and
JSON state as jev. Qwen3-8B in 4-bit form takes approximately 1.2 s for one
decision, with no cost.

- On the 261 recorded jev decisions, Qwen3-4B selects a "nearer" move in 210
  of 226 (jev: 85 %), the move that collects a key in 16 of 16, and the same
  move as jev in 157 of 261. Qwen3-4B reads the full request. Laya does not.
- In real games (dead end check of 4 moves, one run for each cavern, because
  the model is deterministic), Qwen3-4B got 1, 2, and 0 keys in caverns 1,
  2, and 3. Qwen3-8B got 0 and 2 keys in caverns 1 and 2, and it completed
  The Menagerie in 64 decisions (jev: approximately 80).
- The model is very sure (1.0 against 0.0). Thus, when it makes a loop, it
  repeats the loop until the run ends. Jev gives probabilities between 0 and
  1, and its answers change, thus it can get out of a loop. We sampled the
  answer of the model with a temperature (`LOCAL_TEMPERATURE`, 2 runs for
  each cavern). A temperature of 2 gave Central Cavern 3.5 keys, The Cold
  Room 1.5, and The Menagerie 2, with no complete run. A temperature of 4 was
  worse. A temperature of 1.5 gave Central Cavern 4.5 keys, The Cold Room
  complete in 1 of 2 runs (55 decisions), and The Menagerie 2 keys. Thus a
  random spread of the answers does not give the result of jev. The spread of
  the jev probabilities contains information about the options.

## Open work

- The defaults are worse in some caverns. With the defaults (the key
  decision with the map, a dead end check of 4 moves, 10 runs), cavern 4
  collects 0.0 keys, cavern 9 completes 4 of 10 runs, cavern 11 collects 0.0
  keys, and 9 of 10 runs of cavern 20 end with a death at decision 10. With the
  key decision with the facts only and a dead end check of 12 moves, these
  caverns gave 4.0 keys, 10 of 10, 5 of 10 (3.8 keys), and 4.2 keys. We did
  not measure which of the two settings causes each difference.
- The key order. A good key order needs a plan of the route across the map
  (see "The key decision"). Jev selects the next key well from facts near
  Willy, but it does not plan a route.
- The depth of the dead end check. A different depth, or experience in the
  place of the search: a memory of the places where Willy died in other runs.
- Cavern 4. Each run ends in a trap in the top left corner, because the code
  selects a single tile as "the way up".
- Cavern 8. Willy jumps into the small space between two walls where the
  closed portal is. A walk has no effect there. The only way out is a jump to
  the left, onto the level of a guardian. The look-ahead removes that jump
  each time that the guardian makes it deadly. Then the only valid move is
  `wait`, and the run ends after 30 decisions with no new place. When the
  guardian is away, the jump to the left gets Willy out.
- Cavern 17. Willy moves between the two columns of the start platform. The
  only way forward is `walk_right`, which is "nearer", but jev selects
  `walk_left` with a confidence of 0.31.
