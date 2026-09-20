"""The questions that we send to jev, and the calls to jev.

There are two types of request:

1. The key decision. Jev selects the key (or switch) that Willy goes to next.
2. The move decision. Jev selects one macro from the valid moves. The state
   gives the true result of each valid move, from the look-ahead.

Each type has two texts:

    free mode   (the default) The text gives the goal, the meaning of each
                fact, and knowledge of the game. It does not say which option
                to select. The decisions come from jev.
    rules mode  (for comparison) The text is a numbered list of rules of the
                form "select X when Y". Jev executes a procedure that we
                wrote. The state is the same as in free mode.

Do not change a text with no measurement. A shorter text and added facts made
the results worse more than one time (see the README).
"""

import time
from dataclasses import asdict, dataclass, field

from typesafe_sdk import AsyncTypeSafeClient, Choice

from .game import MACROS

# -- The key decision --------------------------------------------------------------

# The state has the map of the cavern and the facts about each key. A test
# showed that the text must name the map: if not, jev does not use it.
MAP_KEY_INSTRUCTIONS = (
    'Willy is a miner in a platform game. The map shows the cavern, and '
    '`map_legend` tells what each symbol means. `keys` gives facts about each key '
    'or switch relative to Willy. Willy must collect all keys and then go into '
    'the exit portal. Willy can climb only 2 rows with one jump. He can fall to a '
    'lower floor, but after a long fall he cannot climb back. A crumbling floor '
    'breaks when Willy uses it, thus a way that goes across a crumbling floor can '
    'be open only one time. Select the key or switch that Willy gets next, in an '
    'order that lets him get all keys.'
)

# The state has only the facts about each key.
FACTS_KEY_INSTRUCTIONS = (
    'Willy is a miner in a platform game. He must collect all keys. Willy can '
    'climb only 2 rows with one jump. `keys` gives facts about each key or switch '
    'relative to Willy. Select the key or switch that is the best for Willy to '
    'get next.'
)

# Rules mode: our preference rules for the key. The state has only the facts.
RULES_KEY_INSTRUCTIONS = (
    'Willy is a miner in a platform game. He must collect all keys. Select the '
    'key that Willy goes to next. `keys` gives facts about each key relative to '
    'Willy. Willy can climb only 2 rows with one jump, thus a key on a much '
    'higher floor needs a long route. Apply these rules in order. Rule 1: do not '
    'select a key that has `one_way_trip`, if a different key is left. Willy '
    'cannot come back from it, thus it must be the last key. Rule 2: prefer the '
    'key with the smallest `floor_rows_apart`. Rule 3: if two keys are equal, '
    'prefer the key with the smallest `horizontal_cells`.'
)

# The meaning of the short memory of each key. It goes after each key text.
KEY_MEMORY_MEANING = (
    ' `current_target` marks the key that Willy goes to now. Willy can keep it or '
    'change it. `decisions_used_for_it` tells how many decisions Willy used for '
    'this key before. `gave_up_on_it` tells how many times Willy made no progress '
    'toward this key.'
)


def key_question(names: list[str], rules_mode: bool = False, with_map: bool = True) -> dict:
    """The Choice question of the key decision. `names` are the option names."""
    if rules_mode:
        instructions = RULES_KEY_INSTRUCTIONS
    else:
        instructions = MAP_KEY_INSTRUCTIONS if with_map else FACTS_KEY_INSTRUCTIONS
    criteria = {name: f"The key or switch that `keys.{name}` describes." for name in names}
    return {"key": Choice(instructions=instructions + KEY_MEMORY_MEANING, criteria=criteria)}


# -- The move decision --------------------------------------------------------------

