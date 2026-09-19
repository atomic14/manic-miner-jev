"""A decision maker that uses an LLM through the `claude` command line tool.

This is for a comparison with jev. The LLM gets the same instructions, the
same options with their criteria, and the same state as jev. It answers with
one option name. The differences from jev:

- The answer is text. The code checks that it is one of the options.
- There are no calibrated probabilities. The selected option gets 1.0.
- The LLM answers only the question that controls Willy. It does not get the
  other questions of the request (danger_left, danger_right, threat).
- A call takes seconds, not a fraction of a second.

The call uses no tools, no project settings, and an empty working folder, thus
the LLM knows only what is in the prompt.
"""

import asyncio
import json
import tempfile
import time

from .brain import Answer

SYSTEM_PROMPT = (
    "You are the decision maker of a program that plays a platform game. "
    "Answer with exactly one option name from the list, and nothing else."
)


def build_prompt(state: dict, question) -> str:
    options = "\n".join(
        f"- {name}: {text}" if text else f"- {name}" for name, text in question.criteria.items()
    )
    return (
        f"{question.instructions}\n\n"
        f"OPTIONS\n{options}\n\n"
        f"STATE\n{json.dumps(state, indent=1)}\n\n"
        "Answer with exactly one option name from the list."
    )


def parse_choice(text: str, options: list[str]):
    """The option that the answer names, or None."""
    cleaned = text.strip().strip("`'\"*. \n").lower()
    for name in options:
        if cleaned == name.lower():
            return name
    # Longest names first, thus "jump_left" does not match "left" by accident.
    found = [name for name in sorted(options, key=len, reverse=True) if name.lower() in cleaned]
    return found[0] if len(found) == 1 else None


class LLMBrain:
    def __init__(self, model: str = "haiku"):
        self.model = model
        self.total_cost = 0.0
        self.invalid_answers = 0
        self._cwd = tempfile.mkdtemp(prefix="jevmanic-llm-")

    async def close(self):
        pass

    async def _call(self, prompt: str) -> dict:
        process = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", self.model, "--system-prompt", SYSTEM_PROMPT,
            "--tools", "", "--setting-sources", "", "--strict-mcp-config",
            "--no-session-persistence", "--output-format", "json",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=self._cwd,
        )
        out, err = await process.communicate(prompt.encode())
        if process.returncode != 0:
            raise RuntimeError(f"claude failed: {err.decode()[:300]}")
        return json.loads(out)

    async def ask(self, state: dict, questions: dict, choice_name: str) -> Answer:
        question = questions[choice_name]
        options = list(question.criteria)
        prompt = build_prompt(state, question)
        start = time.perf_counter()
        tokens, choice, raw = 0, None, ""
        for _ in range(2):  # one more try if the answer is not an option
            reply = await self._call(prompt)
            usage = reply.get("usage", {})
            tokens += usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
            self.total_cost += reply.get("total_cost_usd", 0.0)
            raw = str(reply.get("result", ""))
            choice = parse_choice(raw, options)
            if choice:
                break
            self.invalid_answers += 1
        if choice is None:
            raise RuntimeError(f"the LLM gave no valid option: {raw[:200]!r}")
        return Answer(
            choice=choice,
            # An LLM gives no calibrated probabilities.
            probabilities={name: 1.0 if name == choice else 0.0 for name in options},
            confidence=1.0,
            latency_ms=round((time.perf_counter() - start) * 1000),
            input_tokens=tokens,
            model=f"claude {self.model}",
            request_id="",
            state=state,
        )
