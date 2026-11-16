"""World records shown in the game: the copy bundled with it, refreshed from the
PySnake repository on GitHub when online (your server's own records come from it).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

from opensnake.speedrun import CATEGORY_BY_ID, CUSTOM_PREFIX, Run

RECORDS_URL = "https://raw.githubusercontent.com/CharlieKulak/pysnake/main/pysnake/records.json"
BUNDLED_RECORDS = Path(__file__).parent / "records.json"


# ---- world records ----------------------------------------------------------

class Records:
    """World records by category id: {"time_ms", "player", "date", ...}.

    Starts from the bundled records.json (or a cached newer copy) and, when
    allowed, refreshes from GitHub in a background thread.
    """

    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path
        self.records: dict[str, dict] = {}
        self.updated: str = ""
        self.source = "none"
        self._loaded = False  # whether any records file has been accepted yet
        self._load(BUNDLED_RECORDS, "bundled")
        if cache_path:
            self._load(cache_path, "cached")

    def _accept(self, data: dict, source: str) -> bool:
        if not isinstance(data, dict) or not isinstance(data.get("records"), dict):
            return False
        updated = str(data.get("updated", ""))
        if self._loaded and updated <= self.updated:
            return False  # not newer than what we have
        clean = {}
        for cid, rec in data["records"].items():
            known = cid in CATEGORY_BY_ID or (isinstance(cid, str) and cid.startswith(CUSTOM_PREFIX))
            if known and isinstance(rec, dict) and isinstance(rec.get("time_ms"), int):
                clean[cid] = rec
        self.records, self.updated, self.source = clean, updated, source
        self._loaded = True
        return True

    def _load(self, path: Path, source: str) -> None:
        try:
            self._accept(json.loads(path.read_text()), source)
        except (OSError, ValueError):
            pass

    def get(self, category_id: str) -> dict | None:
        return self.records.get(category_id)

    def set_server(self, records: dict, site: str) -> None:
        """Use a website's own leaderboard (from its OpenSnake server) instead of records.json."""
        if not hasattr(self, "_offline"):
            self._offline = (self.records, self.updated, self.source)
        clean = {cid: r for cid, r in records.items()
                 if isinstance(r, dict) and isinstance(r.get("time_ms"), int)}
        self.records, self.updated, self.source = clean, "", f"site:{site}"

    def clear_server(self) -> None:
        """Back to the records.json world records (e.g. after disconnecting from a site)."""
        if hasattr(self, "_offline"):
            self.records, self.updated, self.source = self._offline
            del self._offline

    def refresh_in_background(self, url: str = RECORDS_URL, timeout: float = 4.0) -> None:
        def work():
            try:
                import urllib.request
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    raw = resp.read(256 * 1024)
                data = json.loads(raw)
                if self._accept(data, "online") and self.cache_path:
                    self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                    self.cache_path.write_text(json.dumps(data, indent=2))
            except Exception:
                pass  # offline or blocked: keep what we have
        threading.Thread(target=work, daemon=True).start()


def save_run(run: Run, folder: Path, player: str = "", game_version: str = "") -> Path | None:
    """Write a finished run as JSON; returns the path (None if it couldn't be written)."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = folder / f"{run.category.id}-{stamp}-{round(run.elapsed)}ms.json"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(run.to_json(player, game_version), indent=1))
        return path
    except OSError as e:
        print(f"pysnake: could not save run: {e}", file=sys.stderr)
        return None
