"""Manic Miner on the ZX Spectrum emulator.

This module starts the game, reads the game data from the emulator memory,
and runs macros. The memory addresses come from the SkoolKit disassembly
(https://skoolkit.ca/disassemblies/manic_miner/).
"""

import contextlib
import ctypes
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import zxspec

SNAPSHOT = Path(__file__).resolve().parent.parent / "roms" / "ManicMiner.z80"

# --- Memory addresses ---
ADDR_CAVERN_NAME = 32768  # 32 ASCII characters
# The game keeps the 20 cavern definitions here. Each one has 1024 bytes,
# and the name is at offset 512.
ADDR_CAVERN_DEFINITIONS = 45056
CAVERN_COUNT = 20
ADDR_TILE_FLOOR = 32809  # attribute byte of each tile type
ADDR_TILE_CRUMBLING = 32818
ADDR_TILE_WALL = 32827
ADDR_TILE_CONVEYOR = 32836
ADDR_TILE_NASTY1 = 32845
ADDR_TILE_NASTY2 = 32854
# The eighth tile of a cavern is the "extra" tile. Its meaning is a property
# of the cavern (see the SkoolKit disassembly): a floor in some caverns, a
# switch in the two Kong Beast caverns, spider silk in The Menagerie.
ADDR_TILE_EXTRA = 32863
EXTRA_TILE_IS_FLOOR = (9, 10, 12, 13, 14)  # cavern numbers from 0
SWITCH_CAVERNS = (7, 11)
SCREEN_BUFFER = 28672  # the screen buffer that the game draws in
ADDR_EUGENE_DIR = 32987  # 0 = Eugene moves down, 1 = up
ADDR_EUGENE_Y = 32988  # pixel y of Eugene
EUGENE_CAVERN = 4
EUGENE_X = 15
ADDR_VGUARDS = 32989  # vertical guardians: 4 x 7 bytes
ADDR_WILLY_PIXEL_Y = 32872  # 2 x the pixel y position
ADDR_WILLY_FRAME = 32873  # 0 to 3: the position of Willy in his cell
ADDR_WILLY_DIR = 32874  # bit 0: 0 = Willy looks right, 1 = Willy looks left
ADDR_AIRBORNE = 32875  # 0 = on the ground, 1 = jump, 2+ = fall, 255 = dead
ADDR_WILLY_ATTR = 32876  # word: address of Willy in the attribute buffer
ADDR_CONVEYOR_DIR = 32879  # 0 = left, 1 = right
ADDR_ITEMS = 32885  # 5 items x 5 bytes
ADDR_PORTAL_POS = 32944  # word: address of the portal in the attribute buffer
ADDR_AIR = 32956  # 63 (full) down to 36 (empty)
ADDR_HGUARDS = 32958  # horizontal guardians: 4 x 7 bytes
ADDR_CAVERN = 33799  # cavern number, 0 to 19
ADDR_SCORE = 33833  # 6 ASCII digits
ADDR_LIVES = 33879
ATTR_BUFFER = 23552  # attribute buffer: 32 columns x 16 rows. Positions use this base.
# Attribute buffer of the empty cavern. It has tiles only: no Willy, no
# guardians, no keys. The game removes a crumbling floor from it when the
# floor is fully gone.
EMPTY_ATTR_BUFFER = 24064

AIR_FULL = 63
AIR_EMPTY = 36
COLS, ROWS = 32, 16

# Kempston joystick bits
JOY_RIGHT = 1
JOY_LEFT = 2
JOY_FIRE = 16

