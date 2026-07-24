from __future__ import annotations

import copy
import threading
import time
from pathlib import Path
from typing import Callable

from .audio_controller import MediaVolumeController
from .config import ProfileStore
from .gsi_server import GSIServer
from .media_session import MediaSessionMonitor
from .models import GameSnapshot, MediaSnapshot, Profile, STATE_LABELS
from .state_engine import GameStateResolver

SnapshotHandler = Callable[[GameSnapshot], None]
SoundHandler = Callable[[str, int], None]
LogHandler = Callable[[str], None]
MediaHandler = Callable[[MediaSnapshot], None]


class RuntimeController:
    def __init__(
        self,
        store: ProfileStore,
        on_snapshot: SnapshotHandler,
        on_sound: SoundHandler,
        on_log: LogHandler | None = None,
        on_media: MediaHandler | None = None,
    ) -> None:
        self.store = store
        self.on_snapshot = on_snapshot
        self.on_sound = on_sound
        self.on_log = on_log or (lambda _: None)
        self.audio = MediaVolumeController(self.on_log)
        self.media = MediaSessionMonitor(on_media or (lambda _: None), self.on_log)
        self.resolver = GameStateResolver()
        self._profile_lock = threading.RLock()
        self._profile = store.active_profile()
        self._current_state = "menu"
        self._last_applied_state: str | None = None
        self._last_snapshot_at = 0.0
        settings = store.settings
        self.server = GSIServer(
            port=settings.port,
            token=settings.gsi_token,
            on_payload=self._handle_payload,
            on_log=self.on_log,
        )

    def start(self) -> None:
        try:
            self.server.start()
        except OSError as exc:
            self.on_log(f"Could not start the GSI listener: {exc}")
        self.media.start()

    def stop(self) -> None:
        self.media.stop()
        self.server.stop()
        with self._profile_lock:
            profile = copy.deepcopy(self._profile)
        restore = profile.volumes.get("menu", 100)
        self.audio.restore_and_stop(restore, profile.target_app)

    def active_profile(self) -> Profile:
        with self._profile_lock:
            return copy.deepcopy(self._profile)

    def update_profile(self, profile: Profile, apply_current_state: bool = True) -> None:
        with self._profile_lock:
            self._profile = copy.deepcopy(profile.normalized())
            current = copy.deepcopy(self._profile)
        if apply_current_state:
            volume = current.volumes.get(self._current_state, current.volumes["menu"])
            self.audio.set_volume(volume, current.fade_duration, current.target_app)
            self._emit_snapshot(current, self._current_state, connected=False)

    def list_audio_sessions(self) -> list[dict[str, object]]:
        return self.audio.list_audio_sessions()

    def _handle_payload(self, payload: dict) -> None:
        update = self.resolver.process(payload)
        if update is None:
            return
        self._current_state = update.state
        with self._profile_lock:
            profile = copy.deepcopy(self._profile)

        should_apply = update.state_changed or self._last_applied_state is None
        if should_apply:
            volume = profile.volumes.get(update.state, profile.volumes["menu"])
            self.audio.set_volume(volume, profile.fade_duration, profile.target_app)
            self._last_applied_state = update.state
            sound_path = profile.event_sounds.get(update.state, "")
            if profile.event_sounds_enabled and self._sound_exists(sound_path):
                self.on_sound(sound_path, profile.event_sound_volume)

        if update.kill_streak is not None and profile.kill_streak_enabled:
            streak_key = str(min(5, max(1, update.kill_streak)))
            streak_sound = profile.kill_streak_sounds.get(streak_key, "")
            if self._sound_exists(streak_sound):
                self.on_sound(streak_sound, profile.kill_streak_volume)

        now = time.monotonic()
        if should_apply or update.kill_streak is not None or now - self._last_snapshot_at >= 0.5:
            self._last_snapshot_at = now
            snapshot = GameSnapshot(
                state=update.state,
                state_label=STATE_LABELS.get(update.state, update.state),
                music_volume=profile.volumes.get(update.state, profile.volumes["menu"]),
                connected=True,
                round_kills=update.round_kills,
                map_round=update.map_round,
                health=update.health,
                bomb_state=update.bomb_state,
            )
            self.on_snapshot(snapshot)

    def _emit_snapshot(self, profile: Profile, state: str, connected: bool) -> None:
        snapshot = GameSnapshot(
            state=state,
            state_label=STATE_LABELS.get(state, state),
            music_volume=profile.volumes.get(state, profile.volumes["menu"]),
            connected=connected,
        )
        self.on_snapshot(snapshot)

    @staticmethod
    def _sound_exists(path: str) -> bool:
        return bool(path) and Path(path).is_file()
