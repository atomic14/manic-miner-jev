"""Test: which key does jev select with rules, and with no rules?

The state is the same. "rules" is the target question of the project.
"free" gives only the purpose, and jev must decide from the facts.

Run:  uv run python -m experiments.probe_target
"""

from dotenv import load_dotenv
from typesafe_sdk import Choice, TypeSafeClient

from jevmanic import brain, describe
from jevmanic.game import Game

FREE_INSTRUCTIONS = (
    "Willy is a miner in a platform game. He must collect all keys. Willy can "
    "climb only 2 rows with one jump. `keys` gives facts about each key "
    "relative to Willy. Select the key that is the easiest for Willy to get next."
)


def main():
    load_dotenv(".env")
    client = TypeSafeClient()
    for cavern in (0, 1):
        snap = Game(cavern=cavern).snapshot()
        names = {k: f"key_{snap.key_letters[k]}" for k in snap.keys}
        state = describe.keys_state(snap, names)
        criteria = {n: f"The key that `keys.{n}` describes." for n in names.values()}
        print(f"\n{snap.cavern_name}")
        for label, instructions in (("rules", brain.key_instructions("promptB", with_map=False)), ("free", FREE_INSTRUCTIONS)):
            answer = client.system_one(state, {"t": Choice(instructions=instructions, criteria=criteria)}).choices["t"]
            probs = " ".join(f"{k}={v:.2f}" for k, v in sorted(answer.probabilities.items()))
            print(f"  {label:6} -> {answer.choice} (confidence {answer.confidence:.2f})  {probs}")
        for name, facts in state["keys"].items():
            print(f"     {name}: {facts['side']} {facts['horizontal_cells']} cells, floor {facts['height']} by {facts['floor_rows_apart']}"
                  + (", one way trip" if "one_way_trip" in facts else ""))


if __name__ == "__main__":
    main()
