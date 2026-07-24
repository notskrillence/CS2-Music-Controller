from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import ProfileStore
from ..cs2_locator import GSI_FILENAME, gsi_config_is_current, install_gsi_config, is_valid_cs2_cfg_path
from ..ui_components import repolish
from .common import PageHeader, card_layout


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
        self.setup_status = QLabel("Checking installation...")
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
        description = QLabel(
            "Follow the active Windows media player, or pin a process for consistent control while CS2 has focus."
        )
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
        local_copy = QLabel(
            "CS2 sends state updates to 127.0.0.1. The listener is not exposed to the network and rejects payloads without this installation's token."
        )
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
            QMessageBox.warning(
                self,
                "Incorrect folder",
                "Select the folder ending in Counter-Strike Global Offensive\\game\\csgo\\cfg.",
            )
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
        QMessageBox.information(
            self,
            "CS2 connected",
            f"Installed {target.name}. Restart CS2 if it is already running.",
        )

    def set_audio_sessions(self, sessions: list[dict[str, object]], selected: str | None) -> None:
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("Follow active media player", None)
        selected_index = 0
        for index, session in enumerate(sessions, start=1):
            name = str(session.get("name", ""))
            display = name[:-4] if name.casefold().endswith(".exe") else name
            if bool(session.get("active")):
                display += "  | active"
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
        body = QLabel(
            "The CS2 cfg directory was not detected. Select it once and the application will install its Game State Integration file."
        )
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
