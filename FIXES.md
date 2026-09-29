# Project review fixes

Reviewed on 29 September 2026, including the uncommitted changes.

The two recorded default experiments completed 67 of 400 runs. Another 268
stopped for no progress, and 65 ended in death. Navigation and loops need
the most attention. The existing 35 tests passed during the review.

## High: misleading height and progress

Status: done. `describe._target_relative` calls a target `higher` when it
hangs above Willy's jump reach (3 rows above his head, measured in the
emulator). `progress` then measures the distance to the way up. Tests:
the recorded cavern 4 state, and keys 3 and 4 rows above Willy's head.

In cavern 4, Willy at `(16, 13)` targets a key at `(16, 6)`. The harness
calls the key "same level" and labels a jump two rows upward "farther".
Height compares the floors below objects, even when the key hangs beyond
Willy's jump reach. The progress calculation then discards vertical distance.

- Code: `describe._relative`, `describe._progress_reference`, and `describe.moves_state`.
- Fix: account for the target's actual height and Willy's jump reach.
  Preserve the distinction between hanging keys within reach and targets
  that require a higher platform.
- Verify: replay the recorded failure and test reachable hanging keys,
  higher targets, and the resulting progress facts.

## High: different outcomes treated as equivalent or ineffective

Status: done. A move has no effect only if another move gives the same game:
the same snapshot, pixel position, and time (`Outcome.same_result`). The
runner forces a move only when one move is left. Tests: the recorded
conveyor state, the stationary jump on a crumbling floor, and moves in the
air (`jump_left` and `jump_right` now stay, because they change the landing).
The promptD texts and `docs/design.md` describe the new rule.

The runner compares only position, keys collected, and completion before
forcing a move. In Central Cavern, walking and waiting reach the same cell
but leave a guardian moving in opposite directions. They also consume
different amounts of time and air. The harness chooses without asking Jev.

The move filter also removes stationary jumps that change crumbling floors.
Remaining in the same cell does not establish that a move has no effect.

- Code: `_LiveRun.move_decision` and `describe.moves_state`.
- Fix: retain choices that can change timing, facing, guardians, or terrain.
  Force a move only when there is no meaningful choice.
- Verify: replay the conveyor example and the stationary crumbling-floor
  jump. Test that the decision maker receives the distinct choices.

## Medium: incomplete searches reported as proven dead ends

Status: done. `Game._can_survive` returns True, False, or None (the search
stopped). Only False removes a move. On the 21 recorded states, the look-ahead
is the same as before. With this rule, the soft-lock check could prove a
trap only when every sequence kills Willy, so we removed it. In 101 recorded
situations (the failure states and The Menagerie), no search ran out of
budget, at a depth of 4 or of 8.

The survival search returns false when its budget runs out. The harness
then reports that the move kills Willy. The new soft-lock check likewise
treats failure to escape within five moves as proof of a trap.

- Code: `Game._can_survive`, `Game._can_leave`, and `Game.look_ahead`.
- Fix: distinguish proven failure, a surviving continuation, and an
  inconclusive search. Do not remove moves merely because search stopped.
- Evidence limit: the review found no budget exhaustion in its sampled
  default-depth states. This risk does not explain those recorded failures.

## Medium: request checks do not validate the experiment's actual states

Status: done. The checks build states and the look-ahead from the run's
`Settings`. They also replay one failure state from each cavern
(`tests/fixtures/failure_states.json`, from `runs/x-jev-own`), and they check
the move filter and the target height against the look-ahead. Limit: the
checks do not test `way_up` or `way_down` in the emulator. That needs a way
to put Willy at the named cell.

The checks replay successful runs from three caverns. They check movement
and key collection, but not navigation, move filtering, or forced choices.
They build default states rather than applying the supplied settings.
For example, disabling progress still passes with a prompt that references it.

- Code: `checks.text_problems`, `checks.after_move_problems`, and `checks.measurement_problems`.
- Fix: pass the complete settings through state construction and look-ahead.
  Add recorded failure states from all caverns and checks of navigation facts.

## Medium: the viewer requires an API key for offline replays

Status: done. `Brain` creates its client at the first request.
`tests/test_viewer.py` lists and replays a run with no API key.

Listing runs creates `Brain()`, as does opening a replay session. Without
an API key, `/api/runs` raises `TypeSafeError`. This contradicts the quick start.

- Code: `server._lab_parts`, `server.Session`, and `brain.Brain`.
- Fix: create the API client only when a live request needs it.
- Verify: list saved runs and replay one with no API key configured.

## Medium: the ladder setting leaks between concurrent runs

Status: done. `Settings` moved to `jevmanic/settings.py`. The state builders
take the run's settings, and there is no module variable. A test interleaves
the two settings on the Ore Refinery state.

`play_live` assigns a run's ladder setting to the global `describe.LADDER_FIX`.
Another run can overwrite it while the first run still uses its original
logged settings. Comparisons in one process can therefore mix settings.

- Code: `runner.play_live` and `describe._room_above`.
- Fix: pass the setting explicitly through each run's state construction.
- Verify: interleave runs with different ladder settings and compare each
  with its isolated execution.

## Follow-up experiment design

Status: done. The two High fixes were measured together on caverns
1, 4, and 6 (`docs/findings.md`, "The target height and the move filter").
Then each fix alone, in all 20 caverns ("Each change alone, in all caverns"):
25 complete runs of 200 before, 30 with the height fix, 31 with the filter,
32 with both. No total difference is measurable. The height fix helps cavern
4 clearly. In cavern 12 it makes the key order worse, through a true fact.
The cavern 6 loss did not repeat.

For representative failures, establish whether the available moves and
filters permit progress. Use an offline search or a known successful route.
Separate inaccurate facts, removed actions, and poor model choices.

Keep the matched rule comparisons, but interpret them within the harness's
limits. Record measurements of the high-priority fixes in `docs/findings.md`.
Historical completion rates describe the code used for those experiments.
