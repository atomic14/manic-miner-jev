# A reasoning model as the planner

This document records one test: a reasoning model makes the plan for a
cavern, and jev makes each move decision.

## Why we did this test

Jev selects a good **first** key from the map. It does not reliably give the
full key order, because a later decision can need the route across several
floors. That is reasoning of more than one step, and jev is not made for it.
A reasoning model is made for it. TypeSafe describes this division: a System
Two model plans, and a System One model (jev) makes the fast decisions.

## The method

We started a clean subagent (a reasoning model, Claude) with one message.

- It got only: the maps of caverns 1 to 4, the legend, the patrol limits of
  the guardians, the conveyor directions, and the game mechanics.
- It got no results of this project and no key orders.
- The message told it not to read files, not to search the web, not to use
  tools, and not to use published walkthroughs.
- It used approximately 72,000 tokens and 7 minutes for the four caverns.

The game mechanics in the message:

- The map is a grid of 32 columns and 16 rows. Row 0 is the top.
- Willy is 2 cells wide and 2 cells high. He stands on the row directly below
  his block.
- Willy can walk left and right. He can jump straight up, to the left, or to
  the right.
- A jump rises approximately 2.5 rows and moves Willy 4 to 5 cells to the
  side. With a jump, Willy can land on a surface that is 1 or 2 rows higher.
- With a jump, Willy can collect a key that hangs up to approximately 4 rows
  above the surface he stands on.
- Floor, crumbling floor, and conveyor cells do not stop Willy from below or
  from the side. Only wall cells stop him. He can stand on top of a wall.
- A fall of up to approximately 4 rows is safe. A longer fall kills Willy.
- A crumbling floor cell breaks a little each time Willy stands on it, and
  then it is gone. It can also be a way down.
- A conveyor moves Willy in its direction.
- A nasty does not move and kills on contact. Willy can jump over one nasty.
- A guardian patrols between two columns and kills on contact.
- Willy can enter the portal only when he has all keys.
- The air supply is limited, thus a short route is important.

The maps in the message:

```
CAVERN 1: Central Cavern
    01234567890123456789012345678901   (column numbers, last digit)
 0  #........A.X....X............B.#
 1  #...............C..............#
 2  #..............................#
 3  #..............................#
 4  #......................XD..X...#
 5  #=============~~~~=~~~~========#
 6  #.............................E#
 7  #===.........GG................#
 8  #............GG..###.X.........#
 9  #====...<<<<<<<<<<<<<<<<<<<<...#
10  #............................==#
11  #..............................#
12  #...........X.......###~~~~~===#
13  #.WW.===============.........PP#
14  #.WW.........................PP#
15  #==============================#
Horizontal guardians (the map shows the present position):
  - rows 7-8, moves between column 8 and column 16
Conveyor direction: moves Willy to the left

CAVERN 2: The Cold Room
    01234567890123456789012345678901   (column numbers, last digit)
 0  #..................#############
 1  #......A................B.....X#
 2  #..............................#
 3  #................GG..~~~=......#
 4  #................GG............#
 5  #===================........#..#
 6  #....................====#~~#..#
 7  #=~~~~~..................#C.#..#
 8  #........................#~~#..#
 9  #..D.....=======.........#~~#..#
10  #..................~~~~..#~~#..#
11  #..>>>>..................#~~#..#
12  #.............====.E.....#~~#..#
13  #.WW....~~~~................GPP#
14  #.WW........................GPP#
15  #==============================#
Horizontal guardians (the map shows the present position):
  - rows 3-4, moves between column 1 and column 19
  - rows 13-14, moves between column 12 and column 30
Conveyor direction: moves Willy to the right

CAVERN 3: The Menagerie
    01234567890123456789012345678901   (column numbers, last digit)
 0  #.....A...X....B.......C...X...#
 1  #.................X............#
 2  #..............................#
 3  #..............GG..GG..........#
 4  #..............GG..GG..........#
 5  #====~~~~~~~~~~~~~~~~~~~~~~~~~~#
 6  #....................E........D#
 7  #======....................====#
 8  #..............................#
 9  #.....<<<<<<...................#
10  #........................======#
11  #X............=====..........PP#
12  #....======..................PP#
13  #.WW..............GG.==========#
14  #.WW..............GG...........#
15  #==============================#
Horizontal guardians (the map shows the present position):
  - rows 13-14, moves between column 1 and column 20
  - rows 3-4, moves between column 1 and column 17
  - rows 3-4, moves between column 18 and column 30
Conveyor direction: moves Willy to the left

CAVERN 4: Abandoned Uranium Workings
    01234567890123456789012345678901   (column numbers, last digit)
 0  #A.....X......##################
 1  #...........B............C...PP#
 2  #............................PP#
 3  #..................======......#
 4  #..........................====#
 5  #=.....=.........=.............#
 6  #...........==..D....===......E#
 7  #~~~...........................#
 8  #......==.................===..#
 9  #.................===..........#
10  #>>>..........................=#
11  #...........===.......===......#
12  #.....==...............X....===#
13  #.GG....GG........==.........WW#
14  #.GG....GG...................WW#
15  #==============================#
Horizontal guardians (the map shows the present position):
  - rows 13-14, moves between column 1 and column 11
  - rows 13-14, moves between column 6 and column 16
Conveyor direction: moves Willy to the right
```

