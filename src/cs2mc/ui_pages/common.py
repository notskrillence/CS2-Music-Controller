from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


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


def card_layout(
    frame: QFrame,
    margins: tuple[int, int, int, int] = (18, 18, 18, 18),
) -> QVBoxLayout:
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(12)
    return layout


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    return line


def set_path_label(label: QLabel, path: str, empty_text: str) -> None:
    if not path:
        label.setText(empty_text)
        label.setToolTip("")
        return
    source = Path(path)
    label.setText(source.name if source.is_file() else f"{source.name} (missing)")
    label.setToolTip(path)
