from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATE_KEYS = (
    "menu",
    "game",
    "buy_phase",
    "spectating",
    "bomb_planted",
    "round_over",
    "warmup",
)

STATE_LABELS = {
    "menu": "Menu",
    "game": "In Game",
    "buy_phase": "Buy Time",
    "spectating": "Spectating",
    "bomb_planted": "Bomb Planted",
    "round_over": "Round Over",
    "warmup": "Warmup",
}

DEFAULT_VOLUMES = {
    "menu": 100,
    "game": 14,
    "buy_phase": 42,
    "spectating": 85,
    "bomb_planted": 5,
    "round_over": 70,
    "warmup": 100,
}


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    volumes: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_VOLUMES))
    fade_duration: float = 0.7
    target_app: str | None = None
    event_sounds_enabled: bool = False
    event_sound_volume: int = 70
    event_sounds: dict[str, str] = field(
        default_factory=lambda: {key: "" for key in STATE_KEYS}
    )
    kill_streak_enabled: bool = True
    kill_streak_volume: int = 90
    kill_streak_sounds: dict[str, str] = field(
        default_factory=lambda: {str(i): "" for i in range(1, 6)}
    )

    def normalized(self) -> "Profile":
        clean_volumes: dict[str, int] = {}
        for key in STATE_KEYS:
            try:
                value = int(self.volumes.get(key, DEFAULT_VOLUMES[key]))
            except (TypeError, ValueError):
                value = DEFAULT_VOLUMES[key]
            clean_volumes[key] = max(0, min(100, value))
        self.volumes = clean_volumes

        self.fade_duration = max(0.0, min(3.0, float(self.fade_duration)))
        self.event_sound_volume = max(0, min(100, int(self.event_sound_volume)))
        self.kill_streak_volume = max(0, min(100, int(self.kill_streak_volume)))

        self.event_sounds = {
            key: str(self.event_sounds.get(key, "")) for key in STATE_KEYS
        }
        self.kill_streak_sounds = {
            str(i): str(self.kill_streak_sounds.get(str(i), ""))
            for i in range(1, 6)
        }
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        profile = cls(
            id=str(data.get("id", "default")),
            name=str(data.get("name", "Default")),
            volumes=dict(data.get("volumes", DEFAULT_VOLUMES)),
            fade_duration=float(data.get("fade_duration", 0.7)),
            target_app=data.get("target_app") or None,
            event_sounds_enabled=bool(data.get("event_sounds_enabled", False)),
            event_sound_volume=int(data.get("event_sound_volume", 70)),
            event_sounds=dict(data.get("event_sounds", {})),
            kill_streak_enabled=bool(data.get("kill_streak_enabled", True)),
            kill_streak_volume=int(data.get("kill_streak_volume", 90)),
            kill_streak_sounds=dict(data.get("kill_streak_sounds", {})),
        )
        return profile.normalized()


@dataclass(frozen=True, slots=True)
class AppearanceSettings:
    mode: str = "album"
    seed_color: str = "#d6a24a"
    contrast: int = 6
    surface_darkness: int = 96
    corner_radius: int = 16
    aura_strength: int = 18
    animations: bool = True

    def normalized(self) -> "AppearanceSettings":
        mode = self.mode if self.mode in {"dark", "album", "custom"} else "album"
        seed = self.seed_color if _is_hex_color(self.seed_color) else "#d6a24a"
        return AppearanceSettings(
            mode=mode,
            seed_color=seed.lower(),
            contrast=max(-20, min(30, int(self.contrast))),
            surface_darkness=max(88, min(100, int(self.surface_darkness))),
            corner_radius=max(10, min(24, int(self.corner_radius))),
            aura_strength=max(0, min(40, int(self.aura_strength))),
            animations=bool(self.animations),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppearanceSettings":
        data = data or {}
        return cls(
            mode=str(data.get("mode", "album")),
            seed_color=str(data.get("seed_color", "#d6a24a")),
            contrast=int(data.get("contrast", 6)),
            surface_darkness=int(data.get("surface_darkness", 96)),
            corner_radius=int(data.get("corner_radius", 16)),
            aura_strength=int(data.get("aura_strength", 18)),
            animations=bool(data.get("animations", True)),
        ).normalized()


def _is_hex_color(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    active_profile_id: str
    cs2_cfg_path: str
    gsi_token: str
    port: int = 1337
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    state: str
    state_label: str
    music_volume: int
    connected: bool
    round_kills: int = 0
    map_round: int | None = None
    health: int | None = None
    bomb_state: str = ""




@dataclass(frozen=True, slots=True)
class MediaSnapshot:
    title: str = ""
    artist: str = ""
    app: str = ""
    artwork: bytes | None = None

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.title, self.artist, self.app)


@dataclass(frozen=True, slots=True)
class StateUpdate:
    state: str
    state_changed: bool
    round_kills: int
    kill_streak: int | None
    map_round: int | None
    health: int | None
    bomb_state: str


def resolve_asset_path(relative_path: str) -> Path:
    """Resolve bundled assets in source and PyInstaller builds."""
    import sys

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative_path