FREE_MOVE_INSTRUCTIONS = (
    'Willy is a miner in a platform game. The goal: Willy must collect all keys, '
    'then go into the exit portal, and he must stay alive. The target is the key '
    'that Willy goes to now, or the portal when no key is left. Select the move '
    'that is the best for Willy now. `moves` gives the true result of each '
    'possible move. All moves in `moves` are safe and have an effect. '
    '`moves_not_offered` gives the moves that Willy cannot make now, with the '
    'cause. The meaning of the facts: `progress` tells if a move gets Willy '
    'nearer to the place that `progress_measures` names. `place` tells how '
    'frequently Willy was at the place where the move ends. `tried_from_here` '
    'tells if Willy made this move from this place before. `collects_key` tells '
    'that Willy gets a key with this move. `completes_cavern` tells that Willy '
    'goes into the portal with this move and the cavern is complete. `ends_on` '
    'tells that Willy stands on a crumbling floor after this move, and how much '
    'of that floor is left. `warning` '
    'tells that no move is safe after this move. Knowledge of the game: Willy can '
    'climb only 2 rows with one jump. If Willy comes back to the same places '
    'again and again, the direct way is closed, and he must go a different way, '
    'also if that way goes away from the target first. A crumbling floor breaks a '
    'little each time Willy stands on it. It can be the only way up, and it is '
    'also a way down. A nasty does not move: if it stops a jump, a jump from a '
    'different cell can go over it. A guardian moves along its patrol area: Willy '
    'can wait for it to go away, jump over it, or go out of its patrol area.'
)

RULES_MOVE_INSTRUCTIONS = (
    'Willy is a miner in a platform game. Select the best next move for Willy. '
    'Willy must go to the target. `moves` gives the true result of each move. All '
    'moves in `moves` are safe. `progress` tells if a move gets Willy nearer to '
    'the place that `progress_measures` names. Apply the first rule that matches. '
    'When two moves match the same rule, select the move whose `tried_from_here` '
    'is no, because a move that Willy tried here before did not help. A crumbling '
    'floor breaks a little each time Willy stands on it, and it can be the only '
    'way up. Thus when `target.height` is not lower, do not select wait on a '
    'crumbling floor, and prefer a jump to a walk when the move has `ends_on` '
    'crumbling floor. Rule 1: select a move that has `completes_cavern` or '
    '`collects_key`. Rule 2: when a guardian in `guardians` has `height` same '
    'level, moves toward Willy, and its `horizontal_cells` is 4 or less, select '
    'the jump toward that guardian if that jump is in `moves`, because the jump '
    'goes over the guardian. Do not walk away from it toward a wall. Rule 3: when '
    '`target.way_down.side` is Willy stands on it, select wait, because the '
    'crumbling floor breaks and Willy falls. Rule 4: select a move whose '
    '`progress` is nearer and whose `place` is new place. When `target.height` is '
    'higher, prefer a move that goes higher. When `target.height` is lower, '
    'prefer a move that goes lower. Rule 5: select a move whose `progress` is '
    'nearer. Rule 6: when a move toward the target is in `moves_not_offered` with '
    'the cause guardian, select wait, because a guardian moves away. Rule 7: when '
    'a jump toward the target is in `moves_not_offered` with the cause nasty, '
    'select the walk move that goes away from the target, because a nasty does '
    'not move and a jump from 1 cell farther back can go over it.'
)

MOVE_CRITERIA = {
    'jump_right': 'Jump to the right. The result is in `moves.jump_right`.',
    'jump_left': 'Jump to the left. The result is in `moves.jump_left`.',
    'walk_right': 'Walk 1 cell to the right. The result is in `moves.walk_right`.',
    'walk_left': 'Walk 1 cell to the left. The result is in `moves.walk_left`.',
    'jump_up': 'Jump straight up. The result is in `moves.jump_up`.',
    'wait': 'Do not move. The result is in `moves.wait`.',
}


def move_question(offered: list[str] | None = None, rules_mode: bool = False) -> dict:
    """The Choice question of the move decision. `offered` are the valid macros."""
    offered = list(MACROS) if offered is None else offered
    instructions = RULES_MOVE_INSTRUCTIONS if rules_mode else FREE_MOVE_INSTRUCTIONS
    criteria = {name: MOVE_CRITERIA[name] for name in offered}
    return {"move": Choice(instructions=instructions, criteria=criteria)}


def questions_as_json(questions: dict) -> dict:
    """Questions in the form that the viewer and the log show."""
    return {
        name: {"type": type(q).__name__, "instructions": q.instructions, "criteria": q.criteria}
        for name, q in questions.items()
    }


# -- Calls ----------------------------------------------------------------------------


@dataclass
class Answer:
    """All data of one request. The viewer and the log use this."""

    choice: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: int
    input_tokens: int
    model: str
    request_id: str
    state: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


class Brain:
    """The decision maker that uses jev."""

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
            state=state,
        )
