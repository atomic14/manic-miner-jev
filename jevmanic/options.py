"""The command line options that the terminal runner and the measurement tool share."""

import argparse

from .brain import DEFAULT_INSTRUCTIONS, instruction_sets
from .game import SURVIVAL_DEPTH
from .describe import MOVE_FACT_SETS, PROGRESS_FACTS
from .runner import RULES, Settings


def add_run_options(parser: argparse.ArgumentParser):
    parser.add_argument("--instructions", default=DEFAULT_INSTRUCTIONS, choices=instruction_sets(), metavar="NAME",
                        help="the set of instruction texts, a folder in jevmanic/instructions/: "
                             + ", ".join(instruction_sets()) + f" (default {DEFAULT_INSTRUCTIONS}). promptB is for comparison")
    parser.add_argument("--facts-only-keys", action="store_true",
                        help="the key decision gets the facts only, and no map of the cavern")
    parser.add_argument("--key-every", type=int, default=25, metavar="N",
                        help="repeat the key decision after N decisions, 0 = no repeat (default 25)")
    parser.add_argument("--depth", type=int, default=SURVIVAL_DEPTH, metavar="N",
                        help="the number of moves that the dead end check looks ahead, 0 = off (default 4)")
    parser.add_argument("--key-order", default="", metavar="LETTERS",
                        help="the code sets the key order, and there is no key request: letters, for example "
                             "EACDB, or `optimum` for the optimum order of the cavern")
    parser.add_argument("--random-moves", action="store_true",
                        help="a base for comparison: a random choice from the valid moves (no jev call)")
    parser.add_argument("--rule", choices=sorted(RULES), default="",
                        help="a simple rule in the place of jev, for comparison (no jev call). nearer: a move that "
                             "completes the cavern or collects a key, else a move that goes nearer. nearer-new: the "
                             "same, but a nearer move to a new place first, and then a move to a new place")
    parser.add_argument("--progress", choices=PROGRESS_FACTS, default="route",
                        help="the facts about the direction of each move: route (`progress`, default), plain "
                             "(measured distances only, use --instructions promptD-plain), or none")
    parser.add_argument("--move-facts", choices=list(MOVE_FACT_SETS), default="full",
                        help="the facts of the move state: full (default), or a smaller set for a test "
                             "(use the instruction set promptM-<name>)")
    parser.add_argument("--no-progress", action="store_true",
                        help="the same as --progress none (use it with --instructions promptA-no-progress)")


def settings_from(args: argparse.Namespace) -> Settings:
    return Settings(
        instructions=args.instructions,
        map_key_decision=not args.facts_only_keys,
        key_decision_every=args.key_every,
        survival_depth=args.depth,
        forced_key_order=args.key_order.upper(),
        random_moves=args.random_moves,
        rule=args.rule,
        progress_facts="none" if args.no_progress else args.progress,
        move_facts=args.move_facts,
    )
