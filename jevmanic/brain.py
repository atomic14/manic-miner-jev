"""The questions that we send to jev, and the calls to jev.

There are two requests:

1. The target request. Jev selects the key that Willy goes to next. The code
   sends this request at the start, after each collected key, and when Willy
   makes no progress.
2. The move request. Jev selects one macro. The other questions in this
   request do not control Willy. The viewer shows their answers.

The move request has two modes:

    rules       The criteria give exact rules about the state. The code does
                not check a macro before it runs.
    look-ahead  The code tries each macro in the emulator first. The state
                gives the result of each macro. A macro that kills Willy is
                not an option. This is a check of one step, not a search:
                jev selects the target and the move.

The Doom projects showed that jev needs exact rules in the criteria. A
criterion that gives only the purpose of an option does not work. The numbers
in the rules below come from measurements in the emulator.
"""

import time
from dataclasses import asdict, dataclass, field

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score

from .game import MACROS

# -- Target request -------------------------------------------------------------

TARGET_INSTRUCTIONS = (
    "Willy is a miner in a platform game. He must collect all keys. Select the "
    "key that Willy goes to next. `keys` gives facts about each key relative "
    "to Willy. Willy can climb only 2 rows with one jump, thus a key on a much "
    "higher floor needs a long route. Apply these rules in order. "
    "Rule 1: do not select a key that has `one_way_trip`, if a different key "
    "is left. Willy cannot come back from it, thus it must be the last key. "
    "Rule 2: prefer the key with the smallest `floor_rows_apart`. "
    "Rule 3: if two keys are equal, prefer the key with the smallest "
    "`horizontal_cells`."
)


# The target question with no preference rules. Jev must decide from the facts.
FREE_TARGET_INSTRUCTIONS = (
    "Willy is a miner in a platform game. He must collect all keys. Willy can "
    "climb only 2 rows with one jump. `keys` gives facts about each key "
    "or switch relative to Willy. Select the key or switch that is the best "
    "for Willy to get next."
)


def target_question(key_names: list[str], free: bool = False) -> dict:
    criteria = {name: f"The key or switch that `keys.{name}` describes." for name in key_names}
    instructions = FREE_TARGET_INSTRUCTIONS if free else TARGET_INSTRUCTIONS
    return {"target": Choice(instructions=instructions, criteria=criteria)}


# -- Move request, rules mode ----------------------------------------------------

MOVE_INSTRUCTIONS = (
    "Willy is a miner in a platform game. Select the best next move for Willy. "
    "Willy must go to the target. Willy dies if he touches a nasty or a "
    "guardian. A jump moves Willy 4 cells to the side and can reach a platform "
    "that is 1 or 2 rows higher. Apply the first rule that matches the state."
)

MOVE_CRITERIA = {
    "jump_right": (
        "Jump to the right. Correct when a nasty is exactly 2 cells to the right. "
        "Correct when a guardian on the same level is 2 or 3 cells to the right "
        "and moves toward Willy. Correct when the target is higher and "
        "`target.way_up` is on the right, 1 or 2 cells away. Wrong "
        "when a nasty is 1, 3, or 4 cells to the right."
    ),
    "jump_left": (
        "Jump to the left. Correct when a nasty is exactly 2 cells to the left. "
        "Correct when a guardian on the same level is 2 or 3 cells to the left "
        "and moves toward Willy. Correct when the target is higher and "
        "`target.way_up` is on the left, 1 or 2 cells away. Wrong "
        "when a nasty is 1, 3, or 4 cells to the left."
    ),
    "walk_right": (
        "Walk 1 cell to the right. Correct when the target is to the right and "
        "the first thing to the right is 3 or more cells away. Wrong when a "
        "nasty or a guardian on the same level is 1 or 2 cells to the right."
    ),
    "walk_left": (
        "Walk 1 cell to the left. Correct when the target is to the left and "
        "the first thing to the left is 3 or more cells away. Wrong when a "
        "nasty or a guardian on the same level is 1 or 2 cells to the left."
    ),
    "jump_up": (
        "Jump straight up. Correct only when the target is in the same column "
        "as Willy and 1 to 3 rows higher."
    ),
    "wait": (
        "Do not move. Correct only when a guardian on the same level is 4 to 6 "
        "cells away and moves away from Willy, and the target is on that side."
    ),
}

