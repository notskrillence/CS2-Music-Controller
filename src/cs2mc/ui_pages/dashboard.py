from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..models import GameSnapshot, MediaSnapshot
from ..theme import ThemePalette
from ..ui_components import AlbumArtView, MaterialProgressBar, repolish
from .common import PageHeader, card_layout


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.palette: ThemePalette | None = None
        self.last_snapshot: GameSnapshot | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(15)
        root.addWidget(PageHeader(
            "Overview",
            "Live match context, active profile, and current Windows media session.",
        ))

        self.hero = QFrame()
        self.hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(24, 20, 24, 21)
        hero_layout.setSpacing(8)
        top = QHBoxLayout()
        kicker = QLabel("Game context")
        kicker.setObjectName("Kicker")
        self.connection = QLabel("Waiting for CS2")
        self.connection.setObjectName("Faint")
        top.addWidget(kicker)
        top.addStretch()
        top.addWidget(self.connection)
        hero_layout.addLayout(top)

        self.state_label = QLabel("Menu")
        self.state_label.setObjectName("HeroState")
        hero_layout.addWidget(self.state_label)

        volume_line = QHBoxLayout()
        volume_line.setSpacing(14)
        self.volume_bar = MaterialProgressBar()
        self.volume_bar.setRange(0, 100)
        self.volume_bar.setValue(100)
        self.volume_value = QLabel("100%")
        self.volume_value.setObjectName("MetricValue")
        self.volume_value.setFixedWidth(68)
        self.volume_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        volume_line.addWidget(self.volume_bar, 1)
        volume_line.addWidget(self.volume_value)
        hero_layout.addLayout(volume_line)

        caption = QLabel("Music target")
        caption.setObjectName("Muted")
        hero_layout.addWidget(caption)
        root.addWidget(self.hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.profile_value = self._metric(metrics, "Balanced", "Active profile")
        self.kills_value = self._metric(metrics, "0", "Round kills")
        self.round_value = self._metric(metrics, "N/A", "Round")
        root.addLayout(metrics)

        self.now_playing_card = QFrame()
        self.now_playing_card.setObjectName("AuraCard")
        media_layout = QHBoxLayout(self.now_playing_card)
        media_layout.setContentsMargins(16, 15, 18, 15)
        media_layout.setSpacing(15)
        self.album_art = AlbumArtView(82)
        media_layout.addWidget(self.album_art)

        media_copy = QVBoxLayout()
        media_copy.setSpacing(4)
        eyebrow = QLabel("Now playing")
        eyebrow.setObjectName("Kicker")
        self.track_title = QLabel("Nothing playing")
        self.track_title.setObjectName("SectionTitle")
        self.track_title.setWordWrap(False)
        self.track_artist = QLabel("Start music, then choose its app in Setup if needed.")
        self.track_artist.setObjectName("Muted")
        self.track_artist.setWordWrap(True)
        self.track_app = QLabel("")
        self.track_app.setObjectName("Faint")
        media_copy.addWidget(eyebrow)
        media_copy.addWidget(self.track_title)
        media_copy.addWidget(self.track_artist)
        media_copy.addWidget(self.track_app)
        media_copy.addStretch()
        media_layout.addLayout(media_copy, 1)
        root.addWidget(self.now_playing_card)

        activity = QFrame()
        activity_layout = card_layout(activity, (17, 15, 17, 15))
        line = QHBoxLayout()
        title = QLabel("Runtime")
        title.setObjectName("SectionTitle")
        self.runtime_status = QLabel("Local listener is starting.")
        self.runtime_status.setObjectName("Muted")
        self.runtime_status.setWordWrap(True)
        line.addWidget(title)
        line.addSpacing(12)
        line.addWidget(self.runtime_status, 1)
        activity_layout.addLayout(line)
        root.addWidget(activity)
        root.addStretch()

    @staticmethod
    def _metric(parent: QHBoxLayout, value: str, label: str) -> QLabel:
        frame = QFrame()
        layout = card_layout(frame, (17, 14, 17, 14))
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        parent.addWidget(frame, 1)
        return value_label

    def set_palette(self, palette: ThemePalette) -> None:
        self.palette = palette
        if self.last_snapshot:
            self._apply_state_color(self.last_snapshot.state)

    def set_profile_name(self, name: str) -> None:
        self.profile_value.setText(name)

    def update_snapshot(self, snapshot: GameSnapshot) -> None:
        self.last_snapshot = snapshot
        self.state_label.setText(snapshot.state_label)
        self.volume_bar.setValue(snapshot.music_volume)
        self.volume_value.setText(f"{snapshot.music_volume}%")
        self.kills_value.setText(str(snapshot.round_kills))
        self.round_value.setText("N/A" if snapshot.map_round is None else str(snapshot.map_round + 1))
        self.connection.setText("CS2 connected" if snapshot.connected else "Profile applied")
        self.connection.setObjectName("Success" if snapshot.connected else "Muted")
        repolish(self.connection)
        self._apply_state_color(snapshot.state)

    def _apply_state_color(self, state: str) -> None:
        if not self.palette:
            return
        palette = self.palette
        if state == "bomb_planted":
            color = palette.danger
        elif state == "round_over":
            color = palette.warning
        elif state == "spectating":
            color = palette.text_muted
        else:
            color = palette.primary
        self.state_label.setStyleSheet(f"color:{color};")
        # The custom progress widget reads Highlight from its own palette.
        progress_palette = self.volume_bar.palette()
        progress_palette.setColor(QPalette.ColorRole.Highlight, QColor(color))
        self.volume_bar.setPalette(progress_palette)
        self.volume_bar.update()

    def set_disconnected(self) -> None:
        self.connection.setText("Waiting for CS2")
        self.connection.setObjectName("Faint")
        repolish(self.connection)

    def update_media(self, media: MediaSnapshot) -> None:
        if not media.title:
            self.track_title.setText("Nothing playing")
            self.track_artist.setText("Start music, then choose its app in Setup if needed.")
            self.track_app.setText("")
            self.album_art.set_artwork(None)
            return
        self.track_title.setText(media.title)
        self.track_artist.setText(media.artist or "Unknown artist")
        app = media.app.split("!")[0].split("\\")[-1]
        self.track_app.setText(app)
        self.album_art.set_artwork(media.artwork)
