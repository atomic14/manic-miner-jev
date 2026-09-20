"""Run live games in the terminal, without the viewer.

Examples:
    uv run python -m jevmanic.cli --cavern 2
    uv run python -m jevmanic.cli --cavern 2 --until-complete
    uv run python -m jevmanic.cli --cavern 1 --rules
    uv run python -m jevmanic.cli --cavern 1 --llm haiku

The cavern number starts at 1: cavern 1 is Central Cavern. Each run writes a
log file in runs/, and the viewer can replay it.
"""

import argparse
import asyncio

from dotenv import load_dotenv

from .brain import Brain
from .game import Game
from .llm_brain import LLMBrain
from .options import add_run_options, settings_from
from .runner import play_live

MAX_ATTEMPTS = 10


async def play_once(game, brain, cavern, settings, folder) -> str:
    outcome = ""
    async for kind, data in play_live(game, brain, cavern, settings, folder):
        if kind != "event":
            continue
        if data["type"] == "target":
            print(f"    KEY {data['choice']} at {data['target_cell']} "
                  f"confidence={data.get('confidence', 1):.2f} {data.get('forced_reason', '')}")
        elif data["type"] == "decision":
            top = sorted(data["probabilities"].items(), key=lambda kv: -kv[1])[:3]
            probs = " ".join(f"{k}={v:.2f}" for k, v in top)
            not_offered = f"  not offered={list(data['removed'])}" if data["removed"] else ""
            print(f"{data['n']:3} {data['macro']:11} confidence={data['confidence']:.2f} "
                  f"{data['latency_ms']:5} ms  {probs}{not_offered}")
        elif data["type"] == "result":
            print(f"      -> willy={data['willy']} keys={data['keys_collected']} air={data['air']}")
        elif data["type"] == "end":
            print(data)
            outcome = data["outcome"]
    return outcome


async def main():
    parser = argparse.ArgumentParser(description="Play Manic Miner with jev in the terminal.")
    parser.add_argument("--cavern", type=int, default=1, help="cavern number, 1 to 20 (default 1)")
    parser.add_argument("--until-complete", action="store_true",
                        help=f"play again until a run is complete ({MAX_ATTEMPTS} runs at most)")
    parser.add_argument("--llm", metavar="MODEL", help="an LLM makes the decisions through the "
                        "`claude` command line tool, for example haiku (for comparison, slow)")
    add_run_options(parser)
    args = parser.parse_args()
    if not 1 <= args.cavern <= 20:
        parser.error("the cavern number must be 1 to 20")
    load_dotenv(".env")
    game = Game()
    brain = LLMBrain(args.llm) if args.llm else Brain()
    folder = f"llm-{args.llm}" if args.llm else ""
    for _ in range(MAX_ATTEMPTS if args.until_complete else 1):
        if await play_once(game, brain, args.cavern - 1, settings_from(args), folder) == "cavern complete":
            break
    await brain.close()


if __name__ == "__main__":
    asyncio.run(main())
