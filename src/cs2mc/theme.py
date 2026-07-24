from __future__ import annotations

import colorsys
from dataclasses import dataclass

from .models import AppearanceSettings

DEFAULT_SEED = "#d6a24a"


@dataclass(frozen=True, slots=True)
class ThemePalette:
    seed: str
    background: str
    surface_low: str
    surface: str
    surface_high: str
    surface_highest: str
    outline: str
    outline_strong: str
    text: str
    text_muted: str
    text_faint: str
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    secondary: str
    tertiary: str
    success: str = "#74d69a"
    warning: str = "#efc76f"
    danger: str = "#ff8396"


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(channel))):02x}" for channel in rgb)


def mix(a: str, b: str, amount: float) -> str:
    amount = max(0.0, min(1.0, amount))
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    return _hex((ar + (br - ar) * amount, ag + (bg - ag) * amount, ab + (bb - ab) * amount))


def shift_hsl(value: str, *, hue: float = 0.0, saturation: float = 0.0, lightness: float = 0.0) -> str:
    r, g, b = (channel / 255.0 for channel in _rgb(value))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + hue / 360.0) % 1.0
    s = max(0.0, min(1.0, s + saturation))
    l = max(0.0, min(1.0, l + lightness))
    rr, gg, bb = colorsys.hls_to_rgb(h, l, s)
    return _hex((rr * 255, gg * 255, bb * 255))


def relative_luminance(value: str) -> float:
    def channel(v: int) -> float:
        x = v / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = _rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def on_color(value: str) -> str:
    return "#11100d" if relative_luminance(value) > 0.42 else "#ffffff"


def build_palette(settings: AppearanceSettings, album_seed: str | None = None) -> ThemePalette:
    clean = settings.normalized()
    seed = clean.seed_color
    if clean.mode == "dark":
        seed = DEFAULT_SEED
    elif clean.mode == "album" and album_seed:
        seed = album_seed

    # Keep dark surfaces neutral. The seed is reserved for selection and emphasis,
    # which prevents album art from repainting the entire application.
    black = "#000000"
    darkness = clean.surface_darkness / 100.0
    background = mix("#111111", black, max(0.0, min(1.0, (darkness - 0.88) / 0.12)) * 0.78)
    surface_low = mix(background, "#ffffff", 0.025)
    surface = mix(background, "#ffffff", 0.055)
    surface_high = mix(background, "#ffffff", 0.085)
    surface_highest = mix(background, "#ffffff", 0.12)

    contrast_adjust = clean.contrast / 100.0
    primary = shift_hsl(seed, saturation=0.05 + contrast_adjust * 0.2, lightness=0.08 + contrast_adjust * 0.12)
    primary_container = mix(surface_highest, primary, 0.28 + max(0.0, contrast_adjust) * 0.16)
    secondary = shift_hsl(primary, hue=28, saturation=-0.08, lightness=-0.02)
    tertiary = shift_hsl(primary, hue=-42, saturation=-0.04, lightness=0.02)

    text = mix("#ffffff", primary, 0.025)
    text_muted = mix(text, background, 0.34 - contrast_adjust * 0.12)
    text_faint = mix(text, background, 0.58 - contrast_adjust * 0.10)
    outline = mix(surface_highest, text, 0.12 + max(0.0, contrast_adjust) * 0.06)
    outline_strong = mix(surface_highest, text, 0.22 + max(0.0, contrast_adjust) * 0.08)

    return ThemePalette(
        seed=seed,
        background=background,
        surface_low=surface_low,
        surface=surface,
        surface_high=surface_high,
        surface_highest=surface_highest,
        outline=outline,
        outline_strong=outline_strong,
        text=text,
        text_muted=text_muted,
        text_faint=text_faint,
        primary=primary,
        on_primary=on_color(primary),
        primary_container=primary_container,
        on_primary_container=text,
        secondary=secondary,
        tertiary=tertiary,
    )


