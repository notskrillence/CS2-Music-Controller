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
