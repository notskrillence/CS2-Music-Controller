from __future__ import annotations

import copy
import json
import os
import secrets
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from .models import AppearanceSettings, DEFAULT_VOLUMES, Profile, RuntimeSettings

APP_DIR_NAME = "CS2MusicController"

PRESETS: dict[str, dict] = {
    "Balanced": {
        "description": "Clear gameplay with audible music between rounds.",
        "volumes": {
            "menu": 100,
            "game": 14,
            "buy_phase": 42,
            "spectating": 85,
            "bomb_planted": 5,
            "round_over": 70,
            "warmup": 100,
        },
        "fade_duration": 0.7,
    },
    "Focus": {
        "description": "Minimal music during live rounds and bomb pressure.",
        "volumes": {
            "menu": 90,
            "game": 6,
            "buy_phase": 28,
            "spectating": 65,
            "bomb_planted": 0,
            "round_over": 55,
            "warmup": 85,
        },
        "fade_duration": 0.35,
    },
    "Cinematic": {
        "description": "More music throughout the match with smooth fades.",
        "volumes": {
            "menu": 100,
            "game": 28,
            "buy_phase": 62,
            "spectating": 100,
            "bomb_planted": 12,
            "round_over": 90,
            "warmup": 100,
        },
        "fade_duration": 1.2,
    },
}


def app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / APP_DIR_NAME


class ProfileStore:
    """Thread-safe profile and application settings persistence."""

    def __init__(self, root: Path | None = None, bundled_sounds: Path | None = None):
        self.root = root or app_data_dir()
        self.profiles_dir = self.root / "profiles"
        self.settings_path = self.root / "settings.json"
        self.bundled_sounds = bundled_sounds
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._settings = self._load_settings()
        self._ensure_default_profile()

    def _load_settings(self) -> RuntimeSettings:
        data: dict = {}
        if self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        token = str(data.get("gsi_token") or secrets.token_urlsafe(24))
        try:
            port = int(data.get("port", 1337))
        except (TypeError, ValueError):
            port = 1337
        port = max(1024, min(65535, port))
        settings = RuntimeSettings(
            active_profile_id=str(data.get("active_profile_id") or "default"),
            cs2_cfg_path=str(data.get("cs2_cfg_path") or ""),
            gsi_token=token,
            port=port,
            appearance=AppearanceSettings.from_dict(data.get("appearance")),
        )
        self._write_settings(settings)
        return settings

    def _write_settings(self, settings: RuntimeSettings) -> None:
        payload = {
            "active_profile_id": settings.active_profile_id,
            "cs2_cfg_path": settings.cs2_cfg_path,
            "gsi_token": settings.gsi_token,
            "port": settings.port,
            "appearance": settings.appearance.to_dict(),
        }
        self._atomic_write(self.settings_path, payload)

    @staticmethod
    def _atomic_write(path: Path, payload: dict) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(path)

    def _profile_path(self, profile_id: str) -> Path:
        safe_id = "".join(c for c in profile_id if c.isalnum() or c in "-_" )
        return self.profiles_dir / f"{safe_id}.json"

    def _ensure_default_profile(self) -> None:
        if self._profile_path("default").exists():
            return
        sounds = self.bundled_sounds
        streaks = {str(i): "" for i in range(1, 6)}
        if sounds:
            for i in range(1, 6):
                candidate = sounds / f"kill_{i}.wav"
                if candidate.exists():
                    streaks[str(i)] = str(candidate)
        default = Profile(
            id="default",
            name="Balanced",
            volumes=dict(DEFAULT_VOLUMES),
            kill_streak_sounds=streaks,
        )
        self.save_profile(default)

    @property
    def settings(self) -> RuntimeSettings:
        with self._lock:
            return replace(self._settings)

    def set_cfg_path(self, path: str) -> None:
        with self._lock:
            self._settings = replace(self._settings, cs2_cfg_path=path)
            self._write_settings(self._settings)

    def set_port(self, port: int) -> None:
        with self._lock:
            self._settings = replace(self._settings, port=port)
            self._write_settings(self._settings)

    def set_appearance(self, appearance: AppearanceSettings) -> AppearanceSettings:
        clean = appearance.normalized()
        with self._lock:
            self._settings = replace(self._settings, appearance=clean)
            self._write_settings(self._settings)
        return clean

    def list_profiles(self) -> list[Profile]:
        with self._lock:
            profiles: list[Profile] = []
            for path in sorted(self.profiles_dir.glob("*.json")):
                try:
                    profiles.append(Profile.from_dict(json.loads(path.read_text("utf-8"))))
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    continue
            return sorted(profiles, key=lambda item: item.name.casefold())

    def get_profile(self, profile_id: str) -> Profile:
        with self._lock:
            path = self._profile_path(profile_id)
            if not path.exists():
                path = self._profile_path("default")
            data = json.loads(path.read_text(encoding="utf-8"))
            return Profile.from_dict(data)

    def active_profile(self) -> Profile:
        return self.get_profile(self.settings.active_profile_id)

    def save_profile(self, profile: Profile) -> Profile:
        with self._lock:
            profile.normalized()
            self._atomic_write(self._profile_path(profile.id), profile.to_dict())
            return copy.deepcopy(profile)

    def set_active_profile(self, profile_id: str) -> Profile:
        profile = self.get_profile(profile_id)
        with self._lock:
            self._settings = replace(self._settings, active_profile_id=profile.id)
            self._write_settings(self._settings)
        return profile

    def create_profile(self, name: str, source: Profile | None = None) -> Profile:
        with self._lock:
            profile_id = uuid.uuid4().hex[:12]
            if source:
                data = source.to_dict()
                data.update({"id": profile_id, "name": name.strip() or "New Profile"})
                profile = Profile.from_dict(data)
            else:
                profile = Profile(id=profile_id, name=name.strip() or "New Profile")
            return self.save_profile(profile)

    def rename_profile(self, profile_id: str, name: str) -> Profile:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Profile name cannot be empty.")
        with self._lock:
            profile = self.get_profile(profile_id)
            profile.name = clean_name
            return self.save_profile(profile)

    def delete_profile(self, profile_id: str) -> None:
        if profile_id == "default":
            raise ValueError("The default profile cannot be deleted.")
        with self._lock:
            path = self._profile_path(profile_id)
            if path.exists():
                path.unlink()
            if self._settings.active_profile_id == profile_id:
                self._settings = replace(self._settings, active_profile_id="default")
                self._write_settings(self._settings)

    def apply_preset(self, profile: Profile, preset_name: str) -> Profile:
        if preset_name not in PRESETS:
            raise KeyError(preset_name)
        preset = PRESETS[preset_name]
        profile.volumes = dict(preset["volumes"])
        profile.fade_duration = float(preset["fade_duration"])
        return self.save_profile(profile)

    def import_profile(self, source_path: Path) -> Profile:
        data = json.loads(source_path.read_text(encoding="utf-8"))
        profile = Profile.from_dict(data)
        profile.id = uuid.uuid4().hex[:12]
        return self.save_profile(profile)

    def export_profile(self, profile: Profile, destination: Path) -> None:
        self._atomic_write(destination, profile.to_dict())

    def profiles_by_id(self) -> dict[str, Profile]:
        return {profile.id: profile for profile in self.list_profiles()}
