from __future__ import annotations

from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import AppearanceSettings
from ..ui_components import ColorSwatch, MaterialSlider
from .common import PageHeader, card_layout


class AppearancePage(QWidget):
    settings_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._loading = False
        self._seed = "#d6a24a"
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._emit_settings)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(PageHeader(
            "Appearance",
            "A Material-inspired color-role system with near-AMOLED surfaces and optional album-aware accents.",
        ))

        mode_card = QFrame()
        mode_layout = card_layout(mode_card)
        mode_title = QLabel("Theme source")
        mode_title.setObjectName("SectionTitle")
        mode_layout.addWidget(mode_title)
        mode_line = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Album dynamic", "album")
        self.mode.addItem("CS2MC dark", "dark")
        self.mode.addItem("Custom seed", "custom")
        self.mode.currentIndexChanged.connect(self._schedule)
        self.color_button = QPushButton("Choose seed color")
        self.color_button.clicked.connect(self._choose_color)
        self.color_swatch = ColorSwatch(self._seed)
        mode_line.addWidget(self.mode, 1)
        mode_line.addWidget(self.color_swatch)
        mode_line.addWidget(self.color_button)
        mode_layout.addLayout(mode_line)
        note = QLabel(
            "Album dynamic samples artwork once when the track changes. Semantic bomb, warning, and error colors remain fixed."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        mode_layout.addWidget(note)
        root.addWidget(mode_card)

        tune_card = QFrame()
        tune_layout = card_layout(tune_card)
        tune_title = QLabel("Material tuning")
        tune_title.setObjectName("SectionTitle")
        tune_layout.addWidget(tune_title)
        self.contrast, self.contrast_value = self._slider_row(tune_layout, "Contrast", -20, 30, "%")
        self.darkness, self.darkness_value = self._slider_row(tune_layout, "Surface darkness", 88, 100, "%")
        self.radius, self.radius_value = self._slider_row(tune_layout, "Corner radius", 10, 24, "px")
        self.aura, self.aura_value = self._slider_row(tune_layout, "Album aura", 0, 40, "%")
        self.animations = QCheckBox("Use subtle transitions")
        self.animations.toggled.connect(self._schedule)
        tune_layout.addWidget(self.animations)
        root.addWidget(tune_card)

        preview = QFrame()
        preview.setObjectName("HeroCard")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(22, 20, 22, 20)
        preview_layout.setSpacing(8)
        kicker = QLabel("Live preview")
        kicker.setObjectName("Kicker")
        title = QLabel("Personal, quiet, focused")
        title.setObjectName("HeroState")
        copy_label = QLabel("The accent carries selection and emphasis while the surfaces stay neutral.")
        copy_label.setObjectName("Muted")
        buttons = QHBoxLayout()
        tonal = QPushButton("Tonal action")
        tonal.setObjectName("Tonal")
        primary = QPushButton("Primary action")
        primary.setObjectName("Primary")
        buttons.addWidget(tonal)
        buttons.addWidget(primary)
        buttons.addStretch()
        preview_layout.addWidget(kicker)
        preview_layout.addWidget(title)
        preview_layout.addWidget(copy_label)
        preview_layout.addLayout(buttons)
        root.addWidget(preview)
        root.addStretch()

    def _slider_row(
        self,
        parent: QVBoxLayout,
        name: str,
        minimum: int,
        maximum: int,
        suffix: str,
    ) -> tuple[MaterialSlider, QLabel]:
        line = QHBoxLayout()
        label = QLabel(name)
        label.setMinimumWidth(130)
        slider = MaterialSlider()
        slider.setRange(minimum, maximum)
        value = QLabel("")
        value.setObjectName("Muted")
        value.setFixedWidth(48)
        slider.valueChanged.connect(lambda number, output=value, unit=suffix: output.setText(f"{number}{unit}"))
        slider.valueChanged.connect(self._schedule)
        line.addWidget(label)
        line.addWidget(slider, 1)
        line.addWidget(value)
        parent.addLayout(line)
        return slider, value

    def load_settings(self, settings: AppearanceSettings) -> None:
        clean = settings.normalized()
        self._loading = True
        index = self.mode.findData(clean.mode)
        self.mode.setCurrentIndex(max(0, index))
        self._seed = clean.seed_color
        self._update_swatch()
        self.contrast.setValue(clean.contrast)
        self.darkness.setValue(clean.surface_darkness)
        self.radius.setValue(clean.corner_radius)
        self.aura.setValue(clean.aura_strength)
        self.animations.setChecked(clean.animations)
        self._loading = False

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._seed), self, "Choose theme seed")
        if not chosen.isValid():
            return
        self._seed = chosen.name()
        self._update_swatch()
        if self.mode.currentData() != "custom":
            self.mode.setCurrentIndex(self.mode.findData("custom"))
        self._schedule()

    def _update_swatch(self) -> None:
        self.color_swatch.set_color(self._seed)
        self.color_button.setText(self._seed.upper())

    def _schedule(self, *_: object) -> None:
        if self._loading:
            return
        self._save_timer.start(120)

    def _emit_settings(self) -> None:
        settings = AppearanceSettings(
            mode=str(self.mode.currentData()),
            seed_color=self._seed,
            contrast=self.contrast.value(),
            surface_darkness=self.darkness.value(),
            corner_radius=self.radius.value(),
            aura_strength=self.aura.value(),
            animations=self.animations.isChecked(),
        ).normalized()
        self.settings_changed.emit(settings)