# Criteria for the map encoders in rules mode. A test showed that jev cannot
# count the cells on a map. Thus these criteria give literal patterns that jev
# can find in a map row. The cells of one row have a space between them.
MAP_MOVE_INSTRUCTIONS = (
    "Willy is a miner in a platform game. The map shows the cavern. Willy is "
    "the block of 4 W cells. Select the best next move for Willy. Willy must "
    "collect all keys (K) and then go to the exit portal (P). Willy dies if he "
    "touches a nasty (X) or a guardian (G). A jump moves Willy 4 cells to the "
    "side and can reach a floor that is 1 or 2 rows higher. Look at the two map "
    "rows that contain W. Apply the first rule that matches."
)

MAP_MOVE_CRITERIA = {
    "jump_right": (
        "Jump to the right. Correct when a row with W contains 'W W . . X' or "
        "'W W . . G'. Correct when a row with W contains 'W W . =' or "
        "'W W . . =' or 'W W =', because that is a higher floor that Willy can "
        "jump onto. Wrong when a row with W contains 'W W X' or 'W W . X'."
    ),
    "jump_left": (
        "Jump to the left. Correct when a row with W contains 'X . . W W' or "
        "'G . . W W'. Correct when a row with W contains '= . W W' or "
        "'= . . W W' or '= W W', because that is a higher floor that Willy can "
        "jump onto. Wrong when a row with W contains 'X W W' or 'X . W W'."
    ),
    "walk_right": (
        "Walk 1 cell to the right. Correct when `target.side` is right and no "
        "jump rule matches. Wrong when a row with W contains 'W W . X', "
        "'W W X', 'W W . G', or 'W W G'."
    ),
    "walk_left": (
        "Walk 1 cell to the left. Correct when `target.side` is left and no "
        "jump rule matches. Wrong when a row with W contains 'X . W W', "
        "'X W W', 'G . W W', or 'G W W'."
    ),
    "jump_up": (
        "Jump straight up. Correct only when a K is directly above the W cells, "
        "1 to 3 rows higher."
    ),
    "wait": (
        "Do not move. Correct only when a row with W contains G and the G "
        "cells are 4 or more cells from the W cells."
    ),
}

MAP_ONLY_ENCODERS = ("ascii_local", "ascii_full")

# -- Move request, look-ahead mode -------------------------------------------------

LOOK_AHEAD_INSTRUCTIONS = (
    "Willy is a miner in a platform game. Select the best next move for Willy. "
    "Willy must go to the target. `moves` gives the true result of each move. "
    "All moves in `moves` are safe. `progress` tells if a move gets Willy "
    "nearer to the place that `progress_measures` names. Apply the first rule "
    "that matches. When two moves match the same rule, select the move whose "
    "`tried_from_here` is no, because a move that Willy tried here before did "
    "not help. A crumbling floor breaks a little each time Willy stands on "
    "it, and it can be the only way up. Thus when `target.height` is not "
    "lower, do not select wait on a crumbling floor, and prefer a jump to a "
    "walk when the move has `ends_on` crumbling floor. "
    "Rule 1: select a move that has `completes_cavern` or `collects_key`. "
    "Rule 2: when a guardian in `guardians` has `height` same level, moves "
    "toward Willy, and its `horizontal_cells` is 4 or less, select the jump "
    "toward that guardian if that jump is in `moves`, because the jump goes "
    "over the guardian. Do not walk away from it toward a wall. "
    "Rule 3: when `target.way_down.side` is Willy stands on it, select wait, "
    "because the crumbling floor breaks and Willy falls. "
    "Rule 4: when each move whose `progress` is nearer has the `place` visited "
    "many times, or when no move has the `progress` nearer, Willy is in a "
    "loop and the direct way is closed. Select a move that has "
    "`least_visited_option` yes, also when its `progress` is farther, because "
    "Willy must find a different way. "
    "Rule 5: select a move whose `progress` is nearer and whose `place` is new "
    "place. When `target.height` is higher, prefer a move that goes higher. "
    "When `target.height` is lower, prefer a move that goes lower. "
    "Rule 6: select a move whose `progress` is nearer. "
    "Rule 7: when a move toward the target is in `moves_not_offered` with "
    "the cause guardian, select wait, because a guardian moves away. "
    "Rule 8: when a jump toward the target is in `moves_not_offered` with "
    "the cause nasty, select the walk move that goes away from the target, "
    "because a nasty does not move and a jump from 1 cell farther back can go "
    "over it. "
    "Rule 9: select a move that has `least_visited_option` yes."
)

