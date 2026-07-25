from __future__ import annotations

from itertools import count
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .windows_sound_backend import PlaybackHandle, WindowsSoundBackend


class SoundPlayer(QObject):
    """Overlapping local WAV/MP3 playback without QtMultimedia.

    Windows MCI supplies the codec and playback layer. Qt owns only the cleanup
    timers, keeping the interface package on PySide6-Essentials.
    """

    playback_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend = WindowsSoundBackend()
        self._active: dict[int, PlaybackHandle] = {}
        self._timers: dict[int, QTimer] = {}
        self._tokens = count(1)

    def play(self, path: str, volume_percent: int) -> None:
        source = Path(path)
        if not path or not source.is_file():
            return

        volume = max(0.0, min(1.0, volume_percent / 100.0))
        try:
            handle = self._backend.play(source, volume)
        except Exception as exc:
            # Keep GSI handling stable, but expose the concrete failure instead
            # of making a broken Test button appear to do nothing.
            self.playback_failed.emit(f"Could not play {source.name}: {exc}")
            return

        token = next(self._tokens)
        self._active[token] = handle

        # Keep the timer parented and referenced. Static singleShot callbacks can
        # be lost during shutdown and gave no way to cancel cleanup explicitly.
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda current=token: self._release(current))
        timer.start(handle.duration_ms)
        self._timers[token] = timer

    def close_all(self) -> None:
        for token in tuple(self._active):
            self._release(token)

    def _release(self, token: int) -> None:
        timer = self._timers.pop(token, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        handle = self._active.pop(token, None)
        if handle is not None:
            self._backend.close(handle)
