"""The questions that we send to jev, and the calls to jev.

There are two types of request:

1. The key decision. Jev selects the key (or switch) that Willy goes to next.
2. The move decision. Jev selects one macro from the valid moves. The state
   gives the true result of each valid move, from the look-ahead.

The instruction texts are plain text files in `jevmanic/instructions/`. One
folder is one set of instructions:

    free   (the default) The text gives the goal, the meaning of each fact,
           and knowledge of the game. It does not say which option to select.
           The decisions come from jev.
    rules  (for comparison) The text is a numbered list of rules of the form
           "select X when Y". Jev executes a procedure that we wrote.

The instructions are the only difference between two sets: the state, the
options, and the schedule of the requests are the same. To try a new text,
copy a folder, change the files, and run with `--instructions <folder>`.

Each folder has 3 files: `move.txt`, `key.txt` (the key state has the map),
and `key_facts_only.txt` (the key state has no map). `key_memory.txt` goes
after each key text. The line ends in a file have no meaning: jev gets one
paragraph. Jev reads the words as they are, thus do not use markup.

Do not change a text with no measurement. A shorter text and added facts made
the results worse more than one time (see the README).
"""

import time
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path

from typesafe_sdk import AsyncTypeSafeClient, Choice

from .game import MACROS

INSTRUCTIONS_DIR = Path(__file__).resolve().parent / "instructions"
DEFAULT_INSTRUCTIONS = "free"


def instruction_sets() -> list[str]:
    """The names of the instruction folders. The default set is first."""
    names = sorted(p.name for p in INSTRUCTIONS_DIR.iterdir() if (p / "move.txt").exists())
    return sorted(names, key=lambda name: name != DEFAULT_INSTRUCTIONS)


@cache
def _text(relative_path: str) -> str:
    # One paragraph with single spaces: the line ends in the file have no meaning.
    return " ".join((INSTRUCTIONS_DIR / relative_path).read_text().split())


def move_instructions(instructions: str = DEFAULT_INSTRUCTIONS) -> str:
    return _text(f"{instructions}/move.txt")


def key_instructions(instructions: str = DEFAULT_INSTRUCTIONS, with_map: bool = True) -> str:
    """The key text of one set, with the meaning of the short memory of each key after it."""
    name = "key.txt" if with_map else "key_facts_only.txt"
    return _text(f"{instructions}/{name}") + " " + _text("key_memory.txt")


def key_question(names: list[str], instructions: str = DEFAULT_INSTRUCTIONS, with_map: bool = True) -> dict:
    """The Choice question of the key decision. `names` are the option names."""
    criteria = {name: f"The key or switch that `keys.{name}` describes." for name in names}
    return {"key": Choice(instructions=key_instructions(instructions, with_map), criteria=criteria)}


MOVE_CRITERIA = {
    'jump_right': 'Jump to the right. The result is in `moves.jump_right`.',
    'jump_left': 'Jump to the left. The result is in `moves.jump_left`.',
    'walk_right': 'Walk 1 cell to the right. The result is in `moves.walk_right`.',
    'walk_left': 'Walk 1 cell to the left. The result is in `moves.walk_left`.',
    'jump_up': 'Jump straight up. The result is in `moves.jump_up`.',
    'wait': 'Do not move. The result is in `moves.wait`.',
}


def move_question(offered: list[str] | None = None, instructions: str = DEFAULT_INSTRUCTIONS) -> dict:
    """The Choice question of the move decision. `offered` are the valid macros."""
    offered = list(MACROS) if offered is None else offered
    criteria = {name: MOVE_CRITERIA[name] for name in offered}
    return {"move": Choice(instructions=move_instructions(instructions), criteria=criteria)}


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
