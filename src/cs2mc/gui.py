from __future__ import annotations

import copy
import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .app_metadata import GITHUB_URL
from .config import ProfileStore
from .cs2_locator import detect_cs2_cfg_path, gsi_config_is_current, install_gsi_config, is_valid_cs2_cfg_path
from .external_links import open_external_url
from .models import (
    AppearanceSettings,
    GameSnapshot,
    KillStreakProfile,
    MediaSnapshot,
    Profile,
    resolve_asset_path,
)
from .runtime import RuntimeController
from .sound_player import SoundPlayer
from .theme import apply_application_palette, build_palette, build_stylesheet, dominant_seed_from_image
from .ui_components import ResizeHandle, TitleBar, apply_clickable_cursors
from .ui_pages import (
    AboutPage,
    AppearancePage,
    DashboardPage,
    KillStreakPage,
    OnboardingDialog,
    ProfilesPage,
    SetupPage,
    StatesPage,
)


class SignalBridge(QObject):
    snapshot = Signal(object)
    sound = Signal(str, int)
    log = Signal(str)
    sessions = Signal(object)
    media = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self, store: ProfileStore, bridge: SignalBridge) -> None:
        super().__init__()
        self.store = store
        self.bridge = bridge
        self.sound_player = SoundPlayer(self)
        self.runtime: RuntimeController | None = None
        self.current_profile = store.active_profile()
        self.current_kill_streak_profile = store.active_kill_streak_profile()
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
        self.title_bar.github_requested.connect(self._open_github)
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
        self.about = AboutPage()
        self.nav_buttons: dict[str, QPushButton] = {}
        self.page_indices: dict[str, int] = {}

        primary_pages = (
            ("overview", "Overview", self.dashboard),
            ("audio_states", "Audio states", self.states),
            ("kill_streaks", "Kill streaks", self.kill_streaks),
            ("profiles", "Profiles", self.profiles),
            ("appearance", "Appearance", self.appearance),
            ("setup", "Setup", self.setup),
        )
        for key, label, page in primary_pages:
            self._register_navigation_page(sidebar_layout, key, label, page)
        self.nav_buttons["overview"].setChecked(True)

        sidebar_layout.addStretch()
        self._register_navigation_page(sidebar_layout, "about", "About", self.about)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("Faint")
        sidebar_layout.addWidget(version)
        body_layout.addWidget(sidebar)
        body_layout.addWidget(self.stack, 1)

        self.resize_handles = self._create_resize_handles(root_widget)

        self.states.profile_changed.connect(self._save_profile)
        self.states.test_sound.connect(self.sound_player.play)
        self.kill_streaks.profile_selected.connect(self._select_kill_streak_profile)
        self.kill_streaks.profile_changed.connect(self._save_kill_streak_profile)
        self.kill_streaks.create_requested.connect(self._create_kill_streak_profile)
        self.kill_streaks.rename_requested.connect(self._rename_kill_streak_profile)
        self.kill_streaks.delete_requested.connect(self._delete_kill_streak_profile)
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
        self._load_kill_streak_profile(self.current_kill_streak_profile)
        self._refresh_profile_list()
        self._refresh_kill_streak_profile_list()
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

    def _register_navigation_page(
        self,
        layout: QVBoxLayout,
        key: str,
        label: str,
        page: QWidget,
    ) -> None:
        index = self.stack.addWidget(page)
        button = QPushButton(label)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.clicked.connect(lambda _=False, route=key: self._show_page(route))
        layout.addWidget(button)
        self.page_indices[key] = index
        self.nav_buttons[key] = button

    def _show_page(self, key: str) -> None:
        index = self.page_indices[key]
        if self.stack.currentIndex() == index:
            return
        self.stack.setCurrentIndex(index)
        for route, button in self.nav_buttons.items():
            button.setChecked(route == key)
        if self.store.settings.appearance.animations:
            self._fade_in(self.stack.currentWidget())
        if key == "profiles":
            self._refresh_profile_list()
        elif key == "kill_streaks":
            self._refresh_kill_streak_profile_list()
        elif key == "setup":
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

    def _load_kill_streak_profile(self, profile: KillStreakProfile) -> None:
        self.current_kill_streak_profile = copy.deepcopy(profile)
        self.kill_streaks.load_profile(profile)
        if self.runtime:
            self.runtime.update_kill_streak_profile(profile)

    def _save_kill_streak_profile(self, profile: KillStreakProfile) -> None:
        saved = self.store.save_kill_streak_profile(profile)
        self.current_kill_streak_profile = copy.deepcopy(saved)
        self.kill_streaks.load_profile(saved)
        if self.runtime:
            self.runtime.update_kill_streak_profile(saved)
        self._refresh_kill_streak_profile_list()

    def _refresh_profile_list(self) -> None:
        profiles = self.store.list_profiles()
        active_id = self.store.settings.active_profile_id
        self.profiles.set_profiles(profiles, active_id)
        self.title_bar.set_profiles(profiles, active_id)
        self._shortcut_profiles = profiles[:5]

    def _refresh_kill_streak_profile_list(self) -> None:
        profiles = self.store.list_kill_streak_profiles()
        active_id = self.store.settings.active_kill_streak_profile_id
        self.kill_streaks.set_profiles(profiles, active_id)

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

    def _select_kill_streak_profile(self, profile_id: str) -> None:
        if profile_id == self.current_kill_streak_profile.id:
            return
        profile = self.store.set_active_kill_streak_profile(profile_id)
        self._load_kill_streak_profile(profile)
        self._refresh_kill_streak_profile_list()

    def _create_kill_streak_profile(self, name: str, duplicate: bool) -> None:
        source = self.current_kill_streak_profile if duplicate else None
        profile = self.store.create_kill_streak_profile(name, source)
        self.store.set_active_kill_streak_profile(profile.id)
        self._load_kill_streak_profile(profile)
        self._refresh_kill_streak_profile_list()

    def _rename_kill_streak_profile(self, profile_id: str, name: str) -> None:
        try:
            profile = self.store.rename_kill_streak_profile(profile_id, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Rename failed", str(exc))
            return
        self._load_kill_streak_profile(profile)
        self._refresh_kill_streak_profile_list()

    def _delete_kill_streak_profile(self, profile_id: str) -> None:
        result = QMessageBox.question(
            self,
            "Delete sound profile",
            "Delete this kill-streak sound profile permanently?",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_kill_streak_profile(profile_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))
            return
        profile = self.store.active_kill_streak_profile()
        self._load_kill_streak_profile(profile)
        self._refresh_kill_streak_profile_list()

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
            apply_application_palette(app, self.palette)
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

    def _open_github(self) -> None:
        open_external_url(GITHUB_URL, self)

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
            self.title_bar.maximize_button.set_restore(self.isMaximized())
            self._position_resize_handles()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()


def run_gui(store: ProfileStore) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("CS2 Music Controller")
    app.setOrganizationName("CS2 Music Controller")
    app.setStyle("Fusion")
    families = set(QFontDatabase.families())
    family = next(
        (name for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI") if name in families),
        app.font().family(),
    )
    font = QFont(family)
    font.setPixelSize(13)
    font.setStyleHint(QFont.StyleHint.System)
    app.setFont(font)

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
