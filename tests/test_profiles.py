from pathlib import Path

from cs2mc.config import ProfileStore


def test_profile_lifecycle(tmp_path: Path):
    store = ProfileStore(root=tmp_path)
    default = store.active_profile()
    created = store.create_profile("Competitive", default)
    store.set_active_profile(created.id)
    assert store.active_profile().name == "Competitive"
    created.volumes["game"] = 3
    store.save_profile(created)
    assert store.get_profile(created.id).volumes["game"] == 3
    store.delete_profile(created.id)
    assert store.settings.active_profile_id == "default"


def test_atomic_settings_created(tmp_path: Path):
    store = ProfileStore(root=tmp_path)
    assert store.settings_path.exists()
    assert store.settings.gsi_token


def test_profile_rename_and_appearance_persist(tmp_path: Path):
    from cs2mc.models import AppearanceSettings

    store = ProfileStore(root=tmp_path)
    created = store.create_profile("Old name", store.active_profile())
    renamed = store.rename_profile(created.id, "Faceit")
    assert renamed.name == "Faceit"

    appearance = AppearanceSettings(
        mode="custom",
        seed_color="#336699",
        contrast=12,
        surface_darkness=99,
        corner_radius=20,
        aura_strength=24,
        animations=False,
    )
    store.set_appearance(appearance)
    reloaded = ProfileStore(root=tmp_path)
    assert reloaded.settings.appearance == appearance.normalized()


def test_kill_streak_profiles_are_independent(tmp_path: Path):
    sounds = tmp_path / "sounds"
    sounds.mkdir()
    for name in (
        "valorant-1-kill.mp3",
        "valorant-2-kills.mp3",
        "valorant-3-kills.mp3",
        "valorant-4-kills.mp3",
        "valorant-5-kills.mp3",
        "reaverkill1.mp3",
        "reaverkill2.mp3",
        "reaverkill3.mp3",
        "reaverkill4.mp3",
        "reaverkill5.mp3",
        "kill_1.wav",
        "kill_2.wav",
        "kill_3.wav",
        "kill_4.wav",
        "kill_5.wav",
    ):
        (sounds / name).write_bytes(b"test")

    store = ProfileStore(root=tmp_path / "app", bundled_sounds=sounds)
    kill_profiles = store.list_kill_streak_profiles()
    assert [profile.name for profile in kill_profiles[:3]] == [
        "VALORANT",
        "Reaver",
        "Tones",
    ]
    assert store.active_kill_streak_profile().id == "tones"

    audio = store.create_profile("Competitive", store.active_profile())
    store.set_active_profile(audio.id)
    store.set_active_kill_streak_profile("reaver")
    assert store.active_profile().id == audio.id
    assert store.active_kill_streak_profile().id == "reaver"

    changed = store.active_kill_streak_profile()
    changed.volume = 63
    store.save_kill_streak_profile(changed)
    assert store.get_kill_streak_profile("reaver").volume == 63
    assert not hasattr(store.active_profile(), "kill_streak_sounds")


def test_legacy_embedded_kill_streak_settings_migrate(tmp_path: Path):
    profiles = tmp_path / "profiles"
    profiles.mkdir(parents=True)
    legacy_sound = tmp_path / "custom.mp3"
    legacy_sound.write_bytes(b"test")
    (profiles / "default.json").write_text(
        """{
  "id": "default",
  "name": "Balanced",
  "volumes": {},
  "kill_streak_enabled": true,
  "kill_streak_volume": 77,
  "kill_streak_sounds": {"1": "%s"}
}""" % str(legacy_sound).replace("\\", "\\\\"),
        encoding="utf-8",
    )

    store = ProfileStore(root=tmp_path)
    migrated = store.active_kill_streak_profile()
    assert migrated.name == "Balanced Kill Streaks"
    assert migrated.volume == 77
    assert migrated.sounds["1"] == str(legacy_sound)
    raw_audio = (profiles / "default.json").read_text(encoding="utf-8")
    assert "kill_streak_sounds" not in raw_audio


def test_built_in_kill_streak_paths_repair_after_app_moves(tmp_path: Path):
    old_sounds = tmp_path / "old" / "sounds"
    new_sounds = tmp_path / "new" / "sounds"
    old_sounds.mkdir(parents=True)
    new_sounds.mkdir(parents=True)

    filenames = (
        "valorant-1-kill.mp3",
        "valorant-2-kills.mp3",
        "valorant-3-kills.mp3",
        "valorant-4-kills.mp3",
        "valorant-5-kills.mp3",
        "reaverkill1.mp3",
        "reaverkill2.mp3",
        "reaverkill3.mp3",
        "reaverkill4.mp3",
        "reaverkill5.mp3",
        "kill_1.wav",
        "kill_2.wav",
        "kill_3.wav",
        "kill_4.wav",
        "kill_5.wav",
    )
    for filename in filenames:
        (old_sounds / filename).write_bytes(b"old")
        (new_sounds / filename).write_bytes(b"new")

    root = tmp_path / "app"
    original = ProfileStore(root=root, bundled_sounds=old_sounds)
    customized = original.get_kill_streak_profile("tones")
    custom_sound = tmp_path / "my-custom.wav"
    custom_sound.write_bytes(b"custom")
    customized.sounds["2"] = str(custom_sound)
    original.save_kill_streak_profile(customized)

    for path in old_sounds.iterdir():
        path.unlink()
    old_sounds.rmdir()

    moved = ProfileStore(root=root, bundled_sounds=new_sounds)
    repaired = moved.get_kill_streak_profile("tones")
    assert repaired.sounds["1"] == str(new_sounds / "kill_1.wav")
    assert repaired.sounds["2"] == str(custom_sound)
