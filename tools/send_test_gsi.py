"""Send a synthetic CS2 GSI payload to a locally running development build."""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path


def settings_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return root / "CS2MusicController" / "settings.json"


def make_payload(state: str, kills: int, round_no: int, token: str) -> dict:
    payload = {
        "auth": {"token": token},
        "provider": {"appid": 730, "steamid": "76561198000000000"},
        "map": {"round": round_no, "phase": "live"},
        "round": {"phase": "live"},
        "player": {
            "steamid": "76561198000000000",
            "activity": "playing",
            "state": {"health": 100, "round_kills": kills},
        },
    }
    if state == "menu":
        payload["player"]["activity"] = "menu"
    elif state == "buy_phase":
        payload["round"]["phase"] = "freezetime"
    elif state == "spectating":
        payload["player"]["state"]["health"] = 0
    elif state == "bomb_planted":
        payload["round"]["bomb"] = "planted"
    elif state == "round_over":
        payload["round"]["phase"] = "over"
    elif state == "warmup":
        payload["map"]["phase"] = "warmup"
        payload["round"].pop("phase", None)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "state",
        choices=["menu", "game", "buy_phase", "spectating", "bomb_planted", "round_over", "warmup"],
    )
    parser.add_argument("--kills", type=int, default=0)
    parser.add_argument("--round", type=int, default=4, dest="round_no")
    args = parser.parse_args()

    path = settings_path()
    if not path.exists():
        raise SystemExit("Launch CS2 Music Controller once before using the simulator.")
    settings = json.loads(path.read_text("utf-8"))
    port = int(settings.get("port", 1337))
    token = str(settings["gsi_token"])
    payload = make_payload(args.state, max(0, args.kills), args.round_no, token)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/gsi",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        print(response.read().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
