"""Measure how well jev plays: run many live games and print a table.

Jev does not always give the same answer for the same state, thus one run
tells us little. Use this script before and after each change to the state or
to the questions.

Run:
    uv run python -m experiments.measure caverns=4,6,7 runs=3 label=baseline

Options (all are optional):
    caverns=1,2,3    cavern numbers, 1 to 20            (default 1,2,3)
    runs=3           live games for each cavern         (default 3)
    label=baseline   name of the folder below runs/     (default "measure")
    parallel=5       games that run at the same time    (default 5)
    encoder=words    state encoder                      (default words)
    depth=12         depth of the dead end check, 0 = off
    no-extras        do not ask danger_left, danger_right, threat
    no-memory        do not give `place` and `tried_from_here`
    two-ways-up      give the way up on the left and on the right (measured: worse)
    hybrid-keys      the key decision uses the map; jev gets it at the start and
                     when Willy collects a key; then the run is in movement mode
    key-every=25     with hybrid-keys: repeat the key decision after 25 decisions
    target-map       the target request also has the full map of the cavern
    brief-text       the free mode text in short sentences (measured: worse)
    rigid-target     ask for the target only when Willy collects it or gives up
    recent-moves     give the short-term memory `recent_moves` and `came_from`
    rules-move       move question with our decision procedure (comparison only)
    rules-target     target question with our preference rules (comparison only)

The log files go to runs/<label>/. The viewer can replay them. The summary
goes to runs/<label>/summary.json.
"""

import asyncio
import json
import statistics
import sys
from collections import Counter

from dotenv import load_dotenv

from jevmanic.brain import Brain
from jevmanic.game import Game
from jevmanic.runner import RUNS_DIR, Settings, play_live


def parse(argv):
    options = {"caverns": "1,2,3", "runs": "3", "label": "measure", "parallel": "5", "encoder": "words"}
    flags = set()
    for arg in argv:
        if "=" in arg:
            key, value = arg.split("=", 1)
            options[key] = value
        else:
            flags.add(arg)
    settings = Settings(
        extra_questions="no-extras" not in flags,
        memory="no-memory" not in flags,
        free_target="rules-target" not in flags,
        free_move="rules-move" not in flags,
        recent_moves="recent-moves" in flags,
        flexible_target="rigid-target" not in flags,
        brief_text="brief-text" in flags,
        target_map="target-map" in flags,
        hybrid_keys="hybrid-keys" in flags,
        two_ways_up="two-ways-up" in flags,
    )
    if "key-every" in options:
        settings.key_decision_every = int(options["key-every"])
    if "depth" in options:
        settings.survival_depth = int(options["depth"])
    return options, settings


async def one_run(brain, limit, cavern, encoder, settings, label):
    """Play one game and give a summary of it. An error in one game does not stop the others."""
    try:
        return await _one_run(brain, limit, cavern, encoder, settings, label)
    except Exception as error:
        print(f"  cavern {cavern + 1:2}: ERROR {type(error).__name__}: {error}", flush=True)
        return {"cavern": cavern, "file": "", "outcome": f"error: {type(error).__name__}", "keys": 0,
                "decisions": 0, "tokens": 0, "cost_usd": 0.0, "mean_latency_ms": 0,
                "low_confidence": 0, "jev_calls": 0}


async def _one_run(brain, limit, cavern, encoder, settings, label):
    async with limit:
        game = Game()
        decisions, latencies, confidences = 0, [], []
        end, file = {}, ""
        async for kind, data in play_live(game, brain, encoder, True, cavern, settings, label):
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
    options, settings = parse(sys.argv[1:])
    caverns = [int(c) - 1 for c in options["caverns"].split(",")]
    runs, label = int(options["runs"]), options["label"]
    print(f"label={label} caverns={[c + 1 for c in caverns]} runs={runs} settings={settings}")
    brain = Brain()
    limit = asyncio.Semaphore(int(options["parallel"]))
    jobs = [one_run(brain, limit, c, options["encoder"], settings, label) for c in caverns for _ in range(runs)]
    results = await asyncio.gather(*jobs)
    await brain.close()
    rows = table(results, Game().cavern_names())
    summary = {"label": label, "options": options, "settings": settings.__dict__, "caverns": rows, "runs": results}
    (RUNS_DIR / label / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
