"""Tests of the viewer (jevmanic/server.py) that need no jev calls."""

from fastapi.testclient import TestClient

from jevmanic import server


def test_the_viewer_lists_and_replays_runs_without_an_api_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    client = TestClient(server.app)
    runs = client.get("/api/runs").json()["runs"]
    demo = next(r["file"] for r in runs if r["file"].startswith("cavern-01"))
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"cmd": "speed", "value": 0})
        ws.send_json({"cmd": "replay", "file": demo})
        types = set()
        while "decision" not in types:
            message = ws.receive()
            if "text" in message:
                data = server.json.loads(message["text"])
                assert data["type"] != "error", data
                types.add(data["type"])
        ws.send_json({"cmd": "stop"})
