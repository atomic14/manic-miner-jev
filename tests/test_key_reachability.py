"""Check the search's proof and budget rules on small, fully known games."""

from experiments.probe_key_reachability import compare, find_key


class TinyGame:
    def __init__(self):
        self.emu = self
        self.state = "start"
        self.tick_count = 0
        self.slots = {}

    def save_state(self, slot):
        self.slots[slot] = self.state

    def load_state(self, slot):
        self.state = self.slots[slot]

    def set_joystick(self, value):
        pass

    def run_macro(self, move):
        self.state = {("start", "walk_right"): "middle",
                      ("middle", "jump_right"): "key"}.get((self.state, move), "dead")
        self.tick_count += 1

    def is_dead(self):
        return self.state == "dead"

    def is_complete(self):
        return False

    def peek_range(self, address, length):
        # Death also exposes zero keys, to check that death takes precedence.
        attr = 0 if self.state in ("key", "dead") else 1
        return bytes([attr, 0, 0, 0, 0, 255] + [0] * 19)


def test_key_search_finds_and_restores_a_two_move_route():
    game = TinyGame()
    assert find_key(game, 1, 1, [100]) == ("unreachable", None)
    assert game.state == "start" and game.tick_count == 0
    assert find_key(game, 1, 2, [100]) == ("reachable", ["walk_right", "jump_right"])
    assert game.state == "start" and game.tick_count == 0


def test_key_search_does_not_treat_an_exhausted_budget_as_failure():
    game = TinyGame()
    assert find_key(game, 1, 2, [1]) == ("unknown", None)
    assert game.state == "start" and game.tick_count == 0


def test_key_search_does_not_count_a_key_after_death():
    game = TinyGame()
    game.state = "dead"
    assert find_key(game, 1, 2, [100]) == ("unreachable", None)


def test_conflict_requires_no_possibly_shared_successful_move():
    a = {"left": {"status": "reachable"}, "right": {"status": "unreachable"}}
    b = {"left": {"status": "unreachable"}, "right": {"status": "reachable"}}
    assert compare([a, b])["conflicting_first_moves"]
    b["left"]["status"] = "unknown"
    assert not compare([a, b])["conflicting_first_moves"]
