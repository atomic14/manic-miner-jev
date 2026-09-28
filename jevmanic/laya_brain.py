"""A decision maker that uses Laya, a typed decision model that runs on this computer.

Laya (https://github.com/mizorewww/laya-mlx) has the same form of request as
jev: a state, and typed questions with instructions and criteria. It runs on
Apple Silicon with MLX. It makes no network call and has no cost.

It is for comparison with jev. With `as_text=False`, Laya gets the same
instructions, options, and state as jev. The main difference is the input
size:

- The instructions and the options together get 256 tokens at most. Laya cuts
  the end of the instructions to make them fit.
- The full input gets 1024 tokens at most. Laya cuts the end of the state.

Laya does this without a message, so this class counts what it cut, and
`cut_report()` gives the totals. A long text such as promptA (about 400
tokens) loses most of its content.

The default (`as_text=True`) sends short sentences instead: see
`_ask_with_text`.

Install:  uv sync --extra laya
"""

import os
import random
import time

from .brain import Answer

DEFAULT_MODEL = "aac6fef/laya-typed-decisions-mlx"  # context of 1024 tokens


# The loop fact that each move sentence adds: "new" (the move goes to a new place), "tried", "many",
# or "" for none. See "Laya instead of jev" in docs/findings.md for the choice of "new".
LOOP_FACT = os.environ.get("LAYA_LOOP_FACT", "new")
ORDERS = 6  # Laya prefers the first option, so ask with this many option orders and use the mean


def option_sentences(state: dict, names=()) -> dict:
    """One short sentence for each option, from the facts of the state.

    A move: its `progress` word, and at most one more fact: "collects a
    key", "completes the cavern", or the LOOP_FACT. A key: its distance word
    and its height word. Longer sentences made Laya worse.
    """
    if "moves" in state and not isinstance(state["moves"], dict):
        return {name: f"{name} is not safe." for name in names}  # no move is safe: `moves` is a string
    if "moves" in state:
        out = {}
        for name, move in state["moves"].items():
            extra = " and completes the cavern" if move.get("completes_cavern") else \
                " and collects a key" if move.get("collects_key") else ""
            if not extra and LOOP_FACT == "new" and move["place"] == "new place":
                extra = " and new"
            if not extra and LOOP_FACT == "tried" and move["tried_from_here"] == "yes":
                extra = " but tried before"
            if not extra and LOOP_FACT == "many" and move["place"] == "visited many times":
                extra = " but visited many times"
            out[name] = f"{name} is {move['progress']}{extra}."
        return out
    return {name: f"{name} is {f['horizontal_distance']} and {f['height']}." for name, f in state["keys"].items()}


def state_as_text(state: dict, order=None) -> str:
    sentences = option_sentences(state, order or ())
    return " ".join(sentences[name] for name in (order or sentences))


class LayaBrain:
    def __init__(self, model: str = DEFAULT_MODEL, as_text: bool = True):
        self.as_text = as_text  # False = the same JSON state and options as jev
        self._rng = random.Random(1)  # the same orders in each run
        import laya_mlx  # optional dependency

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
        if self.as_text:
            return self._ask_with_text(state, q, choice_name)
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

    def _ask_with_text(self, facts: dict, q, choice_name: str) -> Answer:
        """Ask Laya in a form that it can read: short sentences, and option names with no text.

        Laya reads short sentences much better than nested JSON. It prefers
        the first option, so this method asks with ORDERS different option
        orders and uses the mean probabilities. See "Laya instead of jev" in
        docs/findings.md.
        """
        names = list(q.criteria)
        orders = [names] + [self._rng.sample(names, len(names)) for _ in range(ORDERS - 1)]
        total, tokens = dict.fromkeys(names, 0.0), 0
        start = time.perf_counter()
        for order in orders:
            question = {"type": "choice", "instructions": q.instructions, "criteria": dict.fromkeys(order, "")}
            text = state_as_text(facts, order)
            self.requests += 1
            self._count_cuts(text, question)
            result = self.agent.predict(text, {choice_name: question})
            tokens += result["usage"]["input_tokens"]
            for name, p in result["answers"][choice_name]["probabilities"].items():
                total[name] += p / len(orders)
        latency_ms = round((time.perf_counter() - start) * 1000)
        choice = max(total, key=total.get)
        ranked = sorted(total.values(), reverse=True)
        return Answer(
            choice=choice,
            probabilities={name: round(p, 4) for name, p in total.items()},
            confidence=round(ranked[0] - ranked[1], 4) if len(ranked) > 1 else 1.0,
            latency_ms=latency_ms,
            input_tokens=tokens,
            model=self.model,
            request_id="",
            state={"text_sent_to_laya": state_as_text(facts, names), "option_orders": len(orders),
                   "facts_from_which_the_text_comes": facts},
        )
