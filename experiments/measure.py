"""Measure how well jev plays: run many live games and print a table.

Jev does not always give the same answer for the same state, thus one run
tells us little. Use this tool before and after each change to the state or to
the questions. 10 runs for each cavern show only large effects.

Examples:
    uv run python -m experiments.measure --caverns 1,2,3 --runs 10 --label my-test
    uv run python -m experiments.measure --caverns 1,2 --label rules --rules
    uv run python -m experiments.measure --caverns 1 --label random --random-moves --key-order ABCDE

The log files go to runs/<label>/, and the viewer can replay them. The summary
goes to runs/<label>/summary.json.
"""

import argparse
import asyncio
import json
import statistics
from collections import Counter
from dataclasses import asdict

from dotenv import load_dotenv

from jevmanic.brain import Brain
from jevmanic.game import Game
from jevmanic.options import add_run_options, settings_from
from jevmanic.runner import RUNS_DIR, play_live


def parse():
    parser = argparse.ArgumentParser(description="Measure how well jev plays Manic Miner.")
    parser.add_argument("--caverns", default="1,2,3", help="cavern numbers, 1 to 20 (default 1,2,3)")
    parser.add_argument("--runs", type=int, default=10, help="live games for each cavern (default 10)")
    parser.add_argument("--label", default="measure", help="the name of the folder below runs/")
    parser.add_argument("--parallel", type=int, default=5, help="games that run at the same time (default 5)")
    add_run_options(parser)
    args = parser.parse_args()
    try:
        args.cavern_list = [int(c) - 1 for c in args.caverns.split(",")]
    except ValueError:
        parser.error("--caverns must be numbers with commas, for example 1,2,3")
    if not all(0 <= c < 20 for c in args.cavern_list):
        parser.error("each cavern number must be 1 to 20")
    return args


async def one_run(brain, limit, cavern, settings, label):
    """Play one game and give a summary of it. An error in one game does not stop the others."""
    try:
        return await _one_run(brain, limit, cavern, settings, label)
    except Exception as error:
        print(f"  cavern {cavern + 1:2}: ERROR {type(error).__name__}: {error}", flush=True)
        return {"cavern": cavern, "file": "", "outcome": f"error: {type(error).__name__}", "keys": 0,
                "decisions": 0, "tokens": 0, "cost_usd": 0.0, "mean_latency_ms": 0,
                "low_confidence": 0, "jev_calls": 0}


async def _one_run(brain, limit, cavern, settings, label):
    async with limit:
        game = Game()
        decisions, latencies, confidences = 0, [], []
        end, file = {}, ""
        async for kind, data in play_live(game, brain, cavern, settings, label):
            if kind != "event":
                continue
            if data["type"] == "header":
                file = data["file"]
            elif data["type"] == "decision" and not data.get("forced"):
                latencies.append(data["latency_ms"])
                confidences.append(data["confidence"])
            elif data["type"] == "end":
                end = data
        print(f"  cavern {cavern + 1:2}: {end['outcome']:22} keys={end['keys_collected']} "
              f"decisions={end['decisions']:3} ${end['cost_usd']:.4f}", flush=True)
        return {
            "cavern": cavern,
            "file": file,
            "outcome": end["outcome"],
            "keys": end["keys_collected"],
            "decisions": end["decisions"],
            "tokens": end["input_tokens"],
            "cost_usd": end["cost_usd"],
            "mean_latency_ms": round(statistics.mean(latencies)) if latencies else 0,
            "low_confidence": sum(1 for c in confidences if c < 0.5),
            "jev_calls": len(confidences),
        }


def table(results, names):
    print(f"\n{'cavern':34} {'complete':>9} {'keys':>6} {'decisions':>10} {'tokens/call':>12} "
          f"{'conf<0.5':>9} {'cost/run':>9}  other outcomes")
    rows = []
    for cavern in sorted({r["cavern"] for r in results}):
        runs = [r for r in results if r["cavern"] == cavern]
        done = [r for r in runs if r["outcome"] == "cavern complete"]
        calls = sum(r["jev_calls"] for r in runs) or 1
        row = {
            "cavern": cavern + 1,
            "name": names[cavern],
            "runs": len(runs),
            "complete": len(done),
            "mean_keys": round(statistics.mean(r["keys"] for r in runs), 1),
            # The decisions of the complete runs only. A failed run has no useful count.
            "mean_decisions_complete": round(statistics.mean(r["decisions"] for r in done)) if done else None,
            "tokens_per_call": round(sum(r["tokens"] for r in runs) / calls),
            "low_confidence_rate": round(sum(r["low_confidence"] for r in runs) / calls, 2),
            "mean_cost_usd": round(statistics.mean(r["cost_usd"] for r in runs), 4),
            "other_outcomes": dict(Counter(r["outcome"] for r in runs if r["outcome"] != "cavern complete")),
        }
        rows.append(row)
        print(f"{row['cavern']:2} {row['name']:31} {row['complete']:>5}/{row['runs']:<3} {row['mean_keys']:>6} "
              f"{str(row['mean_decisions_complete'] or '-'):>10} {row['tokens_per_call']:>12} "
              f"{row['low_confidence_rate']:>9} {row['mean_cost_usd']:>9}  {row['other_outcomes'] or ''}")
    total = sum(r["cost_usd"] for r in results)
    complete = sum(1 for r in results if r["outcome"] == "cavern complete")
    print(f"\ntotal: {complete} of {len(results)} runs complete, cost ${total:.3f}")
    return rows


async def main():
    load_dotenv(".env")
    args = parse()
    settings = settings_from(args)
    print(f"label={args.label} caverns={[c + 1 for c in args.cavern_list]} runs={args.runs} {settings}")
    brain = Brain()
    limit = asyncio.Semaphore(args.parallel)
    jobs = [one_run(brain, limit, c, settings, args.label) for c in args.cavern_list for _ in range(args.runs)]
    results = await asyncio.gather(*jobs)
    await brain.close()
    rows = table(results, Game().cavern_names())
    summary = {"label": args.label, "settings": asdict(settings), "caverns": rows, "runs": results}
    (RUNS_DIR / args.label / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
