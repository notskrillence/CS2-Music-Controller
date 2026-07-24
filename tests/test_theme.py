from cs2mc.models import AppearanceSettings
from cs2mc.theme import build_palette, relative_luminance


def test_album_seed_changes_accent_not_amoled_surface():
    settings = AppearanceSettings(mode="album", surface_darkness=98)
    blue = build_palette(settings, "#3366cc")
    orange = build_palette(settings, "#dd7711")
    assert blue.primary != orange.primary
    assert blue.background == orange.background
    assert relative_luminance(blue.background) < 0.02


def test_invalid_appearance_values_are_normalized():
    settings = AppearanceSettings(
        mode="unknown",
        seed_color="bad",
        contrast=100,
        surface_darkness=10,
        corner_radius=100,
        aura_strength=-1,
    ).normalized()
    assert settings.mode == "album"
    assert settings.seed_color == "#d6a24a"
    assert settings.contrast == 30
    assert settings.surface_darkness == 88
    assert settings.corner_radius == 24
    assert settings.aura_strength == 0
