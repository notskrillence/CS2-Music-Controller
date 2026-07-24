from pathlib import Path

from cs2mc.cs2_locator import parse_libraryfolders_vdf, render_gsi_config


def test_parse_modern_libraryfolders():
    text = r'''
    "libraryfolders"
    {
      "0" { "path" "C:\\Program Files (x86)\\Steam" }
      "1" { "path" "D:\\Games\\SteamLibrary" }
    }
    '''
    paths = parse_libraryfolders_vdf(text)
    assert Path(r"C:\Program Files (x86)\Steam") in paths
    assert Path(r"D:\Games\SteamLibrary") in paths


def test_gsi_config_is_local_and_tokenized():
    config = render_gsi_config(1337, "abc123")
    assert '"uri" "http://127.0.0.1:1337/gsi"' in config
    assert '"token" "abc123"' in config
    assert '"player_state" "1"' in config
