from __future__ import annotations

import copy
import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import PRESETS, ProfileStore
from .cs2_locator import (
    GSI_FILENAME,
    detect_cs2_cfg_path,
    gsi_config_is_current,
    install_gsi_config,
    is_valid_cs2_cfg_path,
)
from .models import (
    AppearanceSettings,
    GameSnapshot,
    MediaSnapshot,
    Profile,
    STATE_KEYS,
    STATE_LABELS,
    resolve_asset_path,
)
from .runtime import RuntimeController
from .sound_player import SoundPlayer
from .theme import ThemePalette, build_palette, build_stylesheet, dominant_seed_from_image
from .ui_components import (
    ProfileCard,
    ResizeHandle,
    TitleBar,
    apply_clickable_cursors,
    repolish,
)


class SignalBridge(QObject):
    snapshot = Signal(object)
    sound = Signal(str, int)
    log = Signal(str)
    sessions = Signal(object)
    media = Signal(object)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, actions: list[QWidget] | None = None) -> None:
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 15)
        root.setSpacing(12)
        copy_layout = QVBoxLayout()
        copy_layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        copy_layout.addWidget(title_label)
        copy_layout.addWidget(subtitle_label)
        root.addLayout(copy_layout, 1)
        for action in actions or []:
            root.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)