## The answer of the subagent

| Cavern | Key order | What we know |
| --- | --- | --- |
| 1 Central Cavern | **E A C D B** | the known good order from earlier search work |
| 2 The Cold Room | **E D A B C** | the most frequent order of our complete runs (36 of 52) |
| 3 The Menagerie | **A B C D E** (E A B C D as an alternative) | our complete runs: E A B C D 55 times, A B C D E 4 times |
| 4 Abandoned Uranium Workings | **E D A B C** | our 2 complete runs: D E C B A |

It gave "medium" as its confidence for each cavern, and it said that it did
not play the routes.

### Cavern 1, Central Cavern: E A C D B

Reasons:

- From the ground floor, Willy can reach only the row 13 platform. He can
  reach the top floor (row 5) only from the far left: the row 9 floor, then
  the row 7 ledge, then row 5.
- E is on the only way up, which is the right side, thus it is first. Willy
  then meets the top keys in the order A, C, D, B while he walks right.
- The row 5 floor goes across the full cavern, thus the only way down is
  through its crumbling cells. Columns 19 to 20 are the only safe drop: it
  lands on the wall block. Columns 20 to 22 fall onto the nasty at column 21.

Route plan: Jump onto the row 13 platform, go right over the nasty at column
12, up onto the wall block (columns 20 to 22), across the crumbling cells to
the row 12 floor, then up to the row 10 ledge, and jump straight up for E.
Jump left onto the conveyor, over the nasty at column 21, onto the wall block
(columns 17 to 19), over the guardian, and ride the conveyor left to the row
9 floor. Climb to the row 7 ledge and up to the row 5 floor. Walk right along
row 5: jump for A, jump for C, over the crumbling gaps, over the nasty at
column 23 to land on D, over the nasty at column 27, and jump for B. Go back
left, stand on the crumbling columns 19 to 20 to drop onto the wall block,
and go right along the conveyor to the row 10 ledge. Step down to the row 12
floor, drop through the crumbling cells to the ground, and walk right into
the portal.

### Cavern 2, The Cold Room: E D A B C

Reasons:

- C is in a walled chimney (columns 26 to 27). Willy can reach it only from
  the top, through its crumbling floors. That drop ends on the ground 2 to 3
  cells from the portal, thus C is the last key.
- B is on the way to the top of the chimney, and A is on the row 5 floor
  immediately before B.
- Willy touches D when he stands on the conveyor at columns 3 to 4, on the
  way up.
- Willy can reach E only at ground level. If E is last, he must go through
  the patrol of the ground guardian two times after he lands next to the
  portal. Thus E is first.

Route plan: Jump onto the row 13 crumbling floor, jump right to the row 12
platform, wait for the ground guardian to pass, then walk off the right end
and fall through E to the ground. Go back left, jump onto crumbling cells at
row 13 that are not used, jump left onto the conveyor, and go left to columns
3 to 4 to touch D. Ride the conveyor right and jump to the row 9 floor, jump
left to the row 7 crumbling ledge, and jump straight up to the row 5 floor
when the top guardian has passed. Jump for A, run right to columns 18 to 19,
jump onto the row 3 crumbling floor, and walk to column 24 for B. Walk off
the right end onto the top of the chimney (row 6), stand on columns 26 to 27,
and let the crumbling floors break one after the other. Willy collects C on
the way down. Walk 2 to 3 cells right into the portal.

### Cavern 3, The Menagerie: A B C D E

Reasons:

- Willy can reach the right-side ledges (row 7 and row 10) only from above,
  thus the route is: up the left, across the top, down the right.
