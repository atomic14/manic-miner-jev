"""Web server for the viewer.

Run:  uv run python -m jevmanic.server
Then open http://127.0.0.1:8000

The pages of the viewer:
    /               the recorded runs: a table with filters, and the totals for each cavern
    /watch          watch one run: a replay (?file=...) or a live run
    /compare        two recorded runs side by side (?a=...&b=...)
    /experiment     ask jev one key question for a situation, or start a live run
    /instructions   read the instruction sets, and write a new set

The page /watch and the server use one WebSocket. The server sends:
    text messages     JSON events
    binary messages   one PNG image of the game screen for each game tick
The page sends JSON commands: start, replay, stop, pause, resume, step, speed.
Text message types: hello, header, target, paths, decision, result, end, status, error.
"""

import asyncio
import io
import json
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import lab
from .brain import (
    DEFAULT_INSTRUCTIONS,
    FIXED_SETS,
    INSTRUCTIONS_DIR,
    MOVE_CRITERIA,
    Brain,
    instruction_files,
    instruction_sets,
    key_instructions,
    move_instructions,
    save_instruction_set,
)
from .game import SURVIVAL_DEPTH, Game
from .key_orders import OPTIMUM_KEY_ORDER
from .runner import Settings, list_run_groups, list_runs, play_live, play_replay, read_run

WEB_DIR = Path(__file__).resolve().parent / "web"
TICK_SECONDS = 0.08  # time for one game tick at speed 1

