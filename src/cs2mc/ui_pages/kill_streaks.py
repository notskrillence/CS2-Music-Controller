from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import BUILT_IN_KILL_STREAK_PROFILE_IDS
from ..models import KillStreakProfile
from ..ui_components import MaterialIconButton, MaterialSlider, apply_clickable_cursors
from .common import PageHeader, card_layout, set_path_label


class KillStreakPage(QWidget):
    profile_selected = Signal(str)
    profile_changed = Signal(object)
    create_requested = Signal(str, bool)
    rename_requested = Signal(str, str)
    duplicate_requested = Signal(str, str)
    delete_requested = Signal(str)
    test_sound = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self.profile: KillStreakProfile | None = None
        self._profiles: dict[str, KillStreakProfile] = {}
        self._loading_profiles = False
        self.rows: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(
            PageHeader(
                "Kill streaks",
                "Sound profiles are independent from music profiles. Switch packs without changing any CS2 volume settings.",
            )
        )

        selector_card = QFrame()
        selector_layout = card_layout(selector_card, (16, 14, 16, 14))
        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)
        selector_label = QLabel("Sound profile")
        selector_label.setObjectName("SectionTitle")
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(220)
        self.profile_combo.currentIndexChanged.connect(self._profile_selected)
        new_button = QPushButton("New profile")
        new_button.setObjectName("Primary")
        new_button.clicked.connect(lambda: self._request_name("New sound profile", False))
        self.profile_menu = MaterialIconButton("more", "Sound profile actions")
        self.profile_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._actions_menu = QMenu(self.profile_menu)
        self.rename_action = QAction("Rename", self._actions_menu)
        self.duplicate_action = QAction("Duplicate", self._actions_menu)
        self.delete_action = QAction("Delete", self._actions_menu)
        self.rename_action.triggered.connect(self._rename)
        self.duplicate_action.triggered.connect(self._duplicate)
        self.delete_action.triggered.connect(self._delete)
        self._actions_menu.addAction(self.rename_action)
        self._actions_menu.addAction(self.duplicate_action)
        self._actions_menu.addSeparator()
        self._actions_menu.addAction(self.delete_action)
        self.profile_menu.setMenu(self._actions_menu)
        selector_row.addWidget(selector_label)
        selector_row.addStretch()
        selector_row.addWidget(self.profile_combo)
        selector_row.addWidget(new_button)
        selector_row.addWidget(self.profile_menu)
        selector_layout.addLayout(selector_row)
        root.addWidget(selector_card)

        controls = QFrame()
        controls_layout = card_layout(controls)
        row = QHBoxLayout()
        self.enabled = QCheckBox("Enable kill-streak sounds")
        self.enabled.toggled.connect(self._changed)
        row.addWidget(self.enabled)
        row.addStretch()
        row.addWidget(QLabel("Sound volume"))
        self.volume = MaterialSlider()
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(190)
        self.volume.sliderReleased.connect(self._changed)
        self.volume_value = QLabel("90%")
        self.volume_value.setObjectName("Muted")
        self.volume.valueChanged.connect(
            lambda value: self.volume_value.setText(f"{value}%")
        )
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
            badge.setObjectName("CircleBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(36, 36)
            title = QLabel("First kill" if streak == 1 else f"{streak}-kill streak")
            title.setObjectName("SectionTitle")
            path_label = QLabel("No sound selected")
            path_label.setObjectName("PathLabel")
            choose = QPushButton("Choose audio")
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
        apply_clickable_cursors(self)

    def set_profiles(self, profiles: list[KillStreakProfile], active_id: str) -> None:
        self._profiles = {profile.id: copy.deepcopy(profile) for profile in profiles}
        self._loading_profiles = True
        self.profile_combo.clear()
        active_index = 0
        for index, profile in enumerate(profiles):
            self.profile_combo.addItem(profile.name, profile.id)
            if profile.id == active_id:
                active_index = index
        self.profile_combo.setCurrentIndex(active_index)
        self._loading_profiles = False
        self._update_profile_actions(active_id)

    def load_profile(self, profile: KillStreakProfile) -> None:
        self.profile = copy.deepcopy(profile)
        self.enabled.blockSignals(True)
        self.enabled.setChecked(profile.enabled)
        self.enabled.blockSignals(False)
        self.volume.setValue(profile.volume)
        for key, label in self.rows.items():
            set_path_label(label, profile.sounds.get(key, ""), "No sound selected")
        self._update_profile_actions(profile.id)

    def _profile_selected(self) -> None:
        if self._loading_profiles:
            return
        profile_id = self.profile_combo.currentData()
        if profile_id:
            self.profile_selected.emit(str(profile_id))

    def _update_profile_actions(self, profile_id: str) -> None:
        built_in = profile_id in BUILT_IN_KILL_STREAK_PROFILE_IDS
        self.rename_action.setEnabled(not built_in)
        self.delete_action.setEnabled(not built_in)

    def _changed(self) -> None:
        if not self.profile:
            return
        self.profile.enabled = self.enabled.isChecked()
        self.profile.volume = self.volume.value()
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _choose(self, key: str) -> None:
        if not self.profile:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose kill-streak audio",
            "",
            "Audio files (*.wav *.mp3);;All files (*)",
        )
        if not path:
            return
        self.profile.sounds[key] = path
        set_path_label(self.rows[key], path, "No sound selected")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _clear(self, key: str) -> None:
        if not self.profile:
            return
        self.profile.sounds[key] = ""
        set_path_label(self.rows[key], "", "No sound selected")
        self.profile_changed.emit(copy.deepcopy(self.profile))

    def _test(self, key: str) -> None:
        if not self.profile:
            return
        path = self.profile.sounds.get(key, "")
        if path and Path(path).is_file():
            self.test_sound.emit(path, self.volume.value())

    def _rename(self) -> None:
        if not self.profile or self.profile.id in BUILT_IN_KILL_STREAK_PROFILE_IDS:
            return
        name = self._name_dialog("Rename sound profile", self.profile.name)
        if name and name != self.profile.name:
            self.rename_requested.emit(self.profile.id, name)

    def _duplicate(self) -> None:
        if not self.profile:
            return
        self._request_name("Duplicate sound profile", True)

    def _delete(self) -> None:
        if not self.profile or self.profile.id in BUILT_IN_KILL_STREAK_PROFILE_IDS:
            return
        self.delete_requested.emit(self.profile.id)

    def _request_name(self, title: str, duplicate: bool) -> None:
        default_name = f"{self.profile.name} Copy" if duplicate and self.profile else ""
        name = self._name_dialog(title, default_name)
        if name:
            self.create_requested.emit(name, duplicate)

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
        edit.setPlaceholderText("Sound profile name")
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("Primary")
        cancel.clicked.connect(dialog.reject)
        save.clicked.connect(dialog.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addWidget(label)
        layout.addWidget(edit)
        layout.addLayout(buttons)
        edit.returnPressed.connect(dialog.accept)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return edit.text().strip()
        return ""
