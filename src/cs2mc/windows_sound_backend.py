from __future__ import annotations

import ctypes
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class PlaybackHandle:
    """Owns one asynchronous Windows MCI playback alias."""

    alias: str
    duration_ms: int = 45_000


class WindowsSoundBackend:
    """Small Windows-native WAV/MP3 backend using WinMM MCI.

    MCI is part of Windows, supports asynchronous local-file playback, and does
    not require QtMultimedia or the WinRT media-playback packages. Each playback
    gets a unique alias so rapid kill sounds and Test clicks may overlap.
    """

    _BUFFER_CHARS = 512

    def __init__(self, command: Callable[[str, int], str] | None = None) -> None:
        self._aliases = count(1)
        self._command_override = command
        self._winmm: Any | None = None

    def play(self, path: Path, volume: float) -> PlaybackHandle:
        source = path.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)

        alias = f"cs2mc_sound_{next(self._aliases)}"
        media_type = self._media_type(source)
        quoted_path = str(source).replace('"', '""')

        try:
            self._send(f'open "{quoted_path}" type {media_type} alias {alias}')
            self._send(f"set {alias} time format milliseconds")

            # MCI volume uses a 0-1000 scale. Some installed codecs may not
            # support setaudio; playback should still continue at system volume.
            mci_volume = round(max(0.0, min(1.0, volume)) * 1000)
            try:
                self._send(f"setaudio {alias} volume to {mci_volume}")
            except RuntimeError:
                pass

            duration_ms = self._duration(alias)
            self._send(f"play {alias} from 0")
            return PlaybackHandle(alias=alias, duration_ms=duration_ms)
        except Exception:
            self._close_alias(alias)
            raise

    def close(self, handle: PlaybackHandle) -> None:
        self._close_alias(handle.alias)

    @staticmethod
    def _media_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".wav":
            return "waveaudio"
        if suffix in {".mp3", ".mpeg", ".mpg"}:
            return "mpegvideo"
        raise ValueError(f"Unsupported audio format: {suffix or '<none>'}")

    def _duration(self, alias: str) -> int:
        try:
            value = self._send(f"status {alias} length")
            duration = int(value.strip())
        except (RuntimeError, ValueError):
            return 45_000
        return max(250, min(duration + 750, 120_000))

    def _close_alias(self, alias: str) -> None:
        try:
            self._send(f"stop {alias}")
        except RuntimeError:
            pass
        try:
            self._send(f"close {alias}")
        except RuntimeError:
            pass

    def _send(self, command: str) -> str:
        if self._command_override is not None:
            return self._command_override(command, self._BUFFER_CHARS)

        if self._winmm is None:
            if not hasattr(ctypes, "windll"):
                raise RuntimeError("Windows MCI playback is only available on Windows")
            self._winmm = ctypes.windll.winmm
            self._winmm.mciSendStringW.argtypes = [
                ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_wchar),
                ctypes.c_uint,
                ctypes.c_void_p,
            ]
            self._winmm.mciSendStringW.restype = ctypes.c_uint
            self._winmm.mciGetErrorStringW.argtypes = [
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_wchar),
                ctypes.c_uint,
            ]
            self._winmm.mciGetErrorStringW.restype = ctypes.c_bool

        buffer = ctypes.create_unicode_buffer(self._BUFFER_CHARS)
        error_code = self._winmm.mciSendStringW(
            command,
            buffer,
            self._BUFFER_CHARS,
            None,
        )
        if error_code:
            error_buffer = ctypes.create_unicode_buffer(self._BUFFER_CHARS)
            self._winmm.mciGetErrorStringW(
                error_code,
                error_buffer,
                self._BUFFER_CHARS,
            )
            message = error_buffer.value or f"MCI error {error_code}"
            raise RuntimeError(f"{message}: {command}")
        return buffer.value
