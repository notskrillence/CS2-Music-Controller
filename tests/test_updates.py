from cs2mc.update_check import check_for_updates_async, is_newer


def test_version_ordering():
    assert is_newer("0.3.0", "0.2.5")
    assert is_newer("v0.3.0", "0.2.5")
    assert is_newer("0.10.0", "0.9.9")
    assert not is_newer("0.2.5", "0.2.5")
    assert not is_newer("0.2.4", "0.2.5")


def test_daily_throttle_skips_recent_check():
    called = []
    started = check_for_updates_async(
        "notskrillence/CS2-Music-Controller",
        "0.3.0",
        last_check=__import__("time").time(),
        on_result=called.append,
    )
    assert started is False
    assert called == []


def test_settings_persist_update_state(tmp_path):
    from cs2mc.config import ProfileStore

    store = ProfileStore(root=tmp_path)
    assert store.settings.last_update_check == 0.0
    assert store.settings.seen_version == ""
    store.record_update_check("0.3.0")
    assert store.settings.last_update_check > 0.0
    reloaded = ProfileStore(root=tmp_path)
    assert reloaded.settings.last_update_check > 0.0
    assert reloaded.settings.seen_version == "0.3.0"
