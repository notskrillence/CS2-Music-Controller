from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtMultimedia import QSoundEffect


class SoundPlayer(QObject):
    """Small QSoundEffect pool for low-latency WAV playback."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._effects: list[QSoundEffect] = []

    def play(self, path: str, volume_percent: int) -> None:
        if not path or not Path(path).is_file():
            return
        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        effect.setVolume(max(0.0, min(1.0, volume_percent / 100.0)))
        self._effects.append(effect)
        effect.play()
        QTimer.singleShot(15000, lambda current=effect: self._release(current))

    def _release(self, effect: QSoundEffect) -> None:
        if effect in self._effects:
            effect.stop()
            self._effects.remove(effect)
            effect.deleteLater()