START_SLOT = 0  # emulator state slot for the start of cavern 0
# Slot 100 + n has the start of cavern n. The look-ahead uses slot 1, and the
# dead end check uses the slots from 2 to 2 + depth. They must not overlap.
CAVERN_SLOT_BASE = 100
LOOK_AHEAD_SLOT = 1  # emulator state slot that the look-ahead uses
DEAD_END_SLOT = 2  # the dead end check uses the slots from this number up
# The dead end check: can Willy stay alive for this number of macros? 4 is a
# compromise: it is sufficient for Central Cavern, and it is a small help from
# the code. The Menagerie is better with 6 or more (see the README).
SURVIVAL_DEPTH = 4
# The largest number of macros that one dead end check can try.
SURVIVAL_BUDGET = 600
DEAD_END_CAUSE = "dead end, Willy cannot stay alive after it"

# Willy moves 2 pixels in each game tick. Thus 4 ticks move him one cell.
TICKS_PER_CELL = 4
# The longest time that we wait for Willy to land after a macro.
MAX_SETTLE_TICKS = 40


@dataclass
class Macro:
    """A short fixed sequence of joystick input."""

    name: str
    joystick: int
    ticks: int  # number of ticks to hold the joystick
    is_jump: bool = False


MACROS = {
    m.name: m
    for m in [
        Macro("walk_left", JOY_LEFT, TICKS_PER_CELL),
        Macro("walk_right", JOY_RIGHT, TICKS_PER_CELL),
        Macro("jump_left", JOY_FIRE | JOY_LEFT, 2, is_jump=True),
        Macro("jump_right", JOY_FIRE | JOY_RIGHT, 2, is_jump=True),
        Macro("jump_up", JOY_FIRE, 2, is_jump=True),
        Macro("wait", 0, TICKS_PER_CELL),
    ]
}


@dataclass
class Guardian:
    x: int  # left column (a guardian is 2 x 2 cells)
    y: int  # top row
    moving: str  # "left", "right", "up", or "down"
    min_x: int  # left limit of the patrol
    max_x: int  # right limit of the patrol
    axis: str = "horizontal"  # or "vertical"
    min_y: int = 0  # top limit of the patrol (vertical guardians)
    max_y: int = 0  # bottom limit of the patrol


@dataclass
class Snapshot:
    """The game data at one moment. All positions are cell positions."""

    cavern_name: str
    tiles: list[str]  # 16 strings of 32 characters, see TILE_CHARS
    willy_x: int  # left column of Willy (Willy is 2 x 2 cells)
    willy_y: int  # top row of Willy
    willy_facing: str  # "left" or "right"
    airborne: bool
    keys: list[tuple[int, int]]  # keys that Willy did not collect
    portal: tuple[int, int]  # top-left cell of the portal (2 x 2 cells)
    guardians: list[Guardian] = field(default_factory=list)
    switches: list[tuple[int, int]] = field(default_factory=list)  # switches that are not flipped
    conveyor_direction: str = "left"  # the direction in which a conveyor moves Willy
    # One letter for each key (A, B, C, ...). A key keeps its letter for the full run.
    key_letters: dict = field(default_factory=dict)
    air: float = 1.0  # 1.0 = full, 0.0 = empty
    # The crumbling floor tiles that are partly gone: cell -> pixel rows that are gone (1 to 7).
    crumbled: dict = field(default_factory=dict)
    score: int = 0
    lives: int = 0


@dataclass
class Outcome:
    """The result of one macro, found by the look-ahead."""

    dead: bool
    cause: str  # if dead: "guardian", "nasty", "fall or other cause", or "dead end"
    complete: bool
    dx: int  # cells to the right (a negative value is to the left)
    dy: int  # rows higher (a negative value is lower)
    keys_collected: int
    ticks: int
    x: int  # the position of Willy after the macro
    y: int
    # The crumbling floor below Willy after the macro: pixel rows that are gone (0 to 7).
    floor_rows_gone: int = 0


# Characters for the tile map.
TILE_EMPTY = "."
TILE_FLOOR = "="
TILE_CRUMBLING = "~"
TILE_WALL = "#"
TILE_CONVEYOR = "c"
TILE_NASTY = "X"


