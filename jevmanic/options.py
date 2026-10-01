"""The run options that cli.py and experiments/measure.py share."""

import argparse

from .brain import DEFAULT_INSTRUCTIONS, instruction_sets
from .game import SURVIVAL_DEPTH
from .runner import KEY_RULES, RULES, Settings


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
                             "that completes the cavern or collects a key, else a move that goes nearer, else any valid move. "
                             "nearer-memory: the same, but it prefers a move not tried from this place before")
    parser.add_argument("--key-rule", choices=sorted(KEY_RULES), default="",
                        help="for comparison: a rule instead of jev's key decision (no jev request). "
                             "nearest: the key nearest to Willy, in cells")
    parser.add_argument("--no-guardian-facts", action="store_true",
                        help="for comparison: the move decision's state has no guardian facts")
    parser.add_argument("--move-map", action="store_true",
                        help="for comparison: the move decision's state also has the present cavern map")
    parser.add_argument("--map-empty", default=".", metavar="SYMBOL",
                        help="the map symbol for empty space (default .)")
    parser.add_argument("--ladder-fix", action="store_true",
                        help="the way-up finder lets Willy jump through floor tiles above a landing place")
    parser.add_argument("--no-progress-facts", action="store_true",
                        help="for comparison: the move decision's state has no progress facts")
    parser.add_argument("--sample-moves", action="store_true",
                        help="for comparison: play a move drawn from jev's move probabilities, "
                             "instead of jev's selected move")
    parser.add_argument("--graph", action="store_true",
                        help="the route facts come from the movement graph: `progress` counts the moves on the "
                             "shortest way to the target, and the target has no way_up and no way_down")
    parser.add_argument("--half-steps", action="store_true",
                        help="two more moves: a half step to the left and a half step to the right")
    parser.add_argument("--no-way-back", action="store_true",
                        help="with --graph: do not offer a move or a key after which a key or the portal is "
                             "out of reach")


def settings_from(args: argparse.Namespace) -> Settings:
    if args.no_way_back and not args.graph:
        raise SystemExit("--no-way-back needs --graph: the movement graph finds the moves with no way back")
    return Settings(
        instructions=args.instructions,
        map_key_decision=not args.facts_only_keys,
        key_decision_every=args.key_every,
        survival_depth=args.depth,
        forced_key_order=args.key_order.upper(),
        random_moves=args.random_moves,
        rule=args.rule,
        key_rule=args.key_rule,
        sample_moves=args.sample_moves,
        guardian_facts=not args.no_guardian_facts,
        move_map=args.move_map,
        map_empty=args.map_empty,
        ladder_fix=args.ladder_fix,
        progress_facts=not args.no_progress_facts,
        graph_facts=args.graph,
        half_steps=args.half_steps,
        no_way_back=args.no_way_back,
    )
