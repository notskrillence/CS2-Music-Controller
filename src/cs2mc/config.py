from __future__ import annotations

import copy
import json
import os
import secrets
import threading
import uuid
from dataclasses import replace
from pathlib import Path

from .models import (
    AppearanceSettings,
    DEFAULT_VOLUMES,
    KILL_STREAK_STEPS,
    KillStreakProfile,
    Profile,
    RuntimeSettings,
)

APP_DIR_NAME = "CS2MusicController"
BUILT_IN_KILL_STREAK_PROFILE_IDS = frozenset({"valorant", "reaver", "tones"})

KILL_STREAK_PACKS: dict[str, dict[str, object]] = {
    "valorant": {
        "name": "VALORANT",
        "files": (
            "valorant-1-kill.mp3",
            "valorant-2-kills.mp3",
            "valorant-3-kills.mp3",
            "valorant-4-kills.mp3",
            "valorant-5-kills.mp3",
        ),
    },
    "reaver": {
        "name": "Reaver",
        "files": tuple(f"reaverkill{i}.mp3" for i in range(1, 6)),
    },
    "tones": {
        "name": "Tones",
        "files": tuple(f"kill_{i}.wav" for i in range(1, 6)),
    },
}

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
    """Thread-safe audio-profile, kill-streak-profile, and settings persistence."""

    def __init__(self, root: Path | None = None, bundled_sounds: Path | None = None):
        self.root = root or app_data_dir()
        self.profiles_dir = self.root / "profiles"
        self.kill_streak_profiles_dir = self.root / "kill_streak_profiles"
        self.settings_path = self.root / "settings.json"
        self.bundled_sounds = bundled_sounds
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.kill_streak_profiles_dir.mkdir(parents=True, exist_ok=True)
        self._settings = self._load_settings()
        self._migrate_embedded_kill_streak_profiles()
        self._ensure_default_profile()
        self._ensure_default_kill_streak_profiles()

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
            active_kill_streak_profile_id=str(
                data.get("active_kill_streak_profile_id") or "tones"
            ),
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
            "active_kill_streak_profile_id": settings.active_kill_streak_profile_id,
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

    @staticmethod
    def _safe_id(value: str) -> str:
        return "".join(c for c in value if c.isalnum() or c in "-_")

    def _profile_path(self, profile_id: str) -> Path:
        return self.profiles_dir / f"{self._safe_id(profile_id)}.json"

    def _kill_streak_profile_path(self, profile_id: str) -> Path:
        return self.kill_streak_profiles_dir / f"{self._safe_id(profile_id)}.json"

    def _ensure_default_profile(self) -> None:
        if self._profile_path("default").exists():
            return
        self.save_profile(Profile(id="default", name="Balanced", volumes=dict(DEFAULT_VOLUMES)))

    def _bundled_sound_paths(self, filenames: tuple[str, ...]) -> dict[str, str]:
        if not self.bundled_sounds:
            return {key: "" for key in KILL_STREAK_STEPS}
        return {
            str(index): str(self.bundled_sounds / filename)
            for index, filename in enumerate(filenames, start=1)
        }

    def _ensure_default_kill_streak_profiles(self) -> None:
        for profile_id, definition in KILL_STREAK_PACKS.items():
            path = self._kill_streak_profile_path(profile_id)
            filenames = tuple(str(item) for item in definition["files"])
            bundled_paths = self._bundled_sound_paths(filenames)

            if not path.exists():
                self.save_kill_streak_profile(
                    KillStreakProfile(
                        id=profile_id,
                        name=str(definition["name"]),
                        sounds=bundled_paths,
                    )
                )
                continue

            # Built-in profiles store absolute asset paths. Repair only stale
            # bundled paths when the app is moved, upgraded, or installed to a
            # new directory. Existing custom replacements remain untouched.
            try:
                profile = KillStreakProfile.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                profile = KillStreakProfile(
                    id=profile_id,
                    name=str(definition["name"]),
                    sounds=bundled_paths,
                )

            changed = profile.name != str(definition["name"])
            profile.name = str(definition["name"])
            for index, filename in enumerate(filenames, start=1):
                key = str(index)
                current = profile.sounds.get(key, "")
                expected = bundled_paths.get(key, "")
                current_path = Path(current) if current else None
                is_stale_bundled_path = bool(
                    current_path
                    and current_path.name.casefold() == filename.casefold()
                    and not current_path.is_file()
                )
                if is_stale_bundled_path and expected:
                    profile.sounds[key] = expected
                    changed = True

            if changed:
                self.save_kill_streak_profile(profile)

    def _migrate_embedded_kill_streak_profiles(self) -> None:
        """Move pre-0.2.3 kill settings out of audio profile JSON files once."""
        active_audio_id = self._settings.active_profile_id
        active_kill_id = self._settings.active_kill_streak_profile_id
        migrated_active: str | None = None

        for path in sorted(self.profiles_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            legacy_keys = {
                "kill_streak_enabled",
                "kill_streak_volume",
                "kill_streak_sounds",
            }
            if not legacy_keys.intersection(data):
                continue

            sounds = {
                key: str(dict(data.get("kill_streak_sounds", {})).get(key, ""))
                for key in KILL_STREAK_STEPS
            }
            enabled = bool(data.get("kill_streak_enabled", True))
            try:
                volume = int(data.get("kill_streak_volume", 90))
            except (TypeError, ValueError):
                volume = 90

            filenames = tuple(Path(sounds[key]).name.casefold() for key in KILL_STREAK_STEPS)
            tones_filenames = tuple(f"kill_{i}.wav" for i in range(1, 6))
            all_blank = not any(sounds.values())
            is_bundled_tones = filenames == tones_filenames and enabled and volume == 90

            if is_bundled_tones or all_blank:
                migrated_id = "tones"
            else:
                source_id = str(data.get("id") or path.stem)
                migrated_id = f"migrated_{self._safe_id(source_id)}"
                migrated_path = self._kill_streak_profile_path(migrated_id)
                if not migrated_path.exists():
                    source_name = str(data.get("name") or "Imported")
                    self._atomic_write(
                        migrated_path,
                        KillStreakProfile(
                            id=migrated_id,
                            name=f"{source_name} Kill Streaks",
                            enabled=enabled,
                            volume=volume,
                            sounds=sounds,
                        ).to_dict(),
                    )

            if str(data.get("id") or path.stem) == active_audio_id:
                migrated_active = migrated_id

            for key in legacy_keys:
                data.pop(key, None)
            self._atomic_write(path, data)

        if migrated_active and active_kill_id == "tones":
            self._settings = replace(
                self._settings,
                active_kill_streak_profile_id=migrated_active,
            )
            self._write_settings(self._settings)

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

    # Audio profiles -----------------------------------------------------

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

    # Kill-streak profiles -----------------------------------------------

    def list_kill_streak_profiles(self) -> list[KillStreakProfile]:
        with self._lock:
            profiles: list[KillStreakProfile] = []
            for path in sorted(self.kill_streak_profiles_dir.glob("*.json")):
                try:
                    profiles.append(
                        KillStreakProfile.from_dict(json.loads(path.read_text("utf-8")))
                    )
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    continue
            built_in_order = {"valorant": 0, "reaver": 1, "tones": 2}
            return sorted(
                profiles,
                key=lambda item: (
                    built_in_order.get(item.id, 100),
                    item.name.casefold(),
                ),
            )

    def get_kill_streak_profile(self, profile_id: str) -> KillStreakProfile:
        with self._lock:
            path = self._kill_streak_profile_path(profile_id)
            if not path.exists():
                path = self._kill_streak_profile_path("tones")
            data = json.loads(path.read_text(encoding="utf-8"))
            return KillStreakProfile.from_dict(data)

    def active_kill_streak_profile(self) -> KillStreakProfile:
        return self.get_kill_streak_profile(self.settings.active_kill_streak_profile_id)

    def save_kill_streak_profile(self, profile: KillStreakProfile) -> KillStreakProfile:
        with self._lock:
            profile.normalized()
            self._atomic_write(
                self._kill_streak_profile_path(profile.id),
                profile.to_dict(),
            )
            return copy.deepcopy(profile)

    def set_active_kill_streak_profile(self, profile_id: str) -> KillStreakProfile:
        profile = self.get_kill_streak_profile(profile_id)
        with self._lock:
            self._settings = replace(
                self._settings,
                active_kill_streak_profile_id=profile.id,
            )
            self._write_settings(self._settings)
        return profile

    def create_kill_streak_profile(
        self,
        name: str,
        source: KillStreakProfile | None = None,
    ) -> KillStreakProfile:
        with self._lock:
            profile_id = uuid.uuid4().hex[:12]
            if source:
                data = source.to_dict()
                data.update({"id": profile_id, "name": name.strip() or "New Sound Profile"})
                profile = KillStreakProfile.from_dict(data)
            else:
                profile = KillStreakProfile(
                    id=profile_id,
                    name=name.strip() or "New Sound Profile",
                )
            return self.save_kill_streak_profile(profile)

    def rename_kill_streak_profile(
        self,
        profile_id: str,
        name: str,
    ) -> KillStreakProfile:
        if profile_id in BUILT_IN_KILL_STREAK_PROFILE_IDS:
            raise ValueError("Bundled sound-profile names are fixed.")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Sound profile name cannot be empty.")
        with self._lock:
            profile = self.get_kill_streak_profile(profile_id)
            profile.name = clean_name
            return self.save_kill_streak_profile(profile)

    def delete_kill_streak_profile(self, profile_id: str) -> None:
        if profile_id in BUILT_IN_KILL_STREAK_PROFILE_IDS:
            raise ValueError("Bundled sound profiles cannot be deleted.")
        with self._lock:
            path = self._kill_streak_profile_path(profile_id)
            if path.exists():
                path.unlink()
            if self._settings.active_kill_streak_profile_id == profile_id:
                self._settings = replace(
                    self._settings,
                    active_kill_streak_profile_id="tones",
                )
                self._write_settings(self._settings)
