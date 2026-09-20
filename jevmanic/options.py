"""The command line options that the terminal runner and the measurement tool share."""

import argparse

from .runner import Settings


def add_run_options(parser: argparse.ArgumentParser):
    parser.add_argument("--rules", action="store_true",
                        help="rules mode: the texts are lists of rules that we wrote (for comparison)")
    parser.add_argument("--facts-only-keys", action="store_true",
                        help="the key decision gets the facts only, and no map of the cavern")
    parser.add_argument("--key-every", type=int, default=25, metavar="N",
                        help="repeat the key decision after N decisions, 0 = no repeat (default 25)")
    parser.add_argument("--depth", type=int, default=12, metavar="N",
                        help="the number of moves that the dead end check looks ahead, 0 = off (default 12)")
    parser.add_argument("--key-order", default="", metavar="LETTERS",
                        help="a test: the code sets the key order, for example EACDB (no key request)")
    parser.add_argument("--random-moves", action="store_true",
                        help="a base for comparison: a random choice from the valid moves (no jev call)")


def settings_from(args: argparse.Namespace) -> Settings:
    return Settings(
        rules_mode=args.rules,
        map_key_decision=not args.facts_only_keys,
        key_decision_every=args.key_every,
        survival_depth=args.depth,
        forced_key_order=args.key_order.upper(),
        random_moves=args.random_moves,
    )
