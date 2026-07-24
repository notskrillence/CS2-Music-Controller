from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect


class SoundPlayer(QObject):
    """Overlapping WAV/MP3 playback with a low-latency WAV fast path."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._effects: list[QSoundEffect] = []
        self._players: list[tuple[QMediaPlayer, QAudioOutput]] = []

    def play(self, path: str, volume_percent: int) -> None:
        source = Path(path)
        if not path or not source.is_file():
            return
        volume = max(0.0, min(1.0, volume_percent / 100.0))
        if source.suffix.casefold() == ".wav":
            self._play_wav(source, volume)
        else:
            self._play_media(source, volume)

    def _play_wav(self, source: Path, volume: float) -> None:
        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(str(source.resolve())))
        effect.setVolume(volume)
        self._effects.append(effect)
        effect.play()
        QTimer.singleShot(15000, lambda current=effect: self._release_effect(current))

    def _play_media(self, source: Path, volume: float) -> None:
        output = QAudioOutput(self)
        output.setVolume(volume)
        player = QMediaPlayer(self)
        player.setAudioOutput(output)
        player.setSource(QUrl.fromLocalFile(str(source.resolve())))
        entry = (player, output)
        self._players.append(entry)

        def status_changed(status: QMediaPlayer.MediaStatus) -> None:
            if status in {
                QMediaPlayer.MediaStatus.EndOfMedia,
                QMediaPlayer.MediaStatus.InvalidMedia,
            }:
                self._release_player(entry)

        player.mediaStatusChanged.connect(status_changed)
        player.errorOccurred.connect(lambda *_: self._release_player(entry))
        player.play()
        QTimer.singleShot(30000, lambda current=entry: self._release_player(current))

    def _release_effect(self, effect: QSoundEffect) -> None:
        if effect in self._effects:
            effect.stop()
            self._effects.remove(effect)
            effect.deleteLater()

    def _release_player(self, entry: tuple[QMediaPlayer, QAudioOutput]) -> None:
        if entry not in self._players:
            return
        player, output = entry
        self._players.remove(entry)
        player.stop()
        player.deleteLater()
        output.deleteLater()
