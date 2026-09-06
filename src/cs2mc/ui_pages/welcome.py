from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..app_metadata import CREATOR_NAME, DONATE_URL, GITHUB_URL, PROJECT_NAME
from ..external_links import open_external_url
from ..models import resolve_asset_path


class WelcomeDialog(QDialog):
    """One sleek first-run-of-version card: star/share ask + support links."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {PROJECT_NAME} {__version__}")
        self.setModal(True)
        self.setMinimumWidth(540)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(12)

        hero = QHBoxLayout()
        hero.setSpacing(16)
        icon_label = QLabel()
        icon_label.setObjectName("AboutIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = resolve_asset_path("assets/app.png")
        if icon_path.exists():
            icon_label.setPixmap(QIcon(str(icon_path)).pixmap(64, 64))
        icon_label.setFixedSize(74, 74)
        hero.addWidget(icon_label)

        copy = QVBoxLayout()
        copy.setSpacing(4)
        title = QLabel(f"What's new in {__version__}")
        title.setObjectName("SectionTitle")
        body = QLabel(
            "Near-zero idle CPU, automatic update checks, and this welcome card. "
            f"If {PROJECT_NAME} improves your matches, please star the repo and share it — "
            "it keeps the project alive."
        )
        body.setObjectName("Muted")
        body.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(body)
        hero.addLayout(copy, 1)
        root.addLayout(hero)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        star = QPushButton("★  Star on GitHub")
        star.setObjectName("Primary")
        star.setToolTip("Open the repository — a star helps others find it")
        star.clicked.connect(lambda: open_external_url(GITHUB_URL, self))
        donate = QPushButton("♥  Donate")
        donate.setObjectName("Tonal")
        donate.setToolTip("Support development via donatr.ee")
        donate.clicked.connect(lambda: open_external_url(DONATE_URL, self))
        buttons.addWidget(star)
        buttons.addWidget(donate)
        root.addLayout(buttons)

        credit = QLabel(f"Made by {CREATOR_NAME} · Free and open source")
        credit.setObjectName("Faint")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(credit)

        close = QPushButton("Start playing")
        close.clicked.connect(self.accept)
        root.addWidget(close)
