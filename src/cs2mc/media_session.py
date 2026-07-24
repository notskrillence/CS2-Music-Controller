from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Callable

from .models import MediaSnapshot

MediaHandler = Callable[[MediaSnapshot], None]
LogHandler = Callable[[str], None]


class MediaSessionMonitor:
    """Low-frequency Windows media metadata monitor.

    It wakes only while the application is running and emits when track identity
    changes. Album bytes are read once per track and are capped to avoid large
    allocations from misbehaving media providers.
    """

    def __init__(
        self,
        on_media: MediaHandler,
        on_log: LogHandler | None = None,
        interval_seconds: float = 1.5,
    ) -> None:
        self.on_media = on_media
        self.on_log = on_log or (lambda _: None)
        self.interval_seconds = max(0.75, float(interval_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_identity: tuple[str, str, str] | None = None

    def start(self) -> None:
        if os.name != "nt" or (self._thread and self._thread.is_alive()):
            return
        self._thread = threading.Thread(target=self._run, name="CS2MC-Media", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        try:
            asyncio.run(self._watch())
        except Exception as exc:
            self.on_log(f"Media metadata monitor stopped: {exc}")

    async def _watch(self) -> None:
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )
        except ImportError:
            return

        try:
            manager = await MediaManager.request_async()
        except Exception as exc:
            self.on_log(f"Windows media metadata is unavailable: {exc}")
            return

        while not self._stop.is_set():
            try:
                session = manager.get_current_session()
                if session is None:
                    if self._last_identity not in (None, ("", "", "")):
                        self._last_identity = ("", "", "")
                        self.on_media(MediaSnapshot())
                else:
                    properties = await session.try_get_media_properties_async()
                    app = session.source_app_user_model_id.split("!")[0]
                    identity = (
                        str(properties.title or ""),
                        str(properties.artist or ""),
                        str(app or ""),
                    )
                    if identity != self._last_identity:
                        artwork = await self._read_thumbnail(getattr(properties, "thumbnail", None))
                        self._last_identity = identity
                        self.on_media(
                            MediaSnapshot(
                                title=identity[0],
                                artist=identity[1],
                                app=identity[2],
                                artwork=artwork,
                            )
                        )
            except Exception:
                # Media providers can disappear between the session and property calls.
                # This is expected during track/player changes, so retry quietly.
                pass
            await asyncio.sleep(self.interval_seconds)

    @staticmethod
    async def _read_thumbnail(reference: object | None) -> bytes | None:
        if reference is None:
            return None
        try:
            from winrt.windows.storage.streams import DataReader

            stream = await reference.open_read_async()
            size = min(int(getattr(stream, "size", 0)), 5 * 1024 * 1024)
            if size <= 0:
                return None
            reader = DataReader(stream)
            await reader.load_async(size)
            buffer = reader.read_buffer(size)
            try:
                return bytes(buffer)
            except TypeError:
                try:
                    return memoryview(buffer).tobytes()
                except TypeError:
                    return None
        except Exception:
            return None