def dominant_seed_from_image(data: bytes | None) -> str | None:
    """Return a stable, colorful seed from compressed artwork bytes.

    QImage is imported lazily so configuration and non-GUI tests remain lightweight.
    The image is sampled into coarse RGB buckets; near-black, near-white, and
    skin-like low-saturation pixels are intentionally de-prioritized.
    """
    if not data:
        return None
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
    except ImportError:
        return None

    image = QImage.fromData(data)
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format.Format_RGB32).scaled(
        64,
        64,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    buckets: dict[tuple[int, int, int], tuple[int, float]] = {}
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            color = image.pixelColor(x, y)
            r, g, b = color.red(), color.green(), color.blue()
            _, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if v < 0.16 or v > 0.94 or s < 0.18:
                continue
            key = (r // 32, g // 32, b // 32)
            count, score = buckets.get(key, (0, 0.0))
            # Population matters most, then saturation and usable mid/high value.
            quality = 0.65 + s * 1.4 + (1.0 - abs(v - 0.62)) * 0.5
            buckets[key] = (count + 1, score + quality)
    if not buckets:
        return None
    key = max(buckets, key=lambda item: buckets[item][0] * buckets[item][1])
    r = key[0] * 32 + 16
    g = key[1] * 32 + 16
    b = key[2] * 32 + 16
    seed = _hex((r, g, b))
    # Dynamic accents need enough brightness for dark surfaces.
    return shift_hsl(seed, saturation=0.06, lightness=0.06)


def apply_application_palette(app: object, palette: ThemePalette) -> None:
    """Apply shared Qt color roles used by custom-painted controls.

    The import stays local so theme math remains testable without PySide6.
    """
    from PySide6.QtGui import QColor, QPalette

    qt_palette = QPalette()
    role = QPalette.ColorRole
    qt_palette.setColor(role.Window, QColor(palette.background))
    qt_palette.setColor(role.WindowText, QColor(palette.text))
    qt_palette.setColor(role.Base, QColor(palette.surface_low))
    qt_palette.setColor(role.AlternateBase, QColor(palette.surface))
    qt_palette.setColor(role.ToolTipBase, QColor(palette.surface_highest))
    qt_palette.setColor(role.ToolTipText, QColor(palette.text))
    qt_palette.setColor(role.Text, QColor(palette.text))
    qt_palette.setColor(role.Button, QColor(palette.surface_high))
    qt_palette.setColor(role.ButtonText, QColor(palette.text))
    qt_palette.setColor(role.BrightText, QColor("#ffffff"))
    qt_palette.setColor(role.Highlight, QColor(palette.primary))
    qt_palette.setColor(role.HighlightedText, QColor(palette.on_primary))
    qt_palette.setColor(role.PlaceholderText, QColor(palette.text_muted))
    qt_palette.setColor(role.Mid, QColor(palette.surface_highest))
    qt_palette.setColor(role.Midlight, QColor(palette.outline_strong))
    qt_palette.setColor(role.Dark, QColor(palette.surface_low))
    qt_palette.setColor(role.Light, QColor(palette.text_faint))
    app.setPalette(qt_palette)  # type: ignore[attr-defined]


def build_stylesheet(p: ThemePalette, settings: AppearanceSettings, font_family: str) -> str:
    radius = settings.normalized().corner_radius
    small = max(8, radius - 6)
    pill = 18
    return f"""
* {{
    font-family: \"{font_family}\";
    font-size: 13px;
    font-weight: 400;
    color: {p.text};
}}
QMainWindow, QDialog, QWidget#Root {{ background: {p.background}; }}
QWidget#Page {{ background: transparent; }}
QLabel {{ background: transparent; }}
QFrame#WindowSurface {{ background: {p.background}; border: 1px solid {p.outline}; }}
QFrame#TitleBar {{ background: {p.background}; border-bottom: 1px solid {p.outline}; }}
QLabel#WindowTitle {{ color: {p.text}; font-size: 13px; font-weight: 600; }}
QLabel#WindowMark {{ color: {p.on_primary}; background: {p.primary}; border-radius: 10px; font-size: 11px; font-weight: 700; padding: 5px 8px; }}
WindowControlButton, MaterialIconButton, QToolButton#ProfileMenuButton {{ background: transparent; border: 0; padding: 0; }}
QFrame#Sidebar {{ background: {p.surface_low}; border-right: 1px solid {p.outline}; }}
QLabel#Brand {{ color: {p.text}; font-size: 15px; font-weight: 700; }}
QLabel#BrandCaption {{ color: {p.text_faint}; font-size: 11px; }}
QPushButton#NavButton {{
    text-align: left; padding: 10px 13px; border: 0; border-radius: {small}px;
    color: {p.text_muted}; background: transparent; font-weight: 500;
}}
QPushButton#NavButton:hover {{ background: {p.surface_high}; color: {p.text}; }}
QPushButton#NavButton:pressed {{ background: {p.surface_highest}; }}
QPushButton#NavButton:checked {{ background: {p.primary_container}; color: {p.text}; font-weight: 600; }}
QLabel#PageTitle {{ color: {p.text}; font-size: 25px; font-weight: 600; }}
QLabel#PageSubtitle {{ color: {p.text_muted}; font-size: 13px; }}
QFrame#Card {{ background: {p.surface}; border: 1px solid {p.outline}; border-radius: {radius}px; }}
QFrame#RaisedCard {{ background: {p.surface_high}; border: 1px solid {p.outline}; border-radius: {radius}px; }}
QFrame#HeroCard {{ background: {p.primary_container}; border: 1px solid {mix(p.primary_container, p.primary, 0.22)}; border-radius: {radius + 6}px; }}
QFrame#AuraCard {{ background: {mix(p.surface, p.primary, settings.aura_strength / 260.0)}; border: 1px solid {mix(p.outline, p.primary, 0.20)}; border-radius: {radius}px; }}
QLabel#Kicker {{ color: {p.text_muted}; font-size: 11px; font-weight: 600; }}
QLabel#HeroState {{ color: {p.text}; font-size: 39px; font-weight: 600; }}
QLabel#MetricValue {{ color: {p.text}; font-size: 22px; font-weight: 600; }}
QLabel#MetricLabel {{ color: {p.text_muted}; font-size: 12px; }}
QLabel#SectionTitle {{ color: {p.text}; font-size: 15px; font-weight: 600; }}
QLabel#CreditName {{ color: {p.primary}; font-size: 30px; font-weight: 700; }}
QLabel#Muted {{ color: {p.text_muted}; }}
QLabel#Faint {{ color: {p.text_faint}; font-size: 12px; }}
QLabel#Success {{ color: {p.success}; font-weight: 600; }}
QLabel#Warning {{ color: {p.warning}; font-weight: 600; }}
QLabel#Danger {{ color: {p.danger}; font-weight: 600; }}
QLabel#PathLabel {{ color: {p.text_muted}; background: {p.surface_low}; border: 1px solid {p.outline}; border-radius: {small}px; padding: 7px 9px; }}
QLabel#AboutIcon {{ background: {p.surface_low}; border: 1px solid {mix(p.outline, p.primary, 0.24)}; border-radius: 18px; }}
QPushButton, QToolButton {{
    color: {p.text}; background: {p.surface_high}; border: 1px solid {p.outline};
    border-radius: {small}px; padding: 8px 13px; font-weight: 500; min-height: 20px;
}}
QPushButton:hover, QToolButton:hover {{ background: {p.surface_highest}; border-color: {p.outline_strong}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {p.surface_low}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {p.text_faint}; background: {p.surface_low}; border-color: {p.outline}; }}
QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus {{ border: 1px solid {p.primary}; }}
QPushButton#Primary {{ background: {p.primary}; border-color: {p.primary}; color: {p.on_primary}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {shift_hsl(p.primary, lightness=0.055)}; border-color: {shift_hsl(p.primary, lightness=0.055)}; }}
QPushButton#Tonal {{ background: {p.primary_container}; border-color: {mix(p.primary_container, p.primary, 0.25)}; color: {p.text}; }}
QPushButton#DangerButton {{ color: {p.danger}; }}
QPushButton#Chip {{ border-radius: {pill}px; padding: 7px 12px; }}
QPushButton#Chip:checked {{ background: {p.primary_container}; border-color: {mix(p.primary_container, p.primary, 0.3)}; }}
QPushButton#SocialIdentityButton {{
    border-radius: 20px; padding: 8px 17px; min-height: 22px; font-weight: 600;
}}
QPushButton#SocialIdentityButton[platform="github"] {{
    color: #f0f3f6; background: #24292f; border-color: #3d444d;
}}
QPushButton#SocialIdentityButton[platform="github"]:hover {{
    background: #30363d; border-color: #59636e;
}}
QPushButton#SocialIdentityButton[platform="github"]:pressed {{ background: #1b1f24; }}
QPushButton#SocialIdentityButton[platform="discord"] {{
    color: #ffffff; background: #5865f2; border-color: #7180ff;
}}
QPushButton#SocialIdentityButton[platform="discord"]:hover {{
    background: #6875f5; border-color: #8993ff;
}}
QPushButton#SocialIdentityButton[platform="discord"]:pressed {{ background: #4752c4; }}
QLineEdit, QComboBox {{
    background: {p.surface_low}; color: {p.text}; border: 1px solid {p.outline};
    border-radius: {small}px; padding: 8px 10px; min-height: 22px;
}}
QComboBox::drop-down {{ border: 0; width: 28px; }}
QComboBox QAbstractItemView {{ background: {p.surface_high}; color: {p.text}; selection-background-color: {p.primary_container}; border: 1px solid {p.outline}; outline: 0; padding: 5px; }}
QMenu {{ background: {p.surface_high}; color: {p.text}; border: 1px solid {p.outline}; border-radius: {small}px; padding: 6px; }}
QMenu::item {{ padding: 8px 24px 8px 10px; border-radius: 7px; }}
QMenu::item:selected {{ background: {p.primary_container}; }}
MaterialSlider {{ background: transparent; min-height: 36px; }}
MaterialProgressBar {{ background: transparent; }}
QCheckBox {{ color: {p.text}; spacing: 9px; min-height: 28px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {p.outline_strong}; border-radius: 6px; background: {p.surface_low}; }}
QCheckBox::indicator:checked {{ background: {p.primary}; border-color: {p.primary}; }}
QScrollArea {{ border: 0; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 4px 2px 4px 2px; }}
QScrollBar::handle:vertical {{ background: {p.outline_strong}; border-radius: 5px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {mix(p.outline_strong, p.primary, 0.24)}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px 4px 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {p.outline_strong}; border-radius: 5px; min-width: 36px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
QFrame#ProfileCard {{ background: {p.surface}; border: 1px solid {p.outline}; border-radius: {radius}px; }}
QFrame#ProfileCard:hover {{ background: {p.surface_high}; border-color: {p.outline_strong}; }}
QFrame#ProfileCard[active="true"] {{ background: {p.primary_container}; border: 1px solid {mix(p.primary_container, p.primary, 0.42)}; }}
QLabel#ProfileBadge {{ color: {p.on_primary}; background: {p.primary}; border-radius: 10px; padding: 3px 8px; font-size: 11px; font-weight: 600; }}
QLabel#CircleBadge {{ color: {p.on_primary}; background: {p.primary}; border-radius: 18px; font-size: 13px; font-weight: 700; }}
QFrame#Divider {{ background: {p.outline}; min-height: 1px; max-height: 1px; border: 0; }}
QSizeGrip {{ width: 16px; height: 16px; background: transparent; }}
QToolTip {{ color: {p.text}; background: {p.surface_highest}; border: 1px solid {p.outline_strong}; border-radius: 8px; padding: 6px 8px; }}
"""