def card_layout(frame: QFrame, margins: tuple[int, int, int, int] = (18, 18, 18, 18)) -> QVBoxLayout:
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(12)
    return layout


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    return line


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.palette: ThemePalette | None = None
        self.last_snapshot: GameSnapshot | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(15)
        root.addWidget(PageHeader("Overview", "Live match context, active profile, and current Windows media session."))

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
        self.volume_bar = QProgressBar()
        self.volume_bar.setRange(0, 100)
        self.volume_bar.setValue(100)
        self.volume_bar.setTextVisible(False)
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
        self.round_value = self._metric(metrics, "—", "Round")
        root.addLayout(metrics)

        self.now_playing_card = QFrame()
        self.now_playing_card.setObjectName("AuraCard")
        media_layout = QHBoxLayout(self.now_playing_card)
        media_layout.setContentsMargins(16, 15, 18, 15)
        media_layout.setSpacing(15)
        self.album_art = QLabel("♫")
        self.album_art.setObjectName("AlbumPlaceholder")
        self.album_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art.setFixedSize(82, 82)
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
        self.round_value.setText("—" if snapshot.map_round is None else str(snapshot.map_round + 1))
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
        self.volume_bar.setStyleSheet(f"QProgressBar::chunk{{background:{color};border-radius:4px;}}")

    def set_disconnected(self) -> None:
        self.connection.setText("Waiting for CS2")
        self.connection.setObjectName("Faint")
        repolish(self.connection)

    def update_media(self, media: MediaSnapshot) -> None:
        if not media.title:
            self.track_title.setText("Nothing playing")
            self.track_artist.setText("Start music, then choose its app in Setup if needed.")
            self.track_app.setText("")
            self.album_art.setPixmap(QPixmap())
            self.album_art.setText("♫")
            self.album_art.setObjectName("AlbumPlaceholder")
            repolish(self.album_art)
            return
        self.track_title.setText(media.title)
        self.track_artist.setText(media.artist or "Unknown artist")
        app = media.app.split("!")[0].split("\\")[-1]
        self.track_app.setText(app)
        if media.artwork:
            pixmap = QPixmap()
            if pixmap.loadFromData(media.artwork):
                self.album_art.setText("")
                self.album_art.setObjectName("AlbumArt")
                repolish(self.album_art)
                self.album_art.setPixmap(
                    pixmap.scaled(
                        82,
                        82,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self.album_art.setPixmap(QPixmap())
        self.album_art.setText("♫")
        self.album_art.setObjectName("AlbumPlaceholder")
        repolish(self.album_art)


class StatesPage(QWidget):
    profile_changed = Signal(object)
    test_sound = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self.profile: Profile | None = None
        self.rows: dict[str, dict[str, object]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(PageHeader(
            "Audio states",
            "Set the music level for each match context and optionally play a WAV when that context begins.",
        ))

        controls = QFrame()
        controls_layout = card_layout(controls)
        toggle_row = QHBoxLayout()
        self.enable_sounds = QCheckBox("Play transition sounds")
        self.enable_sounds.toggled.connect(self._general_changed)
        toggle_row.addWidget(self.enable_sounds)
        toggle_row.addStretch()
        toggle_row.addWidget(QLabel("Sound volume"))
        self.sound_volume = QSlider(Qt.Orientation.Horizontal)
        self.sound_volume.setRange(0, 100)
        self.sound_volume.setFixedWidth(160)
        self.sound_volume.sliderReleased.connect(self._general_changed)
        self.sound_volume_value = QLabel("70%")
        self.sound_volume_value.setObjectName("Muted")
        self.sound_volume.valueChanged.connect(lambda value: self.sound_volume_value.setText(f"{value}%"))
        toggle_row.addWidget(self.sound_volume)
        toggle_row.addWidget(self.sound_volume_value)
        controls_layout.addLayout(toggle_row)
        controls_layout.addWidget(divider())

        fade_row = QHBoxLayout()
        fade_row.addWidget(QLabel("Fade duration"))
        self.fade_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_slider.setRange(0, 30)
        self.fade_slider.setValue(7)
        self.fade_slider.valueChanged.connect(lambda value: self.fade_value.setText(f"{value / 10:.1f}s"))
        self.fade_slider.sliderReleased.connect(self._general_changed)
        self.fade_value = QLabel("0.7s")
        self.fade_value.setObjectName("Muted")
        fade_row.addWidget(self.fade_slider, 1)
        fade_row.addWidget(self.fade_value)
        controls_layout.addLayout(fade_row)
        root.addWidget(controls)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("Page")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 8)
        content_layout.setSpacing(10)
        for key in STATE_KEYS:
            content_layout.addWidget(self._build_state_row(key))
        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _build_state_row(self, key: str) -> QFrame:
        frame = QFrame()
        layout = card_layout(frame, (16, 13, 16, 13))
        top = QHBoxLayout()
        name = QLabel(STATE_LABELS[key])
        name.setObjectName("SectionTitle")
        volume_value = QLabel("0%")
        volume_value.setObjectName("Muted")
        volume_value.setFixedWidth(42)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.valueChanged.connect(lambda value, label=volume_value: label.setText(f"{value}%"))
        slider.sliderReleased.connect(self._row_changed)
        top.addWidget(name)
        top.addSpacing(14)
        top.addWidget(slider, 1)
        top.addWidget(volume_value)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        path_label = QLabel("No transition sound")
        path_label.setObjectName("PathLabel")
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        choose = QPushButton("Choose WAV")
        clear = QPushButton("Clear")
        test = QPushButton("Test")
        choose.clicked.connect(lambda _=False, state=key: self._choose_sound(state))
        clear.clicked.connect(lambda _=False, state=key: self._clear_sound(state))
        test.clicked.connect(lambda _=False, state=key: self._test_sound(state))
        bottom.addWidget(path_label, 1)
        bottom.addWidget(choose)
        bottom.addWidget(clear)
        bottom.addWidget(test)
        layout.addLayout(bottom)
        self.rows[key] = {"slider": slider, "value": volume_value, "path": path_label}
        return frame

    def load_profile(self, profile: Profile) -> None:
        self.profile = copy.deepcopy(profile)
        self.enable_sounds.blockSignals(True)
        self.enable_sounds.setChecked(profile.event_sounds_enabled)
        self.enable_sounds.blockSignals(False)
        self.sound_volume.setValue(profile.event_sound_volume)
        self.fade_slider.setValue(round(profile.fade_duration * 10))
        for key, widgets in self.rows.items():
            slider = widgets["slider"]
            assert isinstance(slider, QSlider)
            slider.setValue(profile.volumes[key])
            path_label = widgets["path"]
            assert isinstance(path_label, QLabel)
            self._set_path_label(path_label, profile.event_sounds.get(key, ""), "No transition sound")

    def _build_profile_from_ui(self) -> Profile | None:
        if not self.profile:
            return None
        profile = copy.deepcopy(self.profile)
        profile.event_sounds_enabled = self.enable_sounds.isChecked()
        profile.event_sound_volume = self.sound_volume.value()
        profile.fade_duration = self.fade_slider.value() / 10.0
        for key, widgets in self.rows.items():
            slider = widgets["slider"]
            assert isinstance(slider, QSlider)
            profile.volumes[key] = slider.value()
        self.profile = profile
        return profile

    def _row_changed(self) -> None:
        profile = self._build_profile_from_ui()
        if profile:
            self.profile_changed.emit(profile)

    def _general_changed(self) -> None:
        self._row_changed()

    def _choose_sound(self, key: str) -> None:
        if not self.profile:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose a WAV sound", "", "WAV audio (*.wav)")
        if not path:
            return
        self.profile.event_sounds[key] = path
        label = self.rows[key]["path"]
        assert isinstance(label, QLabel)
        self._set_path_label(label, path, "No transition sound")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _clear_sound(self, key: str) -> None:
        if not self.profile:
            return
        self.profile.event_sounds[key] = ""
        label = self.rows[key]["path"]
        assert isinstance(label, QLabel)
        self._set_path_label(label, "", "No transition sound")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _test_sound(self, key: str) -> None:
        if not self.profile:
            return
        path = self.profile.event_sounds.get(key, "")
        if path:
            self.test_sound.emit(path, self.sound_volume.value())

    @staticmethod
    def _set_path_label(label: QLabel, path: str, empty_text: str) -> None:
        label.setText(Path(path).name if path else empty_text)
        label.setToolTip(path)


class KillStreakPage(QWidget):
    profile_changed = Signal(object)
    test_sound = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self.profile: Profile | None = None
        self.rows: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(
            "Kill streaks",
            "Assign one WAV to each consecutive kill count. The sequence resets with the CS2 round counter.",
        ))

        controls = QFrame()
        controls_layout = card_layout(controls)
        row = QHBoxLayout()
        self.enabled = QCheckBox("Enable kill-streak sounds")
        self.enabled.toggled.connect(self._changed)
        row.addWidget(self.enabled)
        row.addStretch()
        row.addWidget(QLabel("Sound volume"))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(180)
        self.volume.sliderReleased.connect(self._changed)
        self.volume_value = QLabel("90%")
        self.volume_value.setObjectName("Muted")
        self.volume.valueChanged.connect(lambda value: self.volume_value.setText(f"{value}%"))
        row.addWidget(self.volume)
        row.addWidget(self.volume_value)
        controls_layout.addLayout(row)
        root.addWidget(controls)

        for streak in range(1, 6):
            key = str(streak)
            frame = QFrame()
            layout = card_layout(frame, (16, 13, 16, 13))
            line = QHBoxLayout()
            badge = QLabel(str(streak))
            badge.setObjectName("ProfileBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(34, 34)
            title = QLabel("First kill" if streak == 1 else f"{streak}-kill streak")
            title.setObjectName("SectionTitle")
            path_label = QLabel("No sound selected")
            path_label.setObjectName("PathLabel")
            choose = QPushButton("Choose WAV")
            clear = QPushButton("Clear")
            test = QPushButton("Test")
            choose.clicked.connect(lambda _=False, item=key: self._choose(item))
            clear.clicked.connect(lambda _=False, item=key: self._clear(item))
            test.clicked.connect(lambda _=False, item=key: self._test(item))
            line.addWidget(badge)
            line.addWidget(title)
            line.addSpacing(8)
            line.addWidget(path_label, 1)
            line.addWidget(choose)
            line.addWidget(clear)
            line.addWidget(test)
            layout.addLayout(line)
            root.addWidget(frame)
            self.rows[key] = path_label
        root.addStretch()

    def load_profile(self, profile: Profile) -> None:
        self.profile = copy.deepcopy(profile)
        self.enabled.blockSignals(True)
        self.enabled.setChecked(profile.kill_streak_enabled)
        self.enabled.blockSignals(False)
        self.volume.setValue(profile.kill_streak_volume)
        for key, label in self.rows.items():
            StatesPage._set_path_label(label, profile.kill_streak_sounds.get(key, ""), "No sound selected")

    def _changed(self) -> None:
        if not self.profile:
            return
        self.profile.kill_streak_enabled = self.enabled.isChecked()
        self.profile.kill_streak_volume = self.volume.value()
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _choose(self, key: str) -> None:
        if not self.profile:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose a kill-streak WAV", "", "WAV audio (*.wav)")
        if not path:
            return
        self.profile.kill_streak_sounds[key] = path
        StatesPage._set_path_label(self.rows[key], path, "No sound selected")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _clear(self, key: str) -> None:
        if not self.profile:
            return
        self.profile.kill_streak_sounds[key] = ""
        StatesPage._set_path_label(self.rows[key], "", "No sound selected")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _test(self, key: str) -> None:
        if not self.profile:
            return
        path = self.profile.kill_streak_sounds.get(key, "")
        if path:
            self.test_sound.emit(path, self.volume.value())


class ProfilesPage(QWidget):
    profile_selected = Signal(str)
    create_requested = Signal(str, bool)
    rename_requested = Signal(str, str)
    duplicate_requested = Signal(str, str)
    delete_requested = Signal(str)
    export_requested = Signal(str)
    import_requested = Signal()
    preset_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._profiles: dict[str, Profile] = {}
        self._active_id = "default"

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        new_button = QPushButton("New profile")
        new_button.setObjectName("Primary")
        new_button.clicked.connect(lambda: self._request_name(False, None))
        import_button = QPushButton("Import")
        import_button.clicked.connect(self.import_requested.emit)
        root.addWidget(PageHeader(
            "Profiles",
            "Switch with one click. Every profile stores its own volumes, sounds, fade, and target media app.",
            [import_button, new_button],
        ))

        preset_card = QFrame()
        preset_layout = card_layout(preset_card, (16, 14, 16, 14))
        preset_line = QHBoxLayout()
        label = QLabel("Quick presets")
        label.setObjectName("SectionTitle")
        preset_line.addWidget(label)
        preset_line.addStretch()
        for name in PRESETS:
            button = QPushButton(name)
            button.setObjectName("Chip")
            button.setToolTip(PRESETS[name]["description"])
            button.clicked.connect(lambda _=False, preset=name: self.preset_requested.emit(preset))
            preset_line.addWidget(button)
        preset_layout.addLayout(preset_line)
        root.addWidget(preset_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName("Page")
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 2, 0, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        scroll.setWidget(self.content)
        root.addWidget(scroll, 1)

    def set_profiles(self, profiles: list[Profile], active_id: str) -> None:
        self._profiles = {profile.id: profile for profile in profiles}
        self._active_id = active_id
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for index, profile in enumerate(profiles):
            card = ProfileCard(profile, profile.id == active_id)
            card.activated.connect(self.profile_selected.emit)
            card.rename_requested.connect(self._rename)
            card.duplicate_requested.connect(self._duplicate)
            card.export_requested.connect(self.export_requested.emit)
            card.delete_requested.connect(self.delete_requested.emit)
            self.grid.addWidget(card, index // 2, index % 2)
        self.grid.setRowStretch((len(profiles) + 1) // 2, 1)
        apply_clickable_cursors(self.content)

    def _request_name(self, duplicate: bool, source_id: str | None) -> None:
        title = "Duplicate profile" if duplicate else "New profile"
        default_name = ""
        if source_id and source_id in self._profiles:
            default_name = f"{self._profiles[source_id].name} Copy"
        name = self._name_dialog(title, default_name)
        if not name:
            return
        if duplicate and source_id:
            self.duplicate_requested.emit(source_id, name)
        else:
            self.create_requested.emit(name, False)

    def _rename(self, profile_id: str) -> None:
        profile = self._profiles.get(profile_id)
        if not profile:
            return
        name = self._name_dialog("Rename profile", profile.name)
        if name and name != profile.name:
            self.rename_requested.emit(profile_id, name)

    def _duplicate(self, profile_id: str) -> None:
        self._request_name(True, profile_id)

    def _name_dialog(self, title: str, value: str) -> str:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setMinimumWidth(390)
        layout = QVBoxLayout(dialog)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        edit = QLineEdit(value)
        edit.selectAll()
        edit.setPlaceholderText("Profile name")
        line = QHBoxLayout()
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("Primary")
        cancel.clicked.connect(dialog.reject)
        save.clicked.connect(dialog.accept)
        line.addStretch()
        line.addWidget(cancel)
        line.addWidget(save)
        layout.addWidget(label)
        layout.addWidget(edit)
        layout.addLayout(line)
        edit.returnPressed.connect(dialog.accept)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return edit.text().strip()
        return ""


class AppearancePage(QWidget):
    settings_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._loading = False
        self._seed = "#d6a24a"
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._emit_settings)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(PageHeader(
            "Appearance",
            "A Material-inspired color-role system with near-AMOLED surfaces and optional album-aware accents.",
        ))

        mode_card = QFrame()
        mode_layout = card_layout(mode_card)
        mode_title = QLabel("Theme source")
        mode_title.setObjectName("SectionTitle")
        mode_layout.addWidget(mode_title)
        mode_line = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Album dynamic", "album")
        self.mode.addItem("CS2MC dark", "dark")
        self.mode.addItem("Custom seed", "custom")
        self.mode.currentIndexChanged.connect(self._schedule)
        self.color_button = QPushButton("Choose seed color")
        self.color_button.clicked.connect(self._choose_color)
        self.color_swatch = QLabel("")
        self.color_swatch.setFixedSize(34, 34)
        self.color_swatch.setObjectName("ProfileBadge")
        mode_line.addWidget(self.mode, 1)
        mode_line.addWidget(self.color_swatch)
        mode_line.addWidget(self.color_button)
        mode_layout.addLayout(mode_line)
        note = QLabel("Album dynamic samples artwork once when the track changes. Semantic bomb, warning, and error colors remain fixed.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        mode_layout.addWidget(note)
        root.addWidget(mode_card)

        tune_card = QFrame()
        tune_layout = card_layout(tune_card)
        tune_title = QLabel("Material tuning")
        tune_title.setObjectName("SectionTitle")
        tune_layout.addWidget(tune_title)
        self.contrast, self.contrast_value = self._slider_row(tune_layout, "Contrast", -20, 30, "%")
        self.darkness, self.darkness_value = self._slider_row(tune_layout, "Surface darkness", 88, 100, "%")
        self.radius, self.radius_value = self._slider_row(tune_layout, "Corner radius", 10, 24, "px")
        self.aura, self.aura_value = self._slider_row(tune_layout, "Album aura", 0, 40, "%")
        self.animations = QCheckBox("Use subtle transitions")
        self.animations.toggled.connect(self._schedule)
        tune_layout.addWidget(self.animations)
        root.addWidget(tune_card)

        preview = QFrame()
        preview.setObjectName("HeroCard")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(22, 20, 22, 20)
        preview_layout.setSpacing(8)
        kicker = QLabel("Live preview")
        kicker.setObjectName("Kicker")
        title = QLabel("Personal, quiet, focused")
        title.setObjectName("HeroState")
        copy_label = QLabel("The accent carries selection and emphasis while the surfaces stay neutral.")
        copy_label.setObjectName("Muted")
        buttons = QHBoxLayout()
        tonal = QPushButton("Tonal action")
        tonal.setObjectName("Tonal")
        primary = QPushButton("Primary action")
        primary.setObjectName("Primary")
        buttons.addWidget(tonal)
        buttons.addWidget(primary)
        buttons.addStretch()
        preview_layout.addWidget(kicker)
        preview_layout.addWidget(title)
        preview_layout.addWidget(copy_label)
        preview_layout.addLayout(buttons)
        root.addWidget(preview)
        root.addStretch()

    def _slider_row(self, parent: QVBoxLayout, name: str, minimum: int, maximum: int, suffix: str) -> tuple[QSlider, QLabel]:
        line = QHBoxLayout()
        label = QLabel(name)
        label.setMinimumWidth(130)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        value = QLabel("")
        value.setObjectName("Muted")
        value.setFixedWidth(48)
        slider.valueChanged.connect(lambda number, output=value, unit=suffix: output.setText(f"{number}{unit}"))
        slider.valueChanged.connect(self._schedule)
        line.addWidget(label)
        line.addWidget(slider, 1)
        line.addWidget(value)
        parent.addLayout(line)
        return slider, value

    def load_settings(self, settings: AppearanceSettings) -> None:
        clean = settings.normalized()
        self._loading = True
        index = self.mode.findData(clean.mode)
        self.mode.setCurrentIndex(max(0, index))
        self._seed = clean.seed_color
        self._update_swatch()
        self.contrast.setValue(clean.contrast)
        self.darkness.setValue(clean.surface_darkness)
        self.radius.setValue(clean.corner_radius)
        self.aura.setValue(clean.aura_strength)
        self.animations.setChecked(clean.animations)
        self._loading = False

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._seed), self, "Choose theme seed")
        if not chosen.isValid():
            return
        self._seed = chosen.name()
        self._update_swatch()
        if self.mode.currentData() != "custom":
            self.mode.setCurrentIndex(self.mode.findData("custom"))
        self._schedule()

    def _update_swatch(self) -> None:
        self.color_swatch.setStyleSheet(f"background:{self._seed};border-radius:10px;")
        self.color_button.setText(self._seed.upper())

    def _schedule(self, *_: object) -> None:
        if self._loading:
            return
        self._save_timer.start(120)

    def _emit_settings(self) -> None:
        settings = AppearanceSettings(
            mode=str(self.mode.currentData()),
            seed_color=self._seed,
            contrast=self.contrast.value(),
            surface_darkness=self.darkness.value(),
            corner_radius=self.radius.value(),
            aura_strength=self.aura.value(),
            animations=self.animations.isChecked(),
        ).normalized()
        self.settings_changed.emit(settings)


class SetupPage(QWidget):
    cfg_path_changed = Signal(str)
    refresh_sessions = Signal()
    target_changed = Signal(object)

    def __init__(self, store: ProfileStore) -> None:
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(PageHeader(
            "Setup",
            "Connect the application to CS2 and select the Windows media player it should control.",
        ))

        game_card = QFrame()
        game_layout = card_layout(game_card)
        game_title = QLabel("CS2 Game State Integration")
        game_title.setObjectName("SectionTitle")
        game_layout.addWidget(game_title)
        self.setup_status = QLabel("Checking installation…")
        self.setup_status.setObjectName("Muted")
        self.setup_status.setWordWrap(True)
        game_layout.addWidget(self.setup_status)
        path_line = QHBoxLayout()
        self.cfg_path = QLineEdit()
        self.cfg_path.setReadOnly(True)
        browse = QPushButton("Browse")
        install = QPushButton("Install / repair")
        install.setObjectName("Primary")
        browse.clicked.connect(self.browse_for_cfg)
        install.clicked.connect(self.install_gsi)
        path_line.addWidget(self.cfg_path, 1)
        path_line.addWidget(browse)
        path_line.addWidget(install)
        game_layout.addLayout(path_line)
        root.addWidget(game_card)

        audio_card = QFrame()
        audio_layout = card_layout(audio_card)
        audio_title = QLabel("Music application")
        audio_title.setObjectName("SectionTitle")
        audio_layout.addWidget(audio_title)
        description = QLabel("Follow the active Windows media player, or pin a process for consistent control while CS2 has focus.")
        description.setObjectName("Muted")
        description.setWordWrap(True)
        audio_layout.addWidget(description)
        audio_line = QHBoxLayout()
        self.target_combo = QComboBox()
        self.target_combo.addItem("Follow active media player", None)
        refresh = QPushButton("Refresh apps")
        refresh.clicked.connect(self.refresh_sessions.emit)
        self.target_combo.currentIndexChanged.connect(self._target_selected)
        audio_line.addWidget(self.target_combo, 1)
        audio_line.addWidget(refresh)
        audio_layout.addLayout(audio_line)
        root.addWidget(audio_card)

        local_card = QFrame()
        local_layout = card_layout(local_card)
        local_title = QLabel("Local-only connection")
        local_title.setObjectName("SectionTitle")
        local_layout.addWidget(local_title)
        local_copy = QLabel("CS2 sends state updates to 127.0.0.1. The listener is not exposed to the network and rejects payloads without this installation's token.")
        local_copy.setObjectName("Muted")
        local_copy.setWordWrap(True)
        local_layout.addWidget(local_copy)
        root.addWidget(local_card)
        root.addStretch()

    def refresh_setup_status(self) -> bool:
        settings = self.store.settings
        self.cfg_path.setText(settings.cs2_cfg_path)
        if not settings.cs2_cfg_path or not is_valid_cs2_cfg_path(settings.cs2_cfg_path):
            self.setup_status.setText("CS2 was not detected. Select the game's cfg folder to finish setup.")
            self.setup_status.setObjectName("Danger")
            repolish(self.setup_status)
            return False
        cfg_dir = Path(settings.cs2_cfg_path)
        current = gsi_config_is_current(cfg_dir, settings.port, settings.gsi_token)
        if current:
            self.setup_status.setText(f"Installed: {GSI_FILENAME}")
            self.setup_status.setObjectName("Success")
        else:
            self.setup_status.setText("CS2 was found, but the integration file needs installation or repair.")
            self.setup_status.setObjectName("Warning")
        repolish(self.setup_status)
        return current

    def browse_for_cfg(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select CS2 cfg directory")
        if not chosen:
            return
        if not is_valid_cs2_cfg_path(chosen):
            QMessageBox.warning(self, "Incorrect folder", "Select the folder ending in Counter-Strike Global Offensive\\game\\csgo\\cfg.")
            return
        self.store.set_cfg_path(chosen)
        self.cfg_path_changed.emit(chosen)
        self.install_gsi()

    def install_gsi(self) -> None:
        settings = self.store.settings
        path = settings.cs2_cfg_path
        if not path or not is_valid_cs2_cfg_path(path):
            self.browse_for_cfg()
            return
        try:
            target = install_gsi_config(Path(path), settings.port, settings.gsi_token)
        except OSError as exc:
            QMessageBox.critical(self, "Installation failed", str(exc))
            return
        self.refresh_setup_status()
        QMessageBox.information(self, "CS2 connected", f"Installed {target.name}. Restart CS2 if it is already running.")

    def set_audio_sessions(self, sessions: list[dict[str, object]], selected: str | None) -> None:
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("Follow active media player", None)
        selected_index = 0
        for index, session in enumerate(sessions, start=1):
            name = str(session.get("name", ""))
            display = name[:-4] if name.casefold().endswith(".exe") else name
            if bool(session.get("active")):
                display += "  • active"
            self.target_combo.addItem(display, name)
            if selected and name.casefold() == selected.casefold():
                selected_index = index
        self.target_combo.setCurrentIndex(selected_index)
        self.target_combo.blockSignals(False)

    def _target_selected(self) -> None:
        self.target_changed.emit(self.target_combo.currentData())


class OnboardingDialog(QDialog):
    def __init__(self, setup_page: SetupPage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup_page = setup_page
        self.setWindowTitle("Connect CS2")
        self.setModal(True)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        title = QLabel("Connect CS2 Music Controller")
        title.setObjectName("PageTitle")
        body = QLabel("The CS2 cfg directory was not detected. Select it once and the application will install its Game State Integration file.")
        body.setObjectName("PageSubtitle")
        body.setWordWrap(True)
        path = QLabel("Typical path: Steam\\steamapps\\common\\Counter-Strike Global Offensive\\game\\csgo\\cfg")
        path.setObjectName("PathLabel")
        choose = QPushButton("Select CS2 cfg folder")
        choose.setObjectName("Primary")
        choose.clicked.connect(self._choose)
        later = QPushButton("Continue without CS2")
        later.clicked.connect(self.reject)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(path)
        layout.addSpacing(8)
        layout.addWidget(choose)
        layout.addWidget(later)

    def _choose(self) -> None:
        self.setup_page.browse_for_cfg()
        if self.setup_page.refresh_setup_status():
            self.accept()


class MainWindow(QMainWindow):
    def __init__(self, store: ProfileStore, bridge: SignalBridge) -> None:
        super().__init__()
        self.store = store
        self.bridge = bridge
        self.sound_player = SoundPlayer(self)
        self.runtime: RuntimeController | None = None
        self.current_profile = store.active_profile()
        self.last_gsi_at = 0.0
        self.album_seed: str | None = None
        self.palette = build_palette(store.settings.appearance)
        self._artwork_seed_cache: OrderedDict[str, str | None] = OrderedDict()
        self._active_animations: list[QPropertyAnimation] = []

        self.setWindowTitle("CS2 Music Controller")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(980, 680)
        self.resize(1120, 760)
        icon = resolve_asset_path("assets/app.ico")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        root_widget = QFrame()
        root_widget.setObjectName("WindowSurface")
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(root_widget)

        self.title_bar = TitleBar(self)
        self.title_bar.profile_selected.connect(self._select_profile)
        root.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("Root")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root.addWidget(body, 1)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(192)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 14)
        sidebar_layout.setSpacing(5)
        brand = QLabel("CS2MC")
        brand.setObjectName("Brand")
        brand_caption = QLabel("Audio context controller")
        brand_caption.setObjectName("BrandCaption")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(brand_caption)
        sidebar_layout.addSpacing(17)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.states = StatesPage()
        self.kill_streaks = KillStreakPage()
        self.profiles = ProfilesPage()
        self.appearance = AppearancePage()
        self.setup = SetupPage(store)
        pages = [
            ("Overview", self.dashboard),
            ("Audio states", self.states),
            ("Kill streaks", self.kill_streaks),
            ("Profiles", self.profiles),
            ("Appearance", self.appearance),
            ("Setup", self.setup),
        ]
        self.nav_buttons: list[QPushButton] = []
        for index, (label, page) in enumerate(pages):
            self.stack.addWidget(page)
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, i=index: self._show_page(i))
            sidebar_layout.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons[0].setChecked(True)
        sidebar_layout.addStretch()
        version = QLabel(f"Version {__version__}")
        version.setObjectName("Faint")
        sidebar_layout.addWidget(version)
        body_layout.addWidget(sidebar)
        body_layout.addWidget(self.stack, 1)

        self.resize_handles = self._create_resize_handles(root_widget)

        self.states.profile_changed.connect(self._save_profile)
        self.states.test_sound.connect(self.sound_player.play)
        self.kill_streaks.profile_changed.connect(self._save_profile)
        self.kill_streaks.test_sound.connect(self.sound_player.play)
        self.profiles.profile_selected.connect(self._select_profile)
        self.profiles.create_requested.connect(self._create_profile)
        self.profiles.rename_requested.connect(self._rename_profile)
        self.profiles.duplicate_requested.connect(self._duplicate_profile)
        self.profiles.delete_requested.connect(self._delete_profile)
        self.profiles.export_requested.connect(self._export_profile)
        self.profiles.import_requested.connect(self._import_profile)
        self.profiles.preset_requested.connect(self._apply_preset)
        self.appearance.settings_changed.connect(self._appearance_changed)
        self.setup.refresh_sessions.connect(self._refresh_sessions)
        self.setup.target_changed.connect(self._set_target_app)

        self.bridge.snapshot.connect(self._snapshot_received)
        self.bridge.sound.connect(self.sound_player.play)
        self.bridge.log.connect(self._log_received)
        self.bridge.sessions.connect(self._sessions_received)
        self.bridge.media.connect(self._media_received)

        self._load_profile(self.current_profile)
        self._refresh_profile_list()
        self.appearance.load_settings(store.settings.appearance)
        self.setup.refresh_setup_status()
        self._apply_theme(store.settings.appearance)
        self._setup_profile_shortcuts()
        apply_clickable_cursors(root_widget)

        self.stale_timer = QTimer(self)
        self.stale_timer.timeout.connect(self._check_connection_stale)
        self.stale_timer.start(1000)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_resize_handles()

    def _create_resize_handles(self, parent: QWidget) -> dict[str, ResizeHandle]:
        edge = Qt.Edge
        cursor = Qt.CursorShape
        handles = {
            "left": ResizeHandle(self, edge.LeftEdge, cursor.SizeHorCursor),
            "right": ResizeHandle(self, edge.RightEdge, cursor.SizeHorCursor),
            "top": ResizeHandle(self, edge.TopEdge, cursor.SizeVerCursor),
            "bottom": ResizeHandle(self, edge.BottomEdge, cursor.SizeVerCursor),
            "top_left": ResizeHandle(self, edge.TopEdge | edge.LeftEdge, cursor.SizeFDiagCursor),
            "top_right": ResizeHandle(self, edge.TopEdge | edge.RightEdge, cursor.SizeBDiagCursor),
            "bottom_left": ResizeHandle(self, edge.BottomEdge | edge.LeftEdge, cursor.SizeBDiagCursor),
            "bottom_right": ResizeHandle(self, edge.BottomEdge | edge.RightEdge, cursor.SizeFDiagCursor),
        }
        for handle in handles.values():
            handle.setParent(parent)
            handle.raise_()
        return handles

    def _position_resize_handles(self) -> None:
        if not hasattr(self, "resize_handles"):
            return
        width, height = self.width(), self.height()
        edge_size, corner = 6, 12
        geometry = {
            "left": (0, corner, edge_size, max(0, height - corner * 2)),
            "right": (width - edge_size, corner, edge_size, max(0, height - corner * 2)),
            "top": (corner, 0, max(0, width - corner * 2), edge_size),
            "bottom": (corner, height - edge_size, max(0, width - corner * 2), edge_size),
            "top_left": (0, 0, corner, corner),
            "top_right": (width - corner, 0, corner, corner),
            "bottom_left": (0, height - corner, corner, corner),
            "bottom_right": (width - corner, height - corner, corner, corner),
        }
        visible = not self.isMaximized()
        for name, handle in self.resize_handles.items():
            handle.setGeometry(*geometry[name])
            handle.setVisible(visible)
            handle.raise_()

    def attach_runtime(self, runtime: RuntimeController) -> None:
        self.runtime = runtime
        self._refresh_sessions()

    def run_first_launch_setup(self) -> None:
        settings = self.store.settings
        configured = settings.cs2_cfg_path and is_valid_cs2_cfg_path(settings.cs2_cfg_path)
        if not configured:
            detected = detect_cs2_cfg_path()
            if detected:
                self.store.set_cfg_path(str(detected))
                settings = self.store.settings
                try:
                    install_gsi_config(detected, settings.port, settings.gsi_token)
                except OSError as exc:
                    self.bridge.log.emit(f"Could not install the detected GSI configuration: {exc}")
            else:
                OnboardingDialog(self.setup, self).exec()
        else:
            cfg_dir = Path(settings.cs2_cfg_path)
            if not gsi_config_is_current(cfg_dir, settings.port, settings.gsi_token):
                try:
                    install_gsi_config(cfg_dir, settings.port, settings.gsi_token)
                except OSError as exc:
                    self.bridge.log.emit(f"Could not repair the GSI configuration: {exc}")
        self.setup.refresh_setup_status()

    def _show_page(self, index: int) -> None:
        if self.stack.currentIndex() == index:
            return
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        if self.store.settings.appearance.animations:
            self._fade_in(self.stack.currentWidget())
        if index == 3:
            self._refresh_profile_list()
        elif index == 5:
            self.setup.refresh_setup_status()
            self._refresh_sessions()

    def _fade_in(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.72)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(150)
        animation.setStartValue(0.72)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._active_animations.append(animation)

        def cleanup() -> None:
            widget.setGraphicsEffect(None)
            if animation in self._active_animations:
                self._active_animations.remove(animation)

        animation.finished.connect(cleanup)
        animation.start()

    def _load_profile(self, profile: Profile) -> None:
        self.current_profile = copy.deepcopy(profile)
        self.states.load_profile(profile)
        self.kill_streaks.load_profile(profile)
        self.dashboard.set_profile_name(profile.name)
        if self.runtime:
            self.runtime.update_profile(profile)

    def _save_profile(self, profile: Profile) -> None:
        saved = self.store.save_profile(profile)
        self.current_profile = copy.deepcopy(saved)
        self.dashboard.set_profile_name(saved.name)
        if self.runtime:
            self.runtime.update_profile(saved)
        if self.stack.currentWidget() is self.profiles:
            self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        profiles = self.store.list_profiles()
        active_id = self.store.settings.active_profile_id
        self.profiles.set_profiles(profiles, active_id)
        self.title_bar.set_profiles(profiles, active_id)
        self._shortcut_profiles = profiles[:5]

    def _select_profile(self, profile_id: str) -> None:
        if profile_id == self.current_profile.id:
            return
        profile = self.store.set_active_profile(profile_id)
        self._load_profile(profile)
        self._refresh_profile_list()
        self._refresh_sessions()
        self.dashboard.runtime_status.setText(f"Switched to {profile.name}.")
        if self.store.settings.appearance.animations and self.stack.currentWidget() is self.dashboard:
            self._fade_in(self.dashboard.hero)

    def _create_profile(self, name: str, duplicate: bool) -> None:
        source = self.current_profile if duplicate else None
        profile = self.store.create_profile(name, source)
        self.store.set_active_profile(profile.id)
        self._load_profile(profile)
        self._refresh_profile_list()

    def _duplicate_profile(self, source_id: str, name: str) -> None:
        source = self.store.get_profile(source_id)
        profile = self.store.create_profile(name, source)
        self.store.set_active_profile(profile.id)
        self._load_profile(profile)
        self._refresh_profile_list()

    def _rename_profile(self, profile_id: str, name: str) -> None:
        profile = self.store.rename_profile(profile_id, name)
        if profile_id == self.current_profile.id:
            self._load_profile(profile)
        self._refresh_profile_list()

    def _delete_profile(self, profile_id: str) -> None:
        if profile_id == "default":
            return
        result = QMessageBox.question(self, "Delete profile", "Delete this profile permanently?")
        if result != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_profile(profile_id)
        profile = self.store.active_profile()
        self._load_profile(profile)
        self._refresh_profile_list()

    def _export_profile(self, profile_id: str) -> None:
        profile = self.store.get_profile(profile_id)
        destination, _ = QFileDialog.getSaveFileName(self, "Export profile", f"{profile.name}.json", "JSON profile (*.json)")
        if destination:
            self.store.export_profile(profile, Path(destination))

    def _import_profile(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Import profile", "", "JSON profile (*.json)")
        if not source:
            return
        try:
            profile = self.store.import_profile(Path(source))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.store.set_active_profile(profile.id)
        self._load_profile(profile)
        self._refresh_profile_list()

    def _apply_preset(self, name: str) -> None:
        profile = self.store.apply_preset(self.current_profile, name)
        self._load_profile(profile)
        self._refresh_profile_list()
        self.dashboard.runtime_status.setText(f"Applied {name} to {profile.name}.")

    def _set_target_app(self, target: object) -> None:
        self.current_profile.target_app = str(target) if target else None
        self._save_profile(self.current_profile)

    def _appearance_changed(self, settings: AppearanceSettings) -> None:
        saved = self.store.set_appearance(settings)
        self._apply_theme(saved)

    def _apply_theme(self, settings: AppearanceSettings) -> None:
        self.palette = build_palette(settings, self.album_seed)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(self.palette, settings, self._font_family()))
        self.dashboard.set_palette(self.palette)
        self.appearance.load_settings(settings)
        self._update_window_mask()
        apply_clickable_cursors(self.centralWidget())

    def _update_window_mask(self) -> None:
        # A solid frameless surface is faster and more reliable than a translucent
        # shadow window. Windows 11 still supplies snap/maximize behavior through
        # the custom maximize control and QSizeGrip remains available when normal.
        self._position_resize_handles()

    @staticmethod
    def _font_family() -> str:
        families = set(QFontDatabase.families())
        for candidate in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
            if candidate in families:
                return candidate
        return QApplication.font().family()

    def _refresh_sessions(self) -> None:
        if not self.runtime:
            return

        def worker() -> None:
            sessions = self.runtime.list_audio_sessions()
            self.bridge.sessions.emit(sessions)

        threading.Thread(target=worker, name="CS2MC-Session-Scan", daemon=True).start()

    def _sessions_received(self, sessions: list[dict[str, object]]) -> None:
        self.setup.set_audio_sessions(sessions, self.current_profile.target_app)

    def _snapshot_received(self, snapshot: GameSnapshot) -> None:
        import time

        self.last_gsi_at = time.monotonic() if snapshot.connected else self.last_gsi_at
        self.dashboard.update_snapshot(snapshot)
        self.title_bar.set_connection(snapshot.connected)

    def _media_received(self, media: MediaSnapshot) -> None:
        self.dashboard.update_media(media)
        settings = self.store.settings.appearance
        if settings.mode != "album":
            return
        seed: str | None = None
        if media.artwork:
            digest = hashlib.sha256(media.artwork).hexdigest()
            if digest in self._artwork_seed_cache:
                seed = self._artwork_seed_cache[digest]
                self._artwork_seed_cache.move_to_end(digest)
            else:
                seed = dominant_seed_from_image(media.artwork)
                self._artwork_seed_cache[digest] = seed
                while len(self._artwork_seed_cache) > 32:
                    self._artwork_seed_cache.popitem(last=False)
        if seed != self.album_seed:
            self.album_seed = seed
            self._apply_theme(settings)

    def _check_connection_stale(self) -> None:
        import time

        if self.last_gsi_at and time.monotonic() - self.last_gsi_at > 20.0:
            self.dashboard.set_disconnected()
            self.title_bar.set_connection(False)

    def _log_received(self, message: str) -> None:
        self.dashboard.runtime_status.setText(message)

    def _setup_profile_shortcuts(self) -> None:
        self._shortcut_profiles: list[Profile] = []
        self._shortcuts: list[QShortcut] = []
        for index in range(1, 6):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index}"), self)
            shortcut.activated.connect(lambda item=index - 1: self._activate_shortcut_profile(item))
            self._shortcuts.append(shortcut)

    def _activate_shortcut_profile(self, index: int) -> None:
        if 0 <= index < len(self._shortcut_profiles):
            self._select_profile(self._shortcut_profiles[index].id)

    def changeEvent(self, event) -> None:  # type: ignore[override]
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.title_bar.maximize_button.setText("❐" if self.isMaximized() else "□")
            self._position_resize_handles()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()


def run_gui(store: ProfileStore) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("CS2 Music Controller")
    app.setOrganizationName("CS2 Music Controller")
    families = set(QFontDatabase.families())
    family = next((name for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI") if name in families), app.font().family())
    app.setFont(QFont(family, 10))

    bridge = SignalBridge()
    window = MainWindow(store, bridge)
    runtime = RuntimeController(
        store=store,
        on_snapshot=bridge.snapshot.emit,
        on_sound=bridge.sound.emit,
        on_log=bridge.log.emit,
        on_media=bridge.media.emit,
    )
    window.attach_runtime(runtime)
    runtime.start()
    app.aboutToQuit.connect(runtime.stop)
    window.show()
    QTimer.singleShot(150, window.run_first_launch_setup)
    return app.exec()
