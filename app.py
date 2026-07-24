from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cs2mc.config import ProfileStore  # noqa: E402
from cs2mc.gui import run_gui  # noqa: E402
from cs2mc.models import resolve_asset_path  # noqa: E402


def main() -> int:
    bundled_sounds = resolve_asset_path("assets/sounds/default")
    store = ProfileStore(bundled_sounds=bundled_sounds)
    return run_gui(store)


if __name__ == "__main__":
    raise SystemExit(main())
