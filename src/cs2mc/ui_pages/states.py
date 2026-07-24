from __future__ import annotations

import copy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import Profile, STATE_KEYS, STATE_LABELS
from ..ui_components import MaterialSlider
from .common import PageHeader, card_layout, divider, set_path_label


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
        self.sound_volume = MaterialSlider()
        self.sound_volume.setRange(0, 100)
        self.sound_volume.setFixedWidth(180)
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
        self.fade_slider = MaterialSlider()
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
        content_layout.setContentsMargins(0, 6, 4, 12)
        content_layout.setSpacing(10)
        for key in STATE_KEYS:
            content_layout.addWidget(self._build_state_row(key))
        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _build_state_row(self, key: str) -> QFrame:
        frame = QFrame()
        layout = card_layout(frame, (16, 14, 16, 14))
        top = QHBoxLayout()
        name = QLabel(STATE_LABELS[key])
        name.setObjectName("SectionTitle")
        volume_value = QLabel("0%")
        volume_value.setObjectName("Muted")
        volume_value.setFixedWidth(42)
        slider = MaterialSlider()
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
            assert isinstance(slider, MaterialSlider)
            slider.setValue(profile.volumes[key])
            path_label = widgets["path"]
            assert isinstance(path_label, QLabel)
            set_path_label(path_label, profile.event_sounds.get(key, ""), "No transition sound")

    def _build_profile_from_ui(self) -> Profile | None:
        if not self.profile:
            return None
        profile = copy.deepcopy(self.profile)
        profile.event_sounds_enabled = self.enable_sounds.isChecked()
        profile.event_sound_volume = self.sound_volume.value()
        profile.fade_duration = self.fade_slider.value() / 10.0
        for key, widgets in self.rows.items():
            slider = widgets["slider"]
            assert isinstance(slider, MaterialSlider)
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
        set_path_label(label, path, "No transition sound")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _clear_sound(self, key: str) -> None:
        if not self.profile:
            return
        self.profile.event_sounds[key] = ""
        label = self.rows[key]["path"]
        assert isinstance(label, QLabel)
        set_path_label(label, "", "No transition sound")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _test_sound(self, key: str) -> None:
        if not self.profile:
            return
        path = self.profile.event_sounds.get(key, "")
        if path:
            self.test_sound.emit(path, self.sound_volume.value())
