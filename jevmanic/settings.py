"""The settings of a live run. The runner and the state builders (describe.py) both use them."""

from dataclasses import dataclass

from .brain import DEFAULT_INSTRUCTIONS
from .game import SURVIVAL_DEPTH


@dataclass
class Settings:
    """The settings of a live run. The defaults are the normal settings."""

    # The instruction set: a folder in `jevmanic/instructions/`.
    instructions: str = DEFAULT_INSTRUCTIONS
    # True: the key decision's state has the cavern map. The key decision
    # comes at the start, after each collected key or flipped switch, and
    # again after `key_decision_every` decisions (0 = no repeat).
    # False: the state has the key facts only, and GIVE_UP_DECISIONS applies.
    map_key_decision: bool = True
    key_decision_every: int = 25
    # How many moves the dead-end check looks ahead. 0 = off.
    survival_depth: int = SURVIVAL_DEPTH
    # Settings for comparison. Each one replaces jev in one type of decision.
    forced_key_order: str = ""  # a fixed key order instead of key decisions, for example "EACDB"
    random_moves: bool = False  # a random valid move instead of jev's move decision
    rule: str = ""  # a rule from RULES instead of jev's move decision. "" = jev.
    key_rule: str = ""  # a rule from KEY_RULES instead of jev's key decision. "" = jev.
    # Play a move sampled from jev's probabilities, instead of jev's selected move.
    sample_moves: bool = False
    # False: the move decision's state has no `guardians` field. The look-ahead still removes deadly moves.
    guardian_facts: bool = True
    # True: the move decision's state also has the present cavern map and its legend.
    move_map: bool = False
    map_empty: str = "."  # the map symbol for empty space
    # True: the way-up finder lets Willy jump through floor tiles above a landing place (a "ladder").
    ladder_fix: bool = False
    # False: the move decision's state has no `progress` and no `progress_measures`.
    progress_facts: bool = True
    # True: the route facts come from the movement graph (graph.py). `progress`
    # counts the moves on the shortest way to the target, and the target has
    # no `way_up` and no `way_down`.
    graph_facts: bool = False
    # True: two more moves, a half step to the left and a half step to the right.
    half_steps: bool = False
    # True (needs graph_facts): the harness does not offer a move, or a key,
    # after which a key or the portal is out of reach.
    no_way_back: bool = False
