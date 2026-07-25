from pathlib import Path

import pytest

from cs2mc.windows_sound_backend import WindowsSoundBackend


class FakeMCI:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def __call__(self, command: str, _buffer_chars: int) -> str:
        self.commands.append(command)
        if command.startswith("status ") and command.endswith(" length"):
            return "1250"
        return ""


def test_windows_sound_backend_opens_plays_and_releases_mp3(tmp_path: Path):
    source = tmp_path / "kill sound.mp3"
    source.write_bytes(b"fake")
    mci = FakeMCI()
    backend = WindowsSoundBackend(command=mci)

    handle = backend.play(source, 0.42)

    assert handle.alias.startswith("cs2mc_sound_")
    assert handle.duration_ms == 2000
    assert any(command.startswith('open "') and "type mpegvideo" in command for command in mci.commands)
    assert f"setaudio {handle.alias} volume to 420" in mci.commands
    assert f"play {handle.alias} from 0" in mci.commands

    backend.close(handle)
    assert f"stop {handle.alias}" in mci.commands
    assert f"close {handle.alias}" in mci.commands


def test_windows_sound_backend_uses_waveaudio_for_wav(tmp_path: Path):
    source = tmp_path / "tone.wav"
    source.write_bytes(b"fake")
    mci = FakeMCI()
    backend = WindowsSoundBackend(command=mci)

    backend.play(source, 1.0)

    assert any("type waveaudio" in command for command in mci.commands)


def test_windows_sound_backend_rejects_unsupported_formats(tmp_path: Path):
    source = tmp_path / "sound.flac"
    source.write_bytes(b"fake")
    backend = WindowsSoundBackend(command=FakeMCI())

    with pytest.raises(ValueError):
        backend.play(source, 1.0)
