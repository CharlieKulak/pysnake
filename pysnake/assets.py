"""Optional asset packs.

PySnake ships with no image or sound files: everything is drawn and
synthesized in code. An asset pack is a folder of your own files that replace
individual built-in sprites, sounds or colours. Any file that is missing falls
back to the built-in version, so a pack can be as small as one image.

Packs are looked up, in order, in:
  1. the folder passed with ``pysnake --assets DIR``
  2. the ``PYSNAKE_ASSETS`` environment variable
  3. ``<config dir>/assets`` (see ``config_dir``)

See README.md for the list of file names.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pygame

IMAGE_EXTS = (".svg", ".png", ".webp", ".gif", ".bmp", ".jpg", ".jpeg")
SOUND_EXTS = (".ogg", ".wav", ".mp3", ".flac")

# Colour keys accepted in pack.json, as "#rrggbb" strings.
COLOR_KEYS = ("board_light", "board_dark", "board_sand", "board_sand_dark", "border", "header",
              "snake_head", "snake_tail")


def _base_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home()))
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def config_dir() -> Path:
    """Where settings, scores, runs, packs and mods live.

    PYSNAKE_CONFIG_DIR overrides it on every platform (portable installs, tests).
    The first time PySnake runs, it brings over the settings this game kept when
    it was called OpenSnake.
    """
    override = os.environ.get("PYSNAKE_CONFIG_DIR") or os.environ.get("OPENSNAKE_CONFIG_DIR")
    if override:
        return Path(override)
    new = _base_dir() / ("PySnake" if sys.platform in ("win32", "darwin") else "pysnake")
    if not new.exists():
        old = _base_dir() / ("OpenSnake" if sys.platform in ("win32", "darwin") else "opensnake")
        if old.is_dir():
            try:
                import shutil
                # (Crustacean keeps its own file in the old folder: leave it there)
                shutil.copytree(old, new, ignore=shutil.ignore_patterns("opensnake-rs.json", "crustacean.json"))
            except OSError:
                pass
    return new


def parse_color(value):
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            return None
    if isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(v, int) for v in value):
        return tuple(value)
    return None


class AssetPack:
    def __init__(self, dirs=()):
        self.dirs = [Path(d).expanduser() for d in dirs if d and Path(d).expanduser().is_dir()]
        self.colors: dict[str, tuple[int, int, int]] = {}
        for d in reversed(self.dirs):  # earlier folders win
            try:
                data = json.loads((d / "pack.json").read_text())
            except (OSError, ValueError):
                continue
            for key in COLOR_KEYS:
                col = parse_color(data.get(key))
                if col:
                    self.colors[key] = col

    @classmethod
    def default(cls, cli_dir: str | None = None) -> "AssetPack":
        return cls([cli_dir, os.environ.get("PYSNAKE_ASSETS"), config_dir() / "assets"])

    def _find(self, name: str, exts) -> Path | None:
        for d in self.dirs:
            for ext in exts:
                p = d / (name + ext)
                if p.is_file():
                    return p
        return None

    def image_path(self, name: str) -> Path | None:
        return self._find(name, IMAGE_EXTS)

    def sound(self, name: str) -> Path | None:
        return self._find(name, SOUND_EXTS)

    def color(self, key: str, default):
        return self.colors.get(key, default)


def load_image(path: Path, size: int) -> pygame.Surface | None:
    """Load an image as a size x size surface.

    SVGs are rendered directly at that size, so they stay sharp at any
    resolution; bitmaps are smooth-scaled.
    """
    try:
        if path.suffix.lower() == ".svg":
            return pygame.image.load_sized_svg(str(path), (size, size))
        img = pygame.image.load(str(path))
        if pygame.display.get_surface():
            img = img.convert_alpha()
        return pygame.transform.smoothscale(img, (size, size))
    except (pygame.error, OSError, ValueError) as e:
        print(f"pysnake: could not load {path}: {e}", file=sys.stderr)
        return None
