"""The questions that we send to jev, and the jev requests.

There are two types of decision:

1. The key decision. Jev selects the key (or switch) that Willy goes to next.
2. The move decision. Jev selects one of the valid moves. The state gives the
   true result of each valid move, from the look-ahead.

The texts are plain text files in `jevmanic/instructions/`. Each folder is one
instruction set:

    promptD  (the default) The text gives the goal, the meaning of each
             fact, and knowledge of the game. It does not say which option to
             select.
    promptA  The same text, but it says that each move in `moves` is safe
             and has an effect. That is not always true. The results in the
             README come from this set.
    promptC  A very short text for Laya (laya_brain.py).

Two sets differ only in their texts: the state, the options, and the request
schedule are the same. To try a new text, copy a folder, change the files, and
run with `--instructions <folder>`. The viewer's Instruction sets page can
also save a new set. It cannot change a set in FIXED_SETS.

Each folder has 3 files: `move.txt`, `key.txt` (the key decision's state has
the map), and `key_facts_only.txt` (the state has no map). `key_memory.txt`
goes after each key text. Line ends in a file have no meaning: jev gets one
paragraph. Jev reads the words as they are, so do not use markup.

Measure each change to a text. Changes that looked harmless have made the
results worse; see "A shorter text was worse" in docs/findings.md.
"""

import re
import time
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path

from typesafe_sdk import AsyncTypeSafeClient, Choice

from .game import MACROS

INSTRUCTIONS_DIR = Path(__file__).resolve().parent / "instructions"
DEFAULT_INSTRUCTIONS = "promptD"


def instruction_sets() -> list[str]:
    """The names of the instruction sets, with the default set first."""
    names = sorted(p.name for p in INSTRUCTIONS_DIR.iterdir() if (p / "move.txt").exists())
    return sorted(names, key=lambda name: name != DEFAULT_INSTRUCTIONS)


# The files of one set, and the sets that the viewer cannot change: the default, the
# set of the README results, and the set for Laya. To change one, save a new set.
SET_FILES = ("move.txt", "key.txt", "key_facts_only.txt")
FIXED_SETS = ("promptA", "promptC", "promptD")
SET_NAME = re.compile(r"[A-Za-z0-9_-]{1,40}")


def instruction_files(name: str) -> dict[str, str]:
    """The texts of one set exactly as they are on disk, with their line ends."""
    return {file: (INSTRUCTIONS_DIR / name / file).read_text() for file in SET_FILES}


def save_instruction_set(name: str, texts: dict[str, str], replace_set: bool = False):
    """Write a new instruction set. Raises ValueError for a fixed set or a bad name."""
    if not SET_NAME.fullmatch(name):
        raise ValueError("a set name has 1 to 40 letters, digits, '-' or '_'")
    if name in FIXED_SETS:
        raise ValueError(f"{name} is a fixed set. Save your text as a new set")
    folder = INSTRUCTIONS_DIR / name
    if folder.exists() and not replace_set:
        raise FileExistsError(f"the set {name} exists")
    missing = [file for file in SET_FILES if not str(texts.get(file, "")).strip()]
    if missing:
        raise ValueError("each text must have words: " + ", ".join(missing))
    folder.mkdir(exist_ok=True)
    for file in SET_FILES:
        (folder / file).write_text(str(texts[file]).strip() + "\n")
    _text.cache_clear()


@cache
def _text(relative_path: str) -> str:
    # One paragraph with single spaces: the line ends in the file have no meaning.
    return " ".join((INSTRUCTIONS_DIR / relative_path).read_text().split())


def move_instructions(instructions: str = DEFAULT_INSTRUCTIONS) -> str:
    return _text(f"{instructions}/move.txt")


def key_instructions(instructions: str = DEFAULT_INSTRUCTIONS, with_map: bool = True) -> str:
    """The key decision's text of one set, followed by the text that explains the key memory."""
    name = "key.txt" if with_map else "key_facts_only.txt"
    text = _text(f"{instructions}/{name}") + " " + _text("key_memory.txt")
    # `gave_up_on_it` is only in the state of the key decision with the facts only.
    return text if with_map else text + " " + _text("key_memory_facts_only.txt")


def key_question(names: list[str], instructions: str = DEFAULT_INSTRUCTIONS, with_map: bool = True) -> dict:
    """The key decision's Choice question. `names` are the option names."""
    criteria = {name: f"The key or switch that `keys.{name}` describes." for name in names}
    return {"key": Choice(instructions=key_instructions(instructions, with_map), criteria=criteria)}


MOVE_CRITERIA = {
    'jump_right': 'Jump to the right. The result is in `moves.jump_right`.',
    'jump_left': 'Jump to the left. The result is in `moves.jump_left`.',
    'walk_right': 'Walk to the right. The result is in `moves.walk_right`.',
    'walk_left': 'Walk to the left. The result is in `moves.walk_left`.',
    'jump_up': 'Jump straight up. The result is in `moves.jump_up`.',
    'wait': 'Do not move. The result is in `moves.wait`.',
}


def move_question(offered: list[str] | None = None, instructions: str = DEFAULT_INSTRUCTIONS) -> dict:
    """The move decision's Choice question. `offered` are the valid moves."""
    offered = list(MACROS) if offered is None else offered
    criteria = {name: MOVE_CRITERIA[name] for name in offered}
    return {"move": Choice(instructions=move_instructions(instructions), criteria=criteria)}


def questions_as_json(questions: dict) -> dict:
    """Questions as JSON, in the form that the viewer and the log file show."""
    return {
        name: {"type": type(q).__name__, "instructions": q.instructions, "criteria": q.criteria}
        for name, q in questions.items()
    }


# -- Calls ----------------------------------------------------------------------------


@dataclass
class Answer:
    """Jev's answer to one request, with the state that it got. The log file keeps all of it."""

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
        """Send one request to jev, and return the answer to the question `choice_name`.

        The other decision makers (llm_brain.py, laya_brain.py, local_brain.py)
        have the same method.
        """
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
