from __future__ import annotations

import asyncio
import math
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable

LogHandler = Callable[[str], None]


@dataclass(slots=True)
class VolumeCommand:
    percent: int
    fade_seconds: float
    target_app: str | None
    completion: threading.Event | None = None


class MediaVolumeController:
    """Low-overhead, coalescing per-application Windows volume controller."""

    ALIASES = {
        "thorium.exe": ("Thorium", "Thorium.SGB43ZFAZXSTQM4BOAEQBITWUE"),
        "firefox.exe": ("308046B0AF4A39CB.exe", "Firefox"),
        "foobar2000.exe": ("foobar2000",),
        "YouTube Music.exe": ("com.github.th-ch.youtube-music", "youtube-music"),
    }

    def __init__(self, on_log: LogHandler | None = None) -> None:
        self.on_log = on_log or (lambda _: None)
        self._condition = threading.Condition()
        self._latest: VolumeCommand | None = None
        self._stopping = False
        self._thread = threading.Thread(
            target=self._run,
            name="CS2MC-Audio",
            daemon=True,
        )
        self._thread.start()
        self._available = os.name == "nt"
        self._last_target: str | None = None

    @property
    def available(self) -> bool:
        return self._available

    def set_volume(self, percent: int, fade_seconds: float, target_app: str | None) -> None:
        command = VolumeCommand(
            percent=max(0, min(100, int(percent))),
            fade_seconds=max(0.0, min(3.0, float(fade_seconds))),
            target_app=target_app or None,
        )
        with self._condition:
            self._latest = command
            self._condition.notify()

    def restore_and_stop(
        self,
        percent: int,
        target_app: str | None,
        timeout: float = 2.0,
    ) -> None:
        completion = threading.Event()
        with self._condition:
            self._latest = VolumeCommand(
                percent=max(0, min(100, int(percent))),
                fade_seconds=0.25,
                target_app=target_app or None,
                completion=completion,
            )
            self._condition.notify()
        completion.wait(timeout=timeout)
        with self._condition:
            self._stopping = True
            self._condition.notify()
        self._thread.join(timeout=timeout)

    def list_audio_sessions(self) -> list[dict[str, object]]:
        if os.name != "nt":
            return []
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities

            comtypes.CoInitialize()
            try:
                seen: set[str] = set()
                result: list[dict[str, object]] = []
                for session in AudioUtilities.GetAllSessions():
                    if not session.Process:
                        continue
                    name = session.Process.name()
                    if name in seen:
                        continue
                    seen.add(name)
                    result.append({"name": name, "active": session.State == 1})
                return sorted(result, key=lambda item: (not bool(item["active"]), str(item["name"]).casefold()))
            finally:
                comtypes.CoUninitialize()
        except Exception as exc:
            self.on_log(f"Could not enumerate audio sessions: {exc}")
            return []

    def _run(self) -> None:
        com_initialized = False
        try:
            if os.name == "nt":
                import comtypes

                comtypes.CoInitialize()
                com_initialized = True
            while True:
                with self._condition:
                    while self._latest is None and not self._stopping:
                        self._condition.wait()
                    if self._stopping and self._latest is None:
                        return
                    command = self._latest
                    self._latest = None
                if command is None:
                    continue
                try:
                    self._execute(command)
                except Exception as exc:
                    self.on_log(f"Audio control error: {exc}")
                finally:
                    if command.completion:
                        command.completion.set()
        finally:
            if com_initialized:
                try:
                    import comtypes

                    comtypes.CoUninitialize()
                except Exception:
                    pass

    def _execute(self, command: VolumeCommand) -> None:
        if os.name != "nt":
            self._available = False
            return
        try:
            volume, process_name = self._get_volume_control(command.target_app)
        except ImportError as exc:
            self._available = False
            self.on_log(f"Windows audio dependencies are unavailable: {exc}")
            return
        if volume is None:
            label = command.target_app or "active media player"
            self.on_log(f"No Windows audio session found for {label}.")
            return

        target = command.percent / 100.0
        current = float(volume.GetMasterVolume())
        self._last_target = process_name
        if math.isclose(current, target, abs_tol=0.005):
            return

        if command.fade_seconds <= 0.0:
            volume.SetMasterVolume(target, None)
            return

        frames = max(1, min(90, round(command.fade_seconds * 30)))
        step_time = command.fade_seconds / frames
        delta = target - current
        for index in range(1, frames + 1):
            with self._condition:
                if self._latest is not None:
                    return
            next_value = current + delta * (index / frames)
            volume.SetMasterVolume(max(0.0, min(1.0, next_value)), None)
            time.sleep(step_time)
        volume.SetMasterVolume(target, None)

    def _get_volume_control(self, target_app: str | None):
        from pycaw.pycaw import AudioUtilities

        resolved_target = target_app or self._get_active_media_process()
        if not resolved_target:
            return None, None
        wanted = resolved_target.casefold()
        candidates = []
        for session in AudioUtilities.GetAllSessions():
            if not session.Process:
                continue
            process_name = session.Process.name()
            if self._matches(process_name, wanted):
                candidates.append(session)
        if not candidates:
            return None, resolved_target
        active = next((session for session in candidates if session.State == 1), candidates[0])
        return active.SimpleAudioVolume, active.Process.name()

    def _matches(self, process_name: str, wanted: str) -> bool:
        process_lower = process_name.casefold()
        if process_lower == wanted:
            return True
        for key, aliases in self.ALIASES.items():
            key_lower = key.casefold()
            alias_lower = tuple(alias.casefold() for alias in aliases)
            if wanted == key_lower or any(alias in wanted for alias in alias_lower):
                return process_lower == key_lower or any(alias in process_lower for alias in alias_lower)
            if process_lower == key_lower and any(alias in wanted for alias in alias_lower):
                return True
        return process_lower in wanted or wanted in process_lower

    @staticmethod
    def _get_active_media_process() -> str | None:
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )
        except ImportError:
            return None

        async def resolve() -> str | None:
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if not session:
                return None
            app_name = session.source_app_user_model_id.split("!")[0]
            if ".exe" not in app_name.casefold():
                app_name += ".exe"
            return app_name

        try:
            return asyncio.run(resolve())
        except Exception:
            return None
