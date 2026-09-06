"""Zero-idle-cost update checks against GitHub releases.

Design: one HTTPS request per day at most, stdlib only (urllib), run on a
daemon thread so the UI thread never blocks. Results are cached in the
settings file so offline or repeated launches cost nothing.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    url: str
    is_newer: bool


def _parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(value).strip().lstrip("v").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits and chunk:
            break
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def fetch_latest_release(repo: str, timeout: float = 8.0) -> tuple[str, str] | None:
    """Return (tag_name, html_url) for the latest GitHub release, or None."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CS2MC"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "ignore"))
    except Exception:
        return None
    tag = str(data.get("tag_name") or "").strip()
    url = str(data.get("html_url") or "").strip()
    if not tag or not url:
        return None
    return tag, url


def check_for_updates_async(
    repo: str,
    current_version: str,
    last_check: float,
    on_result,
    min_interval_seconds: float = 86_400.0,
) -> bool:
    """Fetch the latest release on a daemon thread unless checked recently.

    Returns True when a network check was started. `on_result` receives an
    UpdateInfo on the worker thread — the caller must marshal to the UI.
    `last_check` of 0 forces a check (used for manual "check now").
    """
    now = time.time()
    if last_check and now - last_check < min_interval_seconds:
        return False

    def worker() -> None:
        fetched = fetch_latest_release(repo)
        if fetched is None:
            return
        tag, url = fetched
        version = tag.lstrip("v")
        on_result(UpdateInfo(version=version, url=url, is_newer=is_newer(version, current_version)))

    thread = threading.Thread(target=worker, name="CS2MC-UpdateCheck", daemon=True)
    thread.start()
    return True