- That gives A, B, C along the crumbling top floor, then D when the top floor
  breaks at columns 29 to 30 and Willy lands on the row 7 ledge.
- Willy cannot get E from directly above. A drop through the top floor at
  columns 20 to 22 is a fall of approximately 8 rows, which kills him.
- Willy gets E at the top of a jump to the right from the right end of the
  row 11 platform. That jump lands on the row 13 floor that goes to the
  portal.
- E first, from the same platform, costs approximately the same. Thus
  E A B C D is an alternative order.

Route plan: Walk right along the ground floor, jump over the ground guardian,
and jump up to the row 13 floor at column 21. Jump left to the row 11
platform, left to the conveyor, ride it left, jump to the row 7 floor, and
jump up to the row 5 floor at columns 1 to 4. Go across the crumbling top
floor from left to right with no stop, in time with the two guardians: jump
straight up for A, B, and C, and keep away from the nasties at columns 10,
18, and 27. Stand on the crumbling columns 29 to 30 until they break, drop
onto the row 7 ledge, and touch D. Walk off to the left down to the row 10
floor, then off its left end down to the row 13 floor. Jump left to the row
11 platform and jump right from its right end to get E at the top of the
jump. Land on row 13 and walk right into the portal.

### Cavern 4, Abandoned Uranium Workings: E D A B C

Reasons:

- E is near the start, and its ledges (row 12, row 10, row 8, then row 6) are
  also a way up.
- D is low. Willy cannot get it from above, because a fall from there kills
  him. He cannot get back up from the row 9 platform to row 6, thus he must
  get D before the final climb.
- Willy gets D with a jump to the left from the left end of the row 9
  platform, and he lands on the row 11 platform.
- A is then at the end of a chain of ledges along the left side. B is a
  straight jump up on the row 6 platform on the way back to the right. C is
  at the right end of the row 3 platform, one jump from the portal ledge.

Route plan: Walk left below the nasty at column 23, jump left from column 21
onto the row 13 step, jump right onto the row 11 platform (columns 22 to 24),
jump right down to the row 12 floor, jump up to the row 10 block at column
30, and jump straight up for E. Jump left to the row 8 platform, left to the
row 6 platform (columns 21 to 23), and walk off its left end down to the row
9 platform. Jump left from its left end to collect D in the air and land on
the row 11 platform (columns 12 to 14). Go left along row 12, the conveyor,
row 8, and the crumbling ledge at row 7, then jump up to the row 5 block at
column 1 and jump straight up for A. Drop back to the crumbling ledge and
jump right to the row 5 block at column 7. Jump right to the row 6 platform
(columns 12 to 13) and jump straight up for B. Jump right to the row 5 block
at column 17 and up to the row 3 platform, walk to column 24 for C, then jump
right down to the row 4 ledge and walk into the portal.

## The test in play

We used only the key order of the subagent. The code set it with the switch
`key-order`, and jev got no key request. Jev made each move decision with the
normal movement, which we did not change. We did not give the route plan to
jev. 10 live runs for each cavern.

| Cavern | Order | Complete | Decisions | The default configuration |
| --- | --- | --- | --- | --- |
| 1 Central Cavern | E A C D B | 7 of 10 | 74 | 8 to 10 of 10, 70 to 75 decisions |
| 2 The Cold Room | E D A B C | 6 of 10 | 76 | 4 to 6 of 10, 95 to 122 decisions |
| 3 The Menagerie | A B C D E | 9 of 10 | 54 | 10 of 10, 64 to 66 decisions |
| 4 Abandoned Uranium Workings | E D A B C | 0 of 10, 4.2 keys | - | 0 of 10, 3.6 to 4.0 keys |

## What we learned

- The reasoning model gives a good key order from the map only, with reasons
  that need more than one step ("the top floor can only be reached from the
  far left"). For Central Cavern it found the known good order.
- A better key order makes the runs shorter (The Cold Room 76 decisions and
  not 95 to 122, The Menagerie 54 and not 66). It does not make more runs
  complete.
- Thus the key order is not the limit. The limit is the movement layer: the
  facts that tell jev how to get to the selected key.
- We did not test the route plan as a fact in the jev state. That is a
  possible next step.
- 10 runs cannot separate results that are near. The same configuration
  (order E A C D B in Central Cavern) gave 10 of 10 in one measurement and 7
  of 10 in the next one.

The summaries of the measurements are in `experiments/results/`
(`planner-order-cavern-*.json` and `planner-subagent-orders.json`).
