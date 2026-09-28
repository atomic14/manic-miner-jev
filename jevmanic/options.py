"""The run options that cli.py and experiments/measure.py share."""

import argparse

from .brain import DEFAULT_INSTRUCTIONS, instruction_sets
from .game import SURVIVAL_DEPTH
from .runner import RULES, Settings


def add_run_options(parser: argparse.ArgumentParser):
    parser.add_argument("--instructions", default=DEFAULT_INSTRUCTIONS, choices=instruction_sets(), metavar="NAME",
                        help="the instruction set, a folder in jevmanic/instructions/: "
                             + ", ".join(instruction_sets()) + f" (default {DEFAULT_INSTRUCTIONS})")
    parser.add_argument("--facts-only-keys", action="store_true",
                        help="the key decision gets the key facts only, and no cavern map")
    parser.add_argument("--key-every", type=int, default=25, metavar="N",
                        help="repeat the key decision after N decisions, 0 = no repeat (default 25)")
    parser.add_argument("--depth", type=int, default=SURVIVAL_DEPTH, metavar="N",
                        help="how many moves the dead-end check looks ahead, 0 = off (default 4)")
    parser.add_argument("--key-order", default="", metavar="LETTERS",
                        help="a fixed key order instead of key decisions: letters, for example EACDB, "
                             "or `optimum` for the cavern's optimum order")
    parser.add_argument("--random-moves", action="store_true",
                        help="for comparison: a random valid move instead of jev's move decision (no jev request)")
    parser.add_argument("--rule", choices=sorted(RULES), default="",
                        help="for comparison: a rule instead of jev's move decision (no jev request). nearer: a move "
                             "that completes the cavern or collects a key, else a move that goes nearer, else any valid move")


def settings_from(args: argparse.Namespace) -> Settings:
    return Settings(
        instructions=args.instructions,
        map_key_decision=not args.facts_only_keys,
        key_decision_every=args.key_every,
        survival_depth=args.depth,
        forced_key_order=args.key_order.upper(),
        random_moves=args.random_moves,
        rule=args.rule,
    )
