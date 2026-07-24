from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
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
    QStyle,
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


def _with_alpha(color: QColor, alpha: int) -> QColor:
    copy = QColor(color)
    copy.setAlpha(max(0, min(255, alpha)))
    return copy


class WindowControlButton(QToolButton):
    """Font-independent title-bar control with Material-style state layers."""

    def __init__(self, kind: str, tooltip: str) -> None:
        super().__init__()
        self.kind = kind
        self._restore = False
        self.setObjectName("WindowControlButton")
        self.setProperty("closeControl", kind == "close")
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFixedSize(46, 38)

    def sizeHint(self) -> QSize:
        return QSize(46, 38)

    def set_restore(self, restore: bool) -> None:
        if self._restore == restore:
            return
        self._restore = restore
        self.setToolTip("Restore" if restore else "Maximize")
        self.setAccessibleName(self.toolTip())
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        hovered = self.underMouse()
        pressed = self.isDown()
        is_close = self.kind == "close"

        if hovered or pressed:
            if is_close:
                background = QColor("#c42b3a")
            else:
                background = palette.color(QPalette.ColorRole.Midlight)
                background.setAlpha(170 if hovered else 220)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(QRectF(3, 3, self.width() - 6, self.height() - 6), 12, 12)

        icon_color = QColor("#ffffff") if is_close and hovered else palette.color(
            QPalette.ColorRole.WindowText if hovered else QPalette.ColorRole.PlaceholderText
        )
        pen = QPen(icon_color, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx = self.width() / 2.0
        cy = self.height() / 2.0

        if self.kind == "minimize":
            painter.drawLine(QPointF(cx - 6, cy + 3.5), QPointF(cx + 6, cy + 3.5))
        elif self.kind == "maximize":
            if self._restore:
                painter.drawRoundedRect(QRectF(cx - 4.5, cy - 6.0, 10.0, 9.5), 1.5, 1.5)
                painter.drawRoundedRect(QRectF(cx - 6.5, cy - 3.5, 10.0, 9.5), 1.5, 1.5)
            else:
                painter.drawRoundedRect(QRectF(cx - 5.5, cy - 5.0, 11.0, 10.0), 1.5, 1.5)
        elif self.kind == "close":
            painter.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
            painter.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx - 5, cy + 5))