app = FastAPI()
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.middleware("http")
async def no_stale_pages(request, call_next):
    """The browser checks each page and script again, thus a changed file has effect at once."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
def runs_page():
    return FileResponse(WEB_DIR / "runs.html")


@app.get("/watch")
def watch_page():
    return FileResponse(WEB_DIR / "watch.html")


@app.get("/compare")
def compare_page():
    return FileResponse(WEB_DIR / "compare.html")


@app.get("/experiment")
def experiment_page():
    return FileResponse(WEB_DIR / "experiment.html")


@app.get("/lab")
def lab_page():  # the earlier name of the page
    return RedirectResponse("/experiment")


@app.get("/instructions")
def instructions_page():
    return FileResponse(WEB_DIR / "instructions.html")


# -- The recorded runs ---------------------------------------------------------------------


@app.get("/api/runs")
async def runs_list():
    """All recorded runs, their groups, and the names of the caverns."""
    game, _, lock = _lab_parts()
    async with lock:
        caverns = game.cavern_names()
    runs = list_runs()
    return {"runs": runs, "groups": list_run_groups(runs), "caverns": caverns}


@app.get("/api/run")
def run_records(file: str):
    """All records of one log file. A replay page gets the full run before it plays it."""
    try:
        return {"records": read_run(file)}
    except (ValueError, OSError) as error:
        return {"error": str(error)}


# -- The instruction sets ------------------------------------------------------------------


@app.get("/api/instructions")
def instructions_list():
    """All sets, each with its files and the text that jev gets from them."""
    sets = []
    for name in instruction_sets():
        sets.append(
            {
                "name": name,
                "fixed": name in FIXED_SETS,
                "files": instruction_files(name),
                "as_sent": {
                    "move.txt": move_instructions(name),
                    "key.txt": key_instructions(name, True),
                    "key_facts_only.txt": key_instructions(name, False),
                },
            }
        )
    return {"sets": sets, "default": DEFAULT_INSTRUCTIONS,
            "key_memory": (INSTRUCTIONS_DIR / "key_memory.txt").read_text(),
            "move_criteria": MOVE_CRITERIA}


@app.post("/api/instructions")
def instructions_save(msg: dict = Body(...)):
    try:
        save_instruction_set(str(msg.get("name", "")), msg.get("files", {}), bool(msg.get("replace", False)))
    except (ValueError, FileExistsError) as error:
        return {"error": str(error)}
    return {"saved": msg["name"], "sets": instruction_sets()}


# -- The key decision lab ------------------------------------------------------------------
# One game and one jev client for the lab. A lock keeps two requests apart.
_lab: dict = {}


def _lab_parts():
    if not _lab:
        _lab.update(game=Game(), brain=Brain(), lock=asyncio.Lock())
    return _lab["game"], _lab["brain"], _lab["lock"]


@app.get("/api/lab/info")
async def lab_info():
    """The names of the caverns and of the instruction sets."""
    game, _, lock = _lab_parts()
    async with lock:
        return {"caverns": game.cavern_names(), "instruction_sets": instruction_sets()}


@app.get("/api/lab/cavern/{cavern}")
async def lab_cavern(cavern: int):
    game, _, lock = _lab_parts()
    async with lock:
        return lab.cavern_info(game, max(0, min(19, cavern)))


@app.get("/api/lab/screen/{cavern}.png")
async def lab_screen(cavern: int):
    game, _, lock = _lab_parts()
    async with lock:
        game.select_cavern(max(0, min(19, cavern)))
        return Response(_png(game), media_type="image/png")


@app.get("/api/lab/instructions")
async def lab_instructions(name: str = DEFAULT_INSTRUCTIONS, with_map: bool = True):
    """The key instruction text of one set, as jev gets it."""
    name = name if name in instruction_sets() else DEFAULT_INSTRUCTIONS
    return {"text": key_instructions(name, with_map)}


@app.post("/api/lab/place")
async def lab_place(msg: dict = Body(...)):
    """The place where Willy can stand that is nearest to a click."""
    game, _, lock = _lab_parts()
    async with lock:
        snap = lab.situation(game, max(0, min(19, int(msg.get("cavern", 0)))), msg.get("willy"), "")
        return {"willy": [snap.willy_x, snap.willy_y]}


@app.post("/api/lab/ask")
async def lab_ask(msg: dict = Body(...)):
    game, brain, lock = _lab_parts()
    instructions = str(msg.get("instructions", DEFAULT_INSTRUCTIONS))
    async with lock:
        try:
            return await lab.ask(game, brain, max(0, min(19, int(msg.get("cavern", 0)))), msg.get("willy"),
                                 str(msg.get("collected", "")), bool(msg.get("with_map", True)),
                                 instructions if instructions in instruction_sets() else DEFAULT_INSTRUCTIONS,
                                 str(msg.get("custom_text", ""))[:6000])
        except Exception as error:  # show the error on the page
            return {"error": f"{type(error).__name__}: {error}"}


def _png(game: Game) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(game.screen_rgb()).save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


class Session:
    """The status of one viewer connection."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.game = Game()
        self.brain = Brain()
        self.task: asyncio.Task | None = None
        self.speed = 1.0  # 0 = as fast as possible
        self.running = asyncio.Event()  # clear = pause
        self.running.set()
        self.steps = 0  # decisions to run during a pause

    async def send(self, data: dict):
        await self.ws.send_text(json.dumps(data))

    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

    async def _gate(self):
        """Wait here during a pause. A step lets one decision through."""
        if self.running.is_set():
            return
        if self.steps > 0:
            self.steps -= 1
            return
        await self.send({"type": "status", "status": "paused"})
        while not self.running.is_set() and self.steps == 0:
            await asyncio.sleep(0.05)
        if self.steps > 0:
            self.steps -= 1

    async def run(self, events):
        try:
            async for kind, data in events:
                if kind == "frame":
                    await self.ws.send_bytes(_png(self.game))
                    if self.speed > 0:
                        await asyncio.sleep(TICK_SECONDS / self.speed)
                    continue
                await self.send(data)
                if data["type"] == "decision":
                    # The pause point is after a decision and before its macro runs,
                    # thus the viewer can show the possible moves and the selected one.
                    await self._gate()
        except Exception as error:  # show the error in the viewer
            await self.send({"type": "error", "message": f"{type(error).__name__}: {error}"})
            raise

    async def command(self, msg: dict):
        cmd = msg.get("cmd")
        if cmd == "start":
            await self.stop()
            self.steps = 0
            self.running.set()
            instructions = str(msg.get("instructions", DEFAULT_INSTRUCTIONS))
            settings = Settings(
                instructions=instructions if instructions in instruction_sets() else DEFAULT_INSTRUCTIONS,
                map_key_decision=bool(msg.get("map_key_decision", True)),
                survival_depth=max(0, min(20, int(msg.get("dead_end_depth", SURVIVAL_DEPTH)))),
                # The code sets the key order, and there is no key request. "" = jev selects the keys.
                forced_key_order="".join(c for c in str(msg.get("key_order", "")).upper() if c in "ABCDE"),
            )
            cavern = max(0, min(19, int(msg.get("cavern", 0))))
            self.task = asyncio.create_task(self.run(play_live(self.game, self.brain, cavern, settings, show_paths=True)))
        elif cmd == "replay":
            await self.stop()
            # With "paused", the replay stops at its first decision: the viewer jumps to that decision.
            self.steps = 0
            self.running.clear() if msg.get("paused") else self.running.set()
            start = max(0, int(msg.get("start", 0)))
            self.task = asyncio.create_task(self.run(play_replay(self.game, msg["file"], show_paths=True, start=start)))
        elif cmd == "stop":
            await self.stop()
            await self.send({"type": "status", "status": "stopped"})
        elif cmd == "pause":
            self.running.clear()
        elif cmd == "resume":
            self.running.set()
        elif cmd == "step":
            self.running.clear()
            self.steps += 1
        elif cmd == "speed":
            self.speed = float(msg.get("value", 1))


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    session = Session(ws)
    await session.send(
        {
            "type": "hello",
            "caverns": session.game.cavern_names(),
            "key_orders": OPTIMUM_KEY_ORDER,
            "instruction_sets": instruction_sets(),
        }
    )
    try:
        while True:
            await session.command(json.loads(await ws.receive_text()))
    except WebSocketDisconnect:
        pass
    finally:
        await session.stop()
        await session.brain.close()


def main():
    load_dotenv(".env")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
