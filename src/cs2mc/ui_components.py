from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import Profile


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def apply_clickable_cursors(root: QWidget) -> None:
    cursor = Qt.CursorShape.PointingHandCursor
    clickable_types = (QAbstractButton, QComboBox, QCheckBox, QSlider)
    if isinstance(root, clickable_types):
        root.setCursor(cursor)
    for widget in root.findChildren(QWidget):
        if isinstance(widget, clickable_types) or bool(widget.property("clickable")):
            widget.setCursor(cursor)


class TitleBar(QFrame):
    profile_selected = Signal(str)

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._loading_profiles = False
        self._drag_offset = QPoint()
        self.setObjectName("TitleBar")
        self.setFixedHeight(50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 8, 7)
        layout.setSpacing(9)

        mark = QLabel("CS")
        mark.setObjectName("WindowMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("CS2 Music Controller")
        title.setObjectName("WindowTitle")
        layout.addWidget(mark)
        layout.addWidget(title)
        layout.addStretch()

        self.connection = QLabel("CS2 idle")
        self.connection.setObjectName("Faint")
        self.connection.setToolTip("Waiting for the next Game State Integration update")
        layout.addWidget(self.connection)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(160)
        self.profile_combo.setMaximumWidth(220)
        self.profile_combo.setToolTip("Switch profile")
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        layout.addWidget(self.profile_combo)

        self.minimize_button = self._window_button("—", "Minimize")
        self.maximize_button = self._window_button("□", "Maximize")
        self.close_button = self._window_button("×", "Close", close=True)
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)
        apply_clickable_cursors(self)

    @staticmethod
    def _window_button(text: str, tooltip: str, close: bool = False) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setObjectName("CloseButton" if close else "WindowButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def set_profiles(self, profiles: Iterable[Profile], active_id: str) -> None:
        self._loading_profiles = True
        self.profile_combo.clear()
        active_index = 0
        for index, profile in enumerate(profiles):
            self.profile_combo.addItem(profile.name, profile.id)
            if profile.id == active_id:
                active_index = index
        self.profile_combo.setCurrentIndex(active_index)
        self._loading_profiles = False

    def set_connection(self, connected: bool) -> None:
        self.connection.setText("CS2 connected" if connected else "CS2 idle")
        self.connection.setObjectName("Success" if connected else "Faint")
        repolish(self.connection)

    def _profile_changed(self) -> None:
        if self._loading_profiles:
            return
        profile_id = self.profile_combo.currentData()
        if profile_id:
            self.profile_selected.emit(str(profile_id))

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self.maximize_button.setText("□")
            self.maximize_button.setToolTip("Maximize")
        else:
            self._window.showMaximized()
            self.maximize_button.setText("❐")
            self.maximize_button.setToolTip("Restore")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                try:
                    if handle.startSystemMove():
                        event.accept()
                        return
                except RuntimeError:
                    pass
            self._drag_offset = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and not self._window.isMaximized():
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)


class ResizeHandle(QWidget):
    def __init__(self, window: QWidget, edges: Qt.Edge, cursor: Qt.CursorShape) -> None:
        super().__init__(window)
        self._window = window
        self._edges = edges
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and hasattr(handle, "startSystemResize"):
                try:
                    if handle.startSystemResize(self._edges):
                        event.accept()
                        return
                except RuntimeError:
                    pass
        super().mousePressEvent(event)


class ProfileCard(QFrame):
    activated = Signal(str)
    rename_requested = Signal(str)
    duplicate_requested = Signal(str)
    export_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, profile: Profile, active: bool) -> None:
        super().__init__()
        self.profile = profile
        self.setObjectName("ProfileCard")
        self.setProperty("active", active)
        self.setProperty("clickable", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(142)

        root = QVBoxLayout(self)
        root.setContentsMargins(17, 15, 15, 15)
        root.setSpacing(9)
        top = QHBoxLayout()
        title = QLabel(profile.name)
        title.setObjectName("SectionTitle")
        top.addWidget(title)
        top.addStretch()
        if active:
            badge = QLabel("Active")
            badge.setObjectName("ProfileBadge")
            top.addWidget(badge)
        menu_button = QToolButton()
        menu_button.setText("⋯")
        menu_button.setToolTip("Profile actions")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(menu_button)
        rename_action = QAction("Rename", menu)
        duplicate_action = QAction("Duplicate", menu)
        export_action = QAction("Export", menu)
        delete_action = QAction("Delete", menu)
        rename_action.triggered.connect(lambda: self.rename_requested.emit(profile.id))
        duplicate_action.triggered.connect(lambda: self.duplicate_requested.emit(profile.id))
        export_action.triggered.connect(lambda: self.export_requested.emit(profile.id))
        delete_action.triggered.connect(lambda: self.delete_requested.emit(profile.id))
        menu.addAction(rename_action)
        menu.addAction(duplicate_action)
        menu.addAction(export_action)
        if profile.id != "default":
            menu.addSeparator()
            menu.addAction(delete_action)
        menu_button.setMenu(menu)
        top.addWidget(menu_button)
        root.addLayout(top)

        target = profile.target_app or "Active media player"
        target = target[:-4] if target.casefold().endswith(".exe") else target
        summary = QLabel(
            f"Game {profile.volumes.get('game', 0)}%  ·  Buy {profile.volumes.get('buy_phase', 0)}%  ·  Fade {profile.fade_duration:.1f}s"
        )
        summary.setObjectName("Muted")
        target_label = QLabel(target)
        target_label.setObjectName("Faint")
        root.addWidget(summary)
        root.addWidget(target_label)
        root.addStretch()

        activate = QPushButton("Active" if active else "Use profile")
        activate.setObjectName("Tonal" if not active else "Primary")
        activate.setEnabled(not active)
        activate.clicked.connect(lambda: self.activated.emit(profile.id))
        root.addWidget(activate)
        apply_clickable_cursors(self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if not isinstance(child, (QAbstractButton, QComboBox)):
                self.activated.emit(self.profile.id)
                event.accept()
                return
        super().mouseReleaseEvent(event)
