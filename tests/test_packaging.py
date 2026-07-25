from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_uses_essentials_without_qt_multimedia():
    requirements = (ROOT / "requirements.txt").read_text()
    sound_player = (ROOT / "src/cs2mc/sound_player.py").read_text()
    build_script = (ROOT / "build_release.ps1").read_text()

    assert "PySide6-Essentials" in requirements
    assert "\nPySide6>=" not in f"\n{requirements}"
    assert "from PySide6.QtMultimedia" not in sound_player
    assert "winrt-Windows.Media.Core" not in requirements
    assert "winrt-Windows.Media.Playback" not in requirements
    assert '--hidden-import "winrt.windows.media.core"' not in build_script
    assert '--hidden-import "winrt.windows.media.playback"' not in build_script
    assert '--exclude-module "PySide6.QtMultimedia"' in build_script
    assert "pip uninstall -y PySide6 PySide6-Addons" in build_script


def test_repository_images_are_small_and_not_packaged_as_app_assets():
    banner = ROOT / "docs/images/banner.jpg"
    preview = ROOT / "docs/images/social-preview.jpg"

    assert banner.is_file()
    assert preview.is_file()
    assert banner.stat().st_size < 1_000_000
    assert preview.stat().st_size < 1_000_000


def test_all_bundled_kill_streak_files_are_present():
    sounds = ROOT / "assets/sounds/default"
    expected = {
        *(f"kill_{number}.wav" for number in range(1, 6)),
        *(f"reaverkill{number}.mp3" for number in range(1, 6)),
        "valorant-1-kill.mp3",
        *(f"valorant-{number}-kills.mp3" for number in range(2, 6)),
    }
    assert expected <= {path.name for path in sounds.iterdir() if path.is_file()}
