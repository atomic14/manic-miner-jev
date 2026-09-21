"""A decision maker that uses Laya, a typed decision model that runs on this computer.

Laya (https://github.com/mizorewww/laya-mlx) has the same form of request as
jev: a state, and typed questions with instructions and criteria. It runs on
Apple Silicon with MLX. It makes no network call and has no cost.

This is for a comparison with jev. Laya gets the same instructions, the same
options, and the same state as jev. The important difference is the size of
the input:

- The instructions and the options together get 256 tokens at most. Laya cuts
  the end of the instructions to make them fit.
- The full input gets 1024 tokens at most. Laya cuts the end of the state.

Laya does this with no message. Thus this class counts what was cut, and
`cut_report()` gives the totals. A long instruction text (promptA has 400
tokens) loses most of its content.

Install:  uv sync --extra laya
"""

import time

from .brain import Answer

DEFAULT_MODEL = "aac6fef/laya-typed-decisions-mlx"  # context of 1024 tokens


class LayaBrain:
    def __init__(self, model: str = DEFAULT_MODEL):
        import laya_mlx  # an optional dependency

        self.model = f"laya {model.split('/')[-1]}"
        self.maker, self.mode = self.model, "laya"
        self.agent = laya_mlx.load(model)
        self.total_cost = 0.0
        self.requests = 0
        self.cut_instructions = 0  # requests in which Laya cut the instructions
        self.cut_state = 0  # requests in which Laya cut the state
        self.worst = {"instruction_tokens_lost": 0, "state_tokens_lost": 0}

    async def close(self):
        pass

    def _count_cuts(self, state, question: dict):
        """Count the tokens that Laya removes from this request."""
        from laya_mlx.common import build_prefix, serialize_state

        cfg, tok = self.agent.cfg, self.agent.tok
        max_len, head_len = cfg.get("max_len", 512), cfg.get("head_max_len", 192)
        internal = {"t": question["type"], "ins": question["instructions"], "crit": question["criteria"]}
        prefix, _ = build_prefix(tok, internal, head_len)
        wanted = len(tok(f"{question['type']} question: {question['instructions']}", add_special_tokens=False)["input_ids"])
        options = sum(1 + min(48, len(tok(" " + f"{k}: {v}", add_special_tokens=False)["input_ids"]))
                      for k, v in question["criteria"].items())
        kept = len(prefix) - 3 - options  # 3 = the CLS token and 2 SEP tokens
        lost_instructions = max(0, wanted - kept)
        state_tokens = len(tok(serialize_state(state), add_special_tokens=False)["input_ids"])
        lost_state = max(0, state_tokens - (max_len - len(prefix) - 1))
        self.cut_instructions += lost_instructions > 0
        self.cut_state += lost_state > 0
        self.worst["instruction_tokens_lost"] = max(self.worst["instruction_tokens_lost"], lost_instructions)
        self.worst["state_tokens_lost"] = max(self.worst["state_tokens_lost"], lost_state)

    def cut_report(self) -> str:
        return (f"Laya cut the instructions in {self.cut_instructions} of {self.requests} requests "
                f"(at most {self.worst['instruction_tokens_lost']} tokens lost), and the state in "
                f"{self.cut_state} requests (at most {self.worst['state_tokens_lost']} tokens lost).")

    async def ask(self, state: dict, questions: dict, choice_name: str) -> Answer:
        q = questions[choice_name]
        question = {"type": "choice", "instructions": q.instructions, "criteria": dict(q.criteria)}
        self.requests += 1
        self._count_cuts(state, question)
        start = time.perf_counter()
        result = self.agent.predict(state, {choice_name: question})
        latency_ms = round((time.perf_counter() - start) * 1000)
        answer = result["answers"][choice_name]
        return Answer(
            choice=answer["choice"],
            probabilities=dict(answer["probabilities"]),
            confidence=answer["confidence"],
            latency_ms=latency_ms,
            input_tokens=result["usage"]["input_tokens"],
            model=self.model,
            request_id="",
            state=state,
        )
