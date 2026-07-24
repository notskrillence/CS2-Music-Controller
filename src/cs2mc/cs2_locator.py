from __future__ import annotations

import os
import re
from pathlib import Path

GSI_FILENAME = "gamestate_integration_cs2_music_controller.cfg"
CS2_RELATIVE_CFG = Path("steamapps/common/Counter-Strike Global Offensive/game/csgo/cfg")


def _registry_steam_paths() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    found: list[Path] = []
    for hive, key_name, value_name in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
            found.append(Path(str(value)))
        except OSError:
            continue
    return found


def _default_steam_paths() -> list[Path]:
    values = [
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMFILES"),
        os.environ.get("LOCALAPPDATA"),
    ]
    paths: list[Path] = []
    for value in values:
        if not value:
            continue
        root = Path(value)
        paths.extend([root / "Steam", root / "Valve" / "Steam"])
    return paths


def parse_libraryfolders_vdf(text: str) -> list[Path]:
    """Extract Steam library paths from both old and new VDF layouts."""
    matches = re.findall(r'"path"\s+"([^"]+)"', text, flags=re.IGNORECASE)
    if not matches:
        matches = re.findall(r'^\s*"\d+"\s+"([^"]+)"', text, flags=re.MULTILINE)
    result: list[Path] = []
    for raw in matches:
        normalized = raw.replace("\\\\", "\\")
        path = Path(normalized)
        if path not in result:
            result.append(path)
    return result


def discover_steam_libraries(extra_roots: list[Path] | None = None) -> list[Path]:
    roots = [*_registry_steam_paths(), *_default_steam_paths(), *(extra_roots or [])]
    unique_roots: list[Path] = []
    for root in roots:
        try:
            resolved = root.expanduser()
        except OSError:
            continue
        if resolved not in unique_roots:
            unique_roots.append(resolved)

    libraries: list[Path] = []
    for steam_root in unique_roots:
        if steam_root not in libraries:
            libraries.append(steam_root)
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            continue
        try:
            for library in parse_libraryfolders_vdf(vdf.read_text("utf-8", errors="ignore")):
                if library not in libraries:
                    libraries.append(library)
        except OSError:
            continue
    return libraries


def detect_cs2_cfg_path(extra_roots: list[Path] | None = None) -> Path | None:
    for library in discover_steam_libraries(extra_roots):
        candidate = library / CS2_RELATIVE_CFG
        if candidate.is_dir():
            return candidate
    return None


def is_valid_cs2_cfg_path(path: str | Path) -> bool:
    candidate = Path(path)
    if not candidate.is_dir():
        return False
    normalized = "/".join(part.casefold() for part in candidate.parts)
    return normalized.endswith("counter-strike global offensive/game/csgo/cfg")


def render_gsi_config(port: int, token: str) -> str:
    return f'''"CS2 Music Controller"
{{
    "uri" "http://127.0.0.1:{port}/gsi"
    "timeout" "5.0"
    "buffer" "0.05"
    "throttle" "0.10"
    "heartbeat" "15.0"
    "auth"
    {{
        "token" "{token}"
    }}
    "data"
    {{
        "provider" "1"
        "map" "1"
        "round" "1"
        "player_id" "1"
        "player_state" "1"
        "player_match_stats" "1"
    }}
}}
'''


def install_gsi_config(cfg_dir: Path, port: int, token: str) -> Path:
    if not cfg_dir.is_dir():
        raise FileNotFoundError(f"CS2 cfg directory does not exist: {cfg_dir}")
    target = cfg_dir / GSI_FILENAME
    content = render_gsi_config(port, token)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(target)
    return target


def gsi_config_is_current(cfg_dir: Path, port: int, token: str) -> bool:
    target = cfg_dir / GSI_FILENAME
    if not target.exists():
        return False
    try:
        return target.read_text("utf-8") == render_gsi_config(port, token)
    except OSError:
        return False
