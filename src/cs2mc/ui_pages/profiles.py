from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..config import PRESETS
from ..models import Profile
from ..ui_components import ProfileCard, apply_clickable_cursors
from .common import PageHeader, card_layout


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
            "Switch with one click. Every profile stores music levels, state sounds, fade, and its target media app.",
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
        self.grid.setContentsMargins(0, 6, 4, 16)
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
