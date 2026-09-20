"""Web server for the viewer.

Run:  uv run python -m jevmanic.server
Then open http://127.0.0.1:8000

The page and the server use one WebSocket. The server sends:
    text messages     JSON events (header, decision, result, end, runs, status)
    binary messages   one PNG image of the game screen for each game tick
The page sends JSON commands: start, replay, stop, pause, resume, step, speed.
Text message types: hello, header, target, decision, result, end, runs, status, error.
"""

import asyncio
import io
import json
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from PIL import Image

from .brain import Brain
from .game import Game
from .runner import Settings, list_run_groups, list_runs, play_live, play_replay

WEB_DIR = Path(__file__).resolve().parent / "web"
TICK_SECONDS = 0.08  # time for one game tick at speed 1

app = FastAPI()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


def _png(game: Game) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(game.screen_rgb()).save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def _runs_message() -> dict:
    runs = list_runs()
    return {"type": "runs", "runs": runs, "groups": list_run_groups(runs)}


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
                if data["type"] == "result":
                    # The pause point is between decisions.
                    await self._gate()
                if data["type"] == "end":
                    await self.send(_runs_message())
        except Exception as error:  # show the error in the viewer
            await self.send({"type": "error", "message": f"{type(error).__name__}: {error}"})
            raise

    async def command(self, msg: dict):
        cmd = msg.get("cmd")
        if cmd == "start":
            await self.stop()
            settings = Settings(
                rules_mode=bool(msg.get("rules_mode", False)),
                map_key_decision=bool(msg.get("map_key_decision", True)),
                survival_depth=max(0, min(20, int(msg.get("dead_end_depth", 12)))),
            )
            cavern = max(0, min(19, int(msg.get("cavern", 0))))
            self.task = asyncio.create_task(self.run(play_live(self.game, self.brain, cavern, settings)))
        elif cmd == "replay":
            await self.stop()
            self.task = asyncio.create_task(self.run(play_replay(self.game, msg["file"])))
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
            **_runs_message(),
            "type": "hello",
            "caverns": session.game.cavern_names(),
        }
    )
    await ws.send_bytes(_png(session.game))
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
