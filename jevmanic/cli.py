"""Run one live game in the terminal, without the viewer.

Run:  uv run python -m jevmanic.cli [encoder] [lookahead] [until-complete] [cavern=2]

The cavern number starts at 1: cavern=1 is Central Cavern.

With "until-complete", the script plays again until jev completes the cavern
(10 runs at most). Jev does not give the same answer each time, thus some
runs fail and some runs succeed.
"""

import asyncio
import sys

from dotenv import load_dotenv

from .brain import Brain
from .game import Game
from .runner import play_live


async def main(encoder: str, look_ahead: bool, until_complete: bool, cavern: int):
    load_dotenv(".env")
    game, brain = Game(), Brain()
    for attempt in range(10 if until_complete else 1):
        outcome = await play_once(game, brain, encoder, look_ahead, cavern)
        if outcome == "cavern complete":
            break
    await brain.close()


async def play_once(game, brain, encoder, look_ahead, cavern) -> str:
    outcome = ""
    async for kind, data in play_live(game, brain, encoder, look_ahead, cavern):
        if kind != "event":
            continue
        if data["type"] == "target":
            print(f"    TARGET {data['choice']} at {data['target_cell']} "
                  f"conf={data.get('confidence', 1):.2f} {data.get('probabilities', 'forced')}")
        elif data["type"] == "decision":
            top = sorted(data["probabilities"].items(), key=lambda kv: -kv[1])[:3]
            probs = " ".join(f"{k}={v:.2f}" for k, v in top)
            print(f"{data['n']:3} {data['macro']:11} conf={data['confidence']:.2f} "
                  f"{data['latency_ms']:4} ms  {probs}"
                  + (f"  removed={list(data['removed'])}" if data["removed"] else ""))
        elif data["type"] == "result":
            print(f"      -> willy={data['willy']} keys={data['keys_collected']} air={data['air']}")
        elif data["type"] == "end":
            print(data)
            outcome = data["outcome"]
    return outcome


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("words", "hybrid", "ascii_local", "ascii_full") else "words", "lookahead" in sys.argv, "until-complete" in sys.argv,
                     next((int(a.split("=")[1]) - 1 for a in sys.argv if a.startswith("cavern=")), 0)))