# The move question with no decision procedure. It gives the goal, the meaning
# of the facts, and knowledge of the game. It does not say "select X when Y":
# the decision must come from jev.
FREE_MOVE_INSTRUCTIONS = (
    "Willy is a miner in a platform game. He must get to the target, and he "
    "must stay alive. Select the move that is the best for Willy now. "
    "`moves` gives the true result of each possible move. All moves in `moves` "
    "are safe and have an effect. `moves_not_offered` gives the moves that "
    "Willy cannot make now, with the cause. "
    "The meaning of the facts: `progress` tells if a move gets Willy nearer to "
    "the place that `progress_measures` names. `place` tells how frequently "
    "Willy was at the place where the move ends. `tried_from_here` tells if "
    "Willy made this move from this place before. "
    "Knowledge of the game: Willy can climb only 2 rows with one jump. If "
    "Willy comes back to the same places again and again, the direct way is "
    "closed, and he must go a different way, also if that way goes away from "
    "the target first. A crumbling floor breaks a little each time Willy "
    "stands on it. It can be the only way up, and it is also a way down. A "
    "nasty does not move: if it stops a jump, a jump from a different cell "
    "can go over it. A guardian moves along its patrol area: Willy can wait "
    "for it to go away, jump over it, or go out of its patrol area."
)

LOOK_AHEAD_CRITERIA = {
    "jump_right": "Jump to the right. The result is in `moves.jump_right`.",
    "jump_left": "Jump to the left. The result is in `moves.jump_left`.",
    "walk_right": "Walk 1 cell to the right. The result is in `moves.walk_right`.",
    "walk_left": "Walk 1 cell to the left. The result is in `moves.walk_left`.",
    "jump_up": "Jump straight up. The result is in `moves.jump_up`.",
    "wait": "Do not move. The result is in `moves.wait`.",
}

# -- Other questions in the move request --------------------------------------------

EXTRA_QUESTIONS = {
    "danger_right": Noul(
        instructions=(
            "If Willy walks 2 cells to the right now, does he touch a nasty "
            "or a guardian, or fall from an edge?"
        )
    ),
    "danger_left": Noul(
        instructions=(
            "If Willy walks 2 cells to the left now, does he touch a nasty "
            "or a guardian, or fall from an edge?"
        )
    ),
    "threat": Score(
        instructions="How large is the threat to Willy at this moment?",
        criteria=[
            "No nasty and no guardian is near Willy.",
            "A nasty or a guardian is near, but it is not in the path of Willy.",
            "A nasty or a guardian is in the path of Willy and 3 or more cells away.",
            "A nasty or a guardian is 1 or 2 cells from Willy on his level.",
        ],
    ),
}


def move_questions(encoder: str, look_ahead: bool, offered=None, extras: bool = True, free: bool = False) -> dict:
    """The questions of one move request.

    `offered` is the list of macros that jev can select. In look-ahead mode
    it does not contain the macros that kill Willy.
    """
    if look_ahead:
        instructions = FREE_MOVE_INSTRUCTIONS if free else LOOK_AHEAD_INSTRUCTIONS
        criteria = LOOK_AHEAD_CRITERIA
    elif encoder in MAP_ONLY_ENCODERS:
        instructions, criteria = MAP_MOVE_INSTRUCTIONS, MAP_MOVE_CRITERIA
    else:
        instructions, criteria = MOVE_INSTRUCTIONS, MOVE_CRITERIA
    offered = list(MACROS) if offered is None else offered
    move = Choice(instructions=instructions, criteria={m: criteria[m] for m in offered})
    return {"move": move, **(EXTRA_QUESTIONS if extras else {})}


def questions_as_json(questions: dict) -> dict:
    """Questions in the form that the viewer and the log show."""
    return {
        name: {
            "type": type(q).__name__,
            "instructions": q.instructions,
            "criteria": getattr(q, "criteria", None),
        }
        for name, q in questions.items()
    }


# -- Calls ----------------------------------------------------------------------------


@dataclass
class Answer:
    """All data of one jev request. The viewer and the log use this."""

    choice: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: int
    input_tokens: int
    model: str
    request_id: str
    nouls: dict[str, float] = field(default_factory=dict)
    scores: dict[str, dict] = field(default_factory=dict)
    state: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


class Brain:
    def __init__(self):
        self.client = AsyncTypeSafeClient()

    async def close(self):
        await self.client.aclose()

    async def ask(self, state: dict, questions: dict, choice_name: str) -> Answer:
        start = time.perf_counter()
        result = await self.client.system_one(state, questions)
        latency_ms = round((time.perf_counter() - start) * 1000)
        choice = result.choices[choice_name]
        return Answer(
            choice=choice.choice,
            probabilities=dict(choice.probabilities),
            confidence=choice.confidence,
            latency_ms=latency_ms,
            input_tokens=result.usage.input_tokens,
            model=result.model,
            request_id=result.request_id or "",
            nouls={k: v.noul for k, v in result.nouls.items()},
            scores={
                k: {"score": v.score, "confidence": v.confidence}
                for k, v in result.scores.items()
            },
            state=state,
        )
