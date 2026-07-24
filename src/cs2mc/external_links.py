"""Centralized external-link handling for UI surfaces."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget


def open_external_url(url: str, parent: QWidget | None = None) -> bool:
    """Open a trusted project URL and report a shell failure clearly."""
    opened = QDesktopServices.openUrl(QUrl(url))
    if not opened and parent is not None:
        QMessageBox.warning(
            parent,
            "Could not open link",
            "Windows could not open the link in your default browser.",
        )
    return bool(opened)