class MaterialIconButton(QToolButton):
    """Reusable icon-only button that avoids symbol-font fallbacks."""

    def __init__(self, icon_kind: str, tooltip: str, size: int = 38) -> None:
        super().__init__()
        self.icon_kind = icon_kind
        self.setObjectName("MaterialIconButton")
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        if self.underMouse() or self.isDown():
            layer = palette.color(QPalette.ColorRole.Midlight)
            layer.setAlpha(160 if self.underMouse() else 220)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(layer)
            painter.drawRoundedRect(QRectF(2, 2, self.width() - 4, self.height() - 4), 11, 11)

        color = palette.color(
            QPalette.ColorRole.WindowText if self.underMouse() else QPalette.ColorRole.PlaceholderText
        )
        pen = QPen(color, 1.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx = self.width() / 2.0
        cy = self.height() / 2.0

        if self.icon_kind == "more":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            for offset in (-6.0, 0.0, 6.0):
                painter.drawEllipse(QPointF(cx + offset, cy), 1.65, 1.65)
        elif self.icon_kind == "github":
            # A simple repository/network mark rather than a trademarked font glyph.
            painter.drawRoundedRect(QRectF(cx - 7, cy - 6, 14, 12), 3, 3)
            painter.drawLine(QPointF(cx - 3.5, cy - 1.5), QPointF(cx + 3.5, cy - 1.5))
            painter.drawLine(QPointF(cx - 3.5, cy + 2.5), QPointF(cx + 1.5, cy + 2.5))
        elif self.icon_kind == "external":
            painter.drawRoundedRect(QRectF(cx - 6.5, cy - 4.5, 11, 11), 2, 2)
            painter.drawLine(QPointF(cx - 0.5, cy - 6), QPointF(cx + 6, cy - 6))
            painter.drawLine(QPointF(cx + 6, cy - 6), QPointF(cx + 6, cy + 0.5))
            painter.drawLine(QPointF(cx + 5.5, cy - 5.5), QPointF(cx - 0.5, cy + 0.5))


class SocialIdentityButton(QPushButton):
    """Reusable obround identity link with platform-specific theming."""

    def __init__(self, platform: str, handle: str, tooltip: str) -> None:
        super().__init__(f"{platform}  {handle}")
        self.setObjectName("SocialIdentityButton")
        self.setProperty("platform", platform.casefold())
        self.setToolTip(tooltip)
        self.setAccessibleName(f"{platform}: {handle}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setMinimumWidth(156)



class TitleBar(QFrame):
    profile_selected = Signal(str)
    github_requested = Signal()

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._loading_profiles = False
        self._system_move_active = False
        self._manual_dragging = False
        self._press_global = QPoint()
        self._press_window_pos = QPoint()
        self.setObjectName("TitleBar")
        self.setFixedHeight(56)

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
        self.profile_combo.setMinimumWidth(170)
        self.profile_combo.setMaximumWidth(240)
        self.profile_combo.setToolTip("Switch profile")
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        layout.addWidget(self.profile_combo)

        self.github_button = MaterialIconButton("github", "Open project on GitHub")
        self.github_button.clicked.connect(self.github_requested.emit)
        self.minimize_button = WindowControlButton("minimize", "Minimize")
        self.maximize_button = WindowControlButton("maximize", "Maximize")
        self.close_button = WindowControlButton("close", "Close")
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.github_button)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)
        apply_clickable_cursors(self)

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
        else:
            self._window.showMaximized()
        self.maximize_button.set_restore(self._window.isMaximized())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        self._system_move_active = False
        self._manual_dragging = False
        handle = self._window.windowHandle()
        if handle is not None and hasattr(handle, "startSystemMove"):
            try:
                self._system_move_active = bool(handle.startSystemMove())
            except RuntimeError:
                self._system_move_active = False
            if self._system_move_active:
                event.accept()
                return

        if not self._window.isMaximized():
            self._manual_dragging = True
            self._press_global = event.globalPosition().toPoint()
            self._press_window_pos = self._window.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._system_move_active:
            event.accept()
            return
        if self._manual_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_global
            self._window.move(self._press_window_pos + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._system_move_active = False
        self._manual_dragging = False
        super().mouseReleaseEvent(event)


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


class MaterialSlider(QSlider):
    """Smooth, unclipped horizontal slider with direct click-and-drag behavior."""

    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self._dragging = False
        self.setObjectName("MaterialSlider")
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        if self.orientation() != Qt.Orientation.Horizontal:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        left = 10.0
        right = self.width() - 10.0
        center_y = self.height() / 2.0
        usable = max(1.0, right - left)
        position = QStyle.sliderPositionFromValue(
            self.minimum(),
            self.maximum(),
            self.value(),
            round(usable),
            self.invertedAppearance(),
        )
        handle_x = left + position
        track = QRectF(left, center_y - 2.0, usable, 4.0)
        filled = QRectF(left, center_y - 2.0, max(0.0, handle_x - left), 4.0)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Mid))
        painter.drawRoundedRect(track, 2.0, 2.0)
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        if filled.width() > 0:
            painter.drawRoundedRect(filled, 2.0, 2.0)

        radius = 8.5 if self.hasFocus() or self.underMouse() or self._dragging else 7.5
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        painter.drawEllipse(QPointF(handle_x, center_y), radius, radius)
        painter.setBrush(palette.color(QPalette.ColorRole.HighlightedText))
        painter.drawEllipse(QPointF(handle_x, center_y), 2.2, 2.2)

    def _set_value_from_x(self, x: float) -> None:
        usable = max(1.0, self.width() - 20.0)
        ratio = max(0.0, min(1.0, (x - 10.0) / usable))
        if self.invertedAppearance():
            ratio = 1.0 - ratio
        value = self.minimum() + round(ratio * (self.maximum() - self.minimum()))
        self.setValue(value)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.orientation() == Qt.Orientation.Horizontal:
            self._dragging = True
            self.setSliderDown(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._set_value_from_x(event.position().x())
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._set_value_from_x(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._set_value_from_x(event.position().x())
            self._dragging = False
            self.setSliderDown(False)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MaterialProgressBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self.setObjectName("MaterialProgressBar")
        self.setFixedHeight(14)
        self.setMinimumWidth(80)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(minimum + 1, maximum)
        self.setValue(self._value)

    def setValue(self, value: int) -> None:
        clean = max(self._minimum, min(self._maximum, int(value)))
        if clean != self._value:
            self._value = clean
            self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        rect = QRectF(0, 3, self.width(), 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Mid))
        painter.drawRoundedRect(rect, 4, 4)
        ratio = (self._value - self._minimum) / (self._maximum - self._minimum)
        width = self.width() * ratio
        if width > 0:
            painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
            painter.drawRoundedRect(QRectF(0, 3, max(8.0, width), 8), 4, 4)


class ColorSwatch(QWidget):
    def __init__(self, color: str = "#d6a24a", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(34, 34)
        self.setObjectName("ColorSwatch")

    def set_color(self, color: str) -> None:
        candidate = QColor(color)
        if candidate.isValid():
            self._color = candidate
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(_with_alpha(self.palette().color(QPalette.ColorRole.WindowText), 55), 1))
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(2, 2, self.width() - 4, self.height() - 4))


class AlbumArtView(QWidget):
    """Rounded artwork surface with a font-free media placeholder."""

    def __init__(self, size: int = 82, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.setObjectName("AlbumArtView")
        self.setFixedSize(size, size)

    def set_artwork(self, artwork: bytes | None) -> bool:
        pixmap = QPixmap()
        loaded = bool(artwork) and pixmap.loadFromData(artwork or b"")
        self._pixmap = pixmap if loaded else QPixmap()
        self.update()
        return loaded

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        radius = 16.0

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        painter.fillPath(path, palette.color(QPalette.ColorRole.Base))

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            source_x = max(0, (scaled.width() - self.width()) // 2)
            source_y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(
                QRectF(0, 0, self.width(), self.height()),
                scaled,
                QRectF(source_x, source_y, self.width(), self.height()),
            )
        else:
            accent = palette.color(QPalette.ColorRole.Highlight)
            painter.setPen(QPen(accent, 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            center = QPointF(self.width() / 2, self.height() / 2)
            painter.drawEllipse(center, 19, 19)
            painter.drawEllipse(center, 5, 5)
            painter.drawArc(QRectF(center.x() - 12, center.y() - 12, 24, 24), 25 * 16, 120 * 16)

        painter.setClipping(False)
        painter.setPen(QPen(_with_alpha(palette.color(QPalette.ColorRole.Highlight), 100), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)


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

        menu_button = MaterialIconButton("more", "Profile actions")
        menu_button.setObjectName("ProfileMenuButton")
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
            f"Game {profile.volumes.get('game', 0)}%  |  Buy {profile.volumes.get('buy_phase', 0)}%  |  Fade {profile.fade_duration:.1f}s"
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
