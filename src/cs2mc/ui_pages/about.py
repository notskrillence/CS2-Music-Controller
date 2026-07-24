from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..app_metadata import (
    CREATOR_NAME,
    DISCORD_USERNAME,
    GITHUB_URL,
    GITHUB_USERNAME,
    LICENSE_NAME,
    PROJECT_DESCRIPTION,
    PROJECT_NAME,
)
from ..external_links import open_external_url
from ..models import resolve_asset_path
from ..ui_components import SocialIdentityButton
from .common import PageHeader, card_layout


class AboutPage(QWidget):
    """Project identity, credits, and trusted external destinations."""

    def __init__(self) -> None:
        super().__init__()
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self._clear_feedback)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(PageHeader(
            "About",
            "Project information, credits, source code, and release details.",
        ))

        root.addWidget(self._build_project_hero())
        root.addWidget(self._build_identity_card())
        root.addWidget(self._build_source_card())
        root.addStretch()

    def _build_project_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("HeroCard")
        layout = QHBoxLayout(hero)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(18)

        icon_label = QLabel()
        icon_label.setObjectName("AboutIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = resolve_asset_path("assets/app.png")
        if icon_path.exists():
            icon_label.setPixmap(QIcon(str(icon_path)).pixmap(72, 72))
        icon_label.setFixedSize(82, 82)
        layout.addWidget(icon_label)

        copy_layout = QVBoxLayout()
        title = QLabel(PROJECT_NAME)
        title.setObjectName("HeroState")
        description = QLabel(PROJECT_DESCRIPTION)
        description.setObjectName("Muted")
        description.setWordWrap(True)
        release = QLabel(f"Version {__version__}")
        release.setObjectName("Faint")
        copy_layout.addWidget(title)
        copy_layout.addWidget(description)
        copy_layout.addWidget(release)
        layout.addLayout(copy_layout, 1)
        return hero

    def _build_identity_card(self) -> QFrame:
        card = QFrame()
        layout = card_layout(card)

        title = QLabel("Created by")
        title.setObjectName("Kicker")
        creator = QLabel(CREATOR_NAME)
        creator.setObjectName("CreditName")

        identity_row = QHBoxLayout()
        identity_row.setSpacing(10)
        identity_row.setContentsMargins(0, 4, 0, 0)

        github = SocialIdentityButton(
            "GitHub",
            GITHUB_USERNAME,
            "Open the CS2 Music Controller repository",
        )
        github.clicked.connect(self._open_github)

        discord = SocialIdentityButton(
            "Discord",
            DISCORD_USERNAME,
            "Copy the Discord username to the clipboard",
        )
        discord.clicked.connect(self._copy_discord_username)

        identity_row.addWidget(github)
        identity_row.addWidget(discord)
        identity_row.addStretch()

        self.feedback = QLabel()
        self.feedback.setObjectName("Faint")
        self.feedback.setMinimumHeight(18)

        layout.addWidget(title)
        layout.addWidget(creator)
        layout.addLayout(identity_row)
        layout.addWidget(self.feedback)
        return card

    def _build_source_card(self) -> QFrame:
        card = QFrame()
        layout = card_layout(card)

        title = QLabel("Source and support")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            f"The project is published under the {LICENSE_NAME}. "
            "Issues, releases, documentation, and contributions live on GitHub."
        )
        copy.setObjectName("Muted")
        copy.setWordWrap(True)

        repository = QLabel(GITHUB_URL)
        repository.setObjectName("PathLabel")
        repository.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(title)
        layout.addWidget(copy)
        layout.addWidget(repository)
        return card

    def _open_github(self) -> None:
        open_external_url(GITHUB_URL, self)

    def _copy_discord_username(self) -> None:
        QApplication.clipboard().setText(DISCORD_USERNAME)
        self.feedback.setText(f"Copied Discord username: {DISCORD_USERNAME}")
        self._feedback_timer.start(2600)

    def _clear_feedback(self) -> None:
        self.feedback.clear()