@contextlib.contextmanager
def _no_emulator_text():
    """The C++ emulator prints text when it loads a snapshot. Hide that text."""
    sys.stdout.flush()
    saved = os.dup(1)
    with open(os.devnull, "w") as devnull:
        os.dup2(devnull.fileno(), 1)
        try:
            yield
        finally:
            # The C library keeps the text in a buffer. Write it out now,
            # while the output still goes to the null device.
            ctypes.CDLL(None).fflush(None)
            os.dup2(saved, 1)
            os.close(saved)


class Game:
    """One Manic Miner game in one cavern."""

    def __init__(self, snapshot_path: Path = SNAPSHOT, cavern: int = 0):
        with _no_emulator_text():
            self.emu = zxspec.RLSpectrum(False)
            loaded = self.emu.load_z80(str(snapshot_path))
        if not loaded:
            raise RuntimeError(f"cannot load {snapshot_path}")
        # False replays a log file from before this behaviour (see _against_conveyor).
        self.hold_against_conveyor = True
        self._boot()
        self.emu.save_state(START_SLOT)
        self.tick_count = 0
        self.select_cavern(cavern)

    # -- start ---------------------------------------------------------------

    def _boot(self):
        """Go from the title screen to the start of the first cavern."""
        self.emu.run_frames(300)
        self.emu.set_joystick(JOY_FIRE)
        self.emu.run_frames(30)
        self.emu.set_joystick(0)
        for _ in range(100):
            self.emu.run_frames(2)
            if self.emu.peek(ADDR_AIR) == AIR_FULL and self.emu.peek(ADDR_AIRBORNE) == 0:
                break
        else:
            raise RuntimeError("the game did not start")
        # Align the emulator with the start of a game tick.
        self.emu.run_until_tick()

    def cavern_names(self) -> list[str]:
        """The names of the 20 caverns, from the game memory."""
        return [
            self.emu.peek_range(ADDR_CAVERN_DEFINITIONS + n * 1024 + 512, 32)
            .decode("ascii", "replace")
            .strip()
            for n in range(CAVERN_COUNT)
        ]

    def select_cavern(self, cavern: int):
        """Go to the start of a cavern (0 to 19)."""
        slot = CAVERN_SLOT_BASE + cavern
        if not self.emu.has_state(slot):
            self.emu.load_state(START_SLOT)
            if cavern != 0:
                self._warp(cavern)
            self.emu.run_until_tick()
            self.emu.save_state(slot)
        self.cavern = cavern
        self.restart()
        self.__dict__.pop("_switch_cells", None)
        self._key_letters = {}
        self._key_letters = {cell: "ABCDEFGH"[i] for i, cell in enumerate(self.snapshot().keys)}
        self.start_lives = self.emu.peek(ADDR_LIVES)
        self.start_cavern = self.emu.peek(ADDR_CAVERN)

    def _warp(self, cavern: int):
        """Go to a different cavern.

        The code sets the cavern number, gives Willy one more life, and makes
        the air empty. Willy dies, and the game then starts the new cavern.
        """
        self.emu.poke(ADDR_CAVERN, cavern)
        lives = self.emu.peek(ADDR_LIVES)
        self.emu.poke(ADDR_LIVES, lives + 1)
        self.emu.poke(ADDR_AIR, AIR_EMPTY)
        for _ in range(2000):
            self.emu.run_frames(2)
            if (
                self.emu.peek(ADDR_AIR) == AIR_FULL
                and self.emu.peek(ADDR_LIVES) == lives
                and self.emu.peek(ADDR_AIRBORNE) == 0
            ):
                break
        else:
            raise RuntimeError(f"cannot go to cavern {cavern}")
        # Wait until the game has drawn the new cavern.
        for _ in range(200):
            self.emu.run_frames(2)
            drawn = sum(1 for b in self.emu.peek_range(ATTR_BUFFER, COLS * ROWS) if b != 0)
            if drawn > 40 and self.emu.peek(ADDR_AIRBORNE) == 0:
                break
        else:
            raise RuntimeError(f"cavern {cavern} did not start")
        self.emu.run_frames(16)

    def restart(self):
        """Go back to the start of the cavern."""
        self.emu.load_state(CAVERN_SLOT_BASE + self.cavern)
        self.emu.set_joystick(0)
        self.tick_count = 0

    # -- game status -----------------------------------------------------------

    def _word(self, addr):
        return self.emu.peek(addr) + 256 * self.emu.peek(addr + 1)

    @staticmethod
    def _cell(attr_addr):
        offset = attr_addr - ATTR_BUFFER
        return offset % COLS, offset // COLS

    def is_dead(self):
        return (
            self.emu.peek(ADDR_AIRBORNE) == 255
            or self.emu.peek(ADDR_LIVES) < self.start_lives
        )

    def is_complete(self):
        return self.emu.peek(ADDR_CAVERN) != self.start_cavern

    def is_airborne(self):
        return self.emu.peek(ADDR_AIRBORNE) != 0

    def screen_rgb(self):
        """The screen as a numpy array of 192 x 256 x 3 bytes."""
        return self.emu.get_screen_rgb()

    def snapshot(self) -> Snapshot:
        emu = self.emu
        attrs = emu.peek_range(EMPTY_ATTR_BUFFER, COLS * ROWS)
        tile_chars = {
            emu.peek(ADDR_TILE_FLOOR): TILE_FLOOR,
            emu.peek(ADDR_TILE_CRUMBLING): TILE_CRUMBLING,
            emu.peek(ADDR_TILE_WALL): TILE_WALL,
            emu.peek(ADDR_TILE_CONVEYOR): TILE_CONVEYOR,
            emu.peek(ADDR_TILE_NASTY1): TILE_NASTY,
            emu.peek(ADDR_TILE_NASTY2): TILE_NASTY,
        }
        if self.cavern in EXTRA_TILE_IS_FLOOR:
            tile_chars[emu.peek(ADDR_TILE_EXTRA)] = TILE_FLOOR
        tiles = [
            "".join(tile_chars.get(attrs[y * COLS + x], TILE_EMPTY) for x in range(COLS))
            for y in range(ROWS)
        ]

        keys = []
        data = emu.peek_range(ADDR_ITEMS, 25)
        for i in range(5):
            attr = data[i * 5]
            if attr == 255:
                break  # end of the list
            if attr == 0:
                continue  # Willy collected this key
            keys.append(self._cell(data[i * 5 + 1] + 256 * data[i * 5 + 2]))

        guardians = []
        data = emu.peek_range(ADDR_HGUARDS, 28)
        for i in range(4):
            entry = data[i * 7 : (i + 1) * 7]
            if entry[0] == 255:
                break
            if entry[0] == 0:
                continue
            x, y = self._cell(entry[1] + 256 * entry[2])
            # Animation frames 0 to 3 move right. Frames 4 to 7 move left.
            moving = "right" if entry[4] < 4 else "left"
            guardians.append(Guardian(x, y, moving, entry[5] & 31, entry[6] & 31))

        # Vertical guardians: attribute, frame, pixel y, column, step, top, bottom.
        data = emu.peek_range(ADDR_VGUARDS, 28)
        for i in range(4):
            entry = data[i * 7 : (i + 1) * 7]
            if entry[0] == 255:
                break
            x, y = entry[3], entry[2] // 8
            if entry[0] == 0 or not (0 <= x < COLS and 0 <= y < ROWS):
                continue  # some caverns use this table for other data
            step = entry[4] - 256 if entry[4] > 127 else entry[4]
            guardians.append(
                Guardian(x, y, "down" if step >= 0 else "up", x, x, "vertical", entry[5] // 8, entry[6] // 8)
            )
        if self.cavern == EUGENE_CAVERN:
            eugene_y = emu.peek(ADDR_EUGENE_Y) // 8
            moving = "up" if emu.peek(ADDR_EUGENE_DIR) else "down"
            guardians.append(Guardian(EUGENE_X, eugene_y, moving, EUGENE_X, EUGENE_X, "vertical", 0, 11))

        willy_x, willy_y = self._cell(self._word(ADDR_WILLY_ATTR))
        digits = emu.peek_range(ADDR_SCORE, 6)
        return Snapshot(
            cavern_name=emu.peek_range(ADDR_CAVERN_NAME, 32).decode("ascii", "replace").strip(),
            tiles=tiles,
            willy_x=willy_x,
            willy_y=willy_y,
            willy_facing="left" if emu.peek(ADDR_WILLY_DIR) & 1 else "right",
            airborne=self.is_airborne(),
            keys=keys,
            portal=self._cell(self._word(ADDR_PORTAL_POS)),
            guardians=guardians,
            switches=self._switches(),
            conveyor_direction="right" if emu.peek(ADDR_CONVEYOR_DIR) else "left",
            key_letters=dict(getattr(self, "_key_letters", {})),
            air=(emu.peek(ADDR_AIR) - AIR_EMPTY) / (AIR_FULL - AIR_EMPTY),
            crumbled=self._crumbled(tiles),
            score=int(digits) if digits.isdigit() else 0,
            lives=emu.peek(ADDR_LIVES),
        )

    @staticmethod
    def _screen_address(col, row, line):
        return SCREEN_BUFFER + ((row & 0x18) << 8) + ((row & 7) << 5) + (line << 8) + col

    def _cell_pixels(self, col, row):
        return bytes(self.emu.peek(self._screen_address(col, row, i)) for i in range(8))

    @staticmethod
    def _floor_rows_gone(before: Snapshot, after: Snapshot) -> int:
        """The condition of the crumbling floor below Willy after a macro. 8 = the tile is gone."""
        worst, row = 0, after.willy_y + 2
        for x in (after.willy_x, after.willy_x + 1):
            if row < ROWS and 0 <= x < COLS and before.tiles[row][x] == TILE_CRUMBLING:
                gone = after.tiles[row][x] != TILE_CRUMBLING
                worst = max(worst, 8 if gone else after.crumbled.get((x, row), 0))
        return worst

    def _crumbled(self, tiles) -> dict:
        """The pixel rows that are gone, for each crumbling floor tile that is partly gone.

        The game has no counter for this. While Willy stands on a crumbling
        floor, the game moves the pixels of the tile down by one row in each
        frame. After 8 frames the tile is gone.
        """
        out = {}
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row):
                if tile == TILE_CRUMBLING:
                    pixels = self._cell_pixels(x, y)
                    gone = next((i for i, b in enumerate(pixels) if b), 8)
                    if gone:
                        out[(x, y)] = gone
        return out

    def _switches(self) -> list[tuple[int, int]]:
        """The switches that are not flipped. Only the Kong Beast caverns have switches.

        The game has no flag for a switch. It draws a flipped switch with a
        different graphic, thus the code compares the pixels with the tile.
        """
        if self.cavern not in SWITCH_CAVERNS:
            return []
        graphic = bytes(self.emu.peek(ADDR_TILE_EXTRA + 1 + i) for i in range(8))
        if not hasattr(self, "_switch_cells") or self._switch_cells[0] != self.cavern:
            cells = [(c, r) for r in range(ROWS) for c in range(COLS) if self._cell_pixels(c, r) == graphic]
            self._switch_cells = (self.cavern, cells)
        return [cell for cell in self._switch_cells[1] if self._cell_pixels(*cell) == graphic]

    # -- control ---------------------------------------------------------------

    def _tick(self, joystick):
        self.emu.set_joystick(joystick)
        self.emu.run_until_tick()
        self.tick_count += 1

    def _finished(self):
        return self.is_dead() or self.is_complete()

    def _willy_cell_x(self):
        return self._cell(self._word(ADDR_WILLY_ATTR))[0]

    def _faces(self, joystick):
        """Does Willy look in the direction of this joystick input?"""
        looks_left = bool(self.emu.peek(ADDR_WILLY_DIR) & 1)
        return looks_left == bool(joystick & JOY_LEFT)

    def _against_conveyor(self, falling: bool) -> int:
        """The joystick direction against the conveyor that Willy stands on or falls to. If none, 0.

        A conveyor carries Willy along. He stands still on it only if the
        opposite direction is held when he lands on it, and for as long as
        it is held. After one tick with no key, the conveyor has him, and
        he cannot stop again.
        """
        if not self.hold_against_conveyor:
            return 0
        x, y = self._cell(self._word(ADDR_WILLY_ATTR))
        conveyor = self.emu.peek(ADDR_TILE_CONVEYOR)
        solid = {self.emu.peek(a) for a in (ADDR_TILE_FLOOR, ADDR_TILE_CRUMBLING, ADDR_TILE_WALL)}
        for column in (x, x + 1):
            for row in range(y + 2, ROWS if falling else y + 3):
                tile = self.emu.peek(EMPTY_ATTR_BUFFER + row * COLS + column)
                if tile == conveyor:
                    return JOY_LEFT if self.emu.peek(ADDR_CONVEYOR_DIR) else JOY_RIGHT
                if tile in solid:
                    break
        return 0

    def macro_ticks(self, name: str):
        """Run one macro, then wait until Willy is on the ground.

        This is a generator. It gives control back after each game tick, so
        that the viewer can show the screen.

        The game uses one tick to turn Willy when he looks the other way.
        A walk macro continues until Willy is 1 cell away and in line with
        the cell grid. A jump macro turns Willy first. Without this, a jump
        after a turn goes straight up, and a walk ends between two cells.
        """
        macro = MACROS[name]
        direction = macro.joystick & (JOY_LEFT | JOY_RIGHT)
        if macro.is_jump:
            if direction and not self._faces(direction) and not self._finished():
                self._tick(direction)  # turn
                yield
            for _ in range(macro.ticks):
                if self._finished():
                    break
                self._tick(macro.joystick)
                yield
        elif direction:
            start_x = self._willy_cell_x()
            for _ in range(2 * TICKS_PER_CELL):  # the limit applies at a wall
                if self._finished() or self.is_airborne():
                    break
                self._tick(macro.joystick)
                yield
                # Frame 0 is the grid position in the two directions.
                moved = self._willy_cell_x() != start_x
                if moved and self.emu.peek(ADDR_WILLY_FRAME) == 0:
                    break
        else:
            # A wait on a conveyor holds against it: "do not move".
            joystick = self._against_conveyor(falling=False)
            for _ in range(macro.ticks):
                if self._finished():
                    break
                self._tick(joystick)
                yield
        # Keep the direction during a jump. The game ignores it in the air,
        # but it is necessary if Willy lands and the jump is not complete.
        # A fall onto a conveyor holds against it, thus Willy stands still when
        # he lands. A direction has no effect in the air.
        hold = direction if macro.is_jump else self._against_conveyor(falling=True)
        for _ in range(MAX_SETTLE_TICKS):
            if self._finished() or not self.is_airborne():
                break
            self._tick(hold)
            yield
        self.emu.set_joystick(0)

    def run_macro(self, name: str) -> int:
        """Run one macro fully. Returns the number of game ticks that it used."""
        start = self.tick_count
        for _ in self.macro_ticks(name):
            pass
        return self.tick_count - start

    @staticmethod
    def _death_cause(snap: Snapshot) -> str:
        """The thing that killed Willy, from the positions at the death."""
        for g in snap.guardians:
            if abs(g.x - snap.willy_x) <= 2 and abs(g.y - snap.willy_y) <= 2:
                return "guardian"
        for y in range(snap.willy_y - 1, snap.willy_y + 3):
            for x in range(snap.willy_x - 1, snap.willy_x + 3):
                if 0 <= x < COLS and 0 <= y < ROWS and snap.tiles[y][x] == TILE_NASTY:
                    return "nasty"
        return "fall or other cause"

    def _can_survive(self, depth: int, budget: list) -> bool:
        """Can Willy stay alive for `depth` more macros from the current state?

        The check stops at the first sequence of macros that stays alive. It
        does not look for the target, thus it is not a search for a route.
        """
        if self.is_dead():
            return False
        if depth == 0 or self.is_complete():
            return True
        if budget[0] <= 0:
            # In open space the check finds a safe sequence in a small number
            # of tries. If the budget is gone, most sequences kill Willy.
            return False
        slot = DEAD_END_SLOT + depth
        ticks_before = self.tick_count
        self.emu.save_state(slot)
        alive = False
        for name in MACROS:
            budget[0] -= 1
            self.run_macro(name)
            alive = self._can_survive(depth - 1, budget)
            self.emu.load_state(slot)
            self.emu.set_joystick(0)
            self.tick_count = ticks_before
            if alive:
                break
        return alive

    def _willy_pixel(self) -> list[int]:
        x, _ = self._cell(self._word(ADDR_WILLY_ATTR))
        return [x * 8 + 2 * (self.emu.peek(ADDR_WILLY_FRAME) & 3), self.emu.peek(ADDR_WILLY_PIXEL_Y) // 2]

    def macro_paths(self) -> dict:
        """The path of Willy for each macro, for the viewer. The game does not change.

        Each path has the pixel position of Willy (top left) before the macro
        and after each game tick. `dead` tells that the macro kills Willy.
        """
        ticks_before = self.tick_count
        self.emu.save_state(LOOK_AHEAD_SLOT)
        paths = {}
        for name in MACROS:
            points = [self._willy_pixel()]
            for _ in self.macro_ticks(name):
                if self.is_dead() or self.is_complete():
                    break
                points.append(self._willy_pixel())
            paths[name] = {"points": points, "dead": self.is_dead()}
            self.emu.load_state(LOOK_AHEAD_SLOT)
            self.emu.set_joystick(0)
            self.tick_count = ticks_before
        return paths

    def look_ahead(self, survival_depth: int = SURVIVAL_DEPTH) -> dict[str, Outcome]:
        """Try each macro one time and give its result.

        The game goes back to the saved state after each try, thus the
        look-ahead does not change the game. This is a safety check. It is
        not a search for a route.

        A macro is also deadly if it is a dead end: Willy is alive after it,
        but no sequence of macros keeps him alive after that.
        """
        before = self.snapshot()
        ticks_before = self.tick_count
        self.emu.save_state(LOOK_AHEAD_SLOT)
        outcomes = {}
        for name in MACROS:
            ticks = self.run_macro(name)
            after = self.snapshot()
            dead, cause = self.is_dead(), ""
            if dead:
                cause = self._death_cause(after)
            elif survival_depth > 0 and not self._can_survive(survival_depth, [SURVIVAL_BUDGET]):
                dead, cause = True, DEAD_END_CAUSE
            outcomes[name] = Outcome(
                dead=dead,
                cause=cause,
                complete=self.is_complete(),
                dx=after.willy_x - before.willy_x,
                dy=before.willy_y - after.willy_y,
                keys_collected=len(before.keys) - len(after.keys),
                ticks=ticks,
                x=after.willy_x,
                y=after.willy_y,
                floor_rows_gone=self._floor_rows_gone(before, after),
            )
            self.emu.load_state(LOOK_AHEAD_SLOT)
            self.emu.set_joystick(0)
            self.tick_count = ticks_before
        return outcomes
