from __future__ import annotations

from typing import Any

from .models import StateUpdate


class GameStateResolver:
    """Convert CS2 GSI payloads into stable application states and kill events."""

    def __init__(self) -> None:
        self._state = "menu"
        self._round_kills = 0
        self._map_round: int | None = None

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def process(self, data: dict[str, Any]) -> StateUpdate | None:
        provider = data.get("provider") or {}
        if self._safe_int(provider.get("appid"), 0) != 730:
            return None

        player = data.get("player") or {}
        activity = str(player.get("activity") or "")
        map_data = data.get("map") or {}
        round_data = data.get("round") or {}
        player_state = player.get("state") or {}

        provider_steamid = str(provider.get("steamid") or "")
        player_steamid = str(player.get("steamid") or "")
        map_round_raw = map_data.get("round")
        map_round = self._safe_int(map_round_raw) if map_round_raw is not None else None

        if map_round is not None and self._map_round is not None and map_round != self._map_round:
            self._round_kills = 0
        if map_round is not None:
            self._map_round = map_round

        if activity == "menu":
            state = "menu"
        elif provider_steamid and player_steamid and player_steamid != provider_steamid:
            state = "spectating"
        else:
            phase = str(round_data.get("phase") or "")
            health = self._safe_int(player_state.get("health"), 100)
            bomb = str(round_data.get("bomb") or "")
            map_phase = str(map_data.get("phase") or "")

            if phase == "over":
                state = "round_over"
            elif map_phase == "warmup" or (not phase and player):
                state = "warmup"
            elif phase and phase != "live":
                state = "buy_phase"
            elif health <= 0:
                state = "spectating"
            elif bomb == "planted":
                state = "bomb_planted"
            elif player:
                state = "game"
            else:
                state = "menu"

        health_value = None
        if player_state.get("health") is not None:
            health_value = self._safe_int(player_state.get("health"), 0)
        bomb_state = str(round_data.get("bomb") or "")

        current_round_kills = self._safe_int(player_state.get("round_kills"), 0)
        kill_streak: int | None = None
        is_local_player = not player_steamid or not provider_steamid or player_steamid == provider_steamid
        if is_local_player and current_round_kills > self._round_kills:
            kill_streak = current_round_kills
        if is_local_player:
            self._round_kills = current_round_kills

        changed = state != self._state
        self._state = state
        return StateUpdate(
            state=state,
            state_changed=changed,
            round_kills=current_round_kills,
            kill_streak=kill_streak,
            map_round=map_round,
            health=health_value,
            bomb_state=bomb_state,
        )
