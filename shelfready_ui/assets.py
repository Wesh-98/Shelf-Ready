# -*- coding: utf-8 -*-
"""Locating and loading bundled image assets.

Layout on disk:

    assets/
    ├── icons/                              # loaded at runtime
    │   ├── shelfready.ico                  # window + taskbar icon (multi-size)
    │   ├── shelfready_icon_1024.png        # master mark, theme-neutral
    │   ├── shelfready_icon_green.png       # title-bar mark, Terminal theme
    │   ├── shelfready_icon_warm.png        # title-bar mark, Warm theme
    │   └── shelfready_mark_transparent.png # mark alone, no plate
    └── design/                             # reference art, never loaded

Paths resolve relative to the project root, so the app works regardless of
the working directory it was launched from. Every loader degrades quietly:
a missing or unreadable file yields None and the GUI simply renders text,
rather than refusing to start over a decorative asset.
"""

import os
import sys


def _project_dir():
    """Root that assets are resolved against.

    PyInstaller unpacks bundled data to a temp dir and points sys._MEIPASS at
    it, so the source-tree walk from __file__ finds nothing in a frozen build.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROJECT_DIR = _project_dir()
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")

APP_ICO = os.path.join(ICONS_DIR, "shelfready.ico")
MASTER_MARK = os.path.join(ICONS_DIR, "shelfready_icon_1024.png")
TRANSPARENT_MARK = os.path.join(ICONS_DIR, "shelfready_mark_transparent.png")

# Per-theme title-bar marks, keyed by the theme names in theme.THEMES.
THEME_MARKS = {
    "green": os.path.join(ICONS_DIR, "shelfready_icon_green.png"),
    "warm": os.path.join(ICONS_DIR, "shelfready_icon_warm.png"),
}

# PhotoImage objects are garbage collected the moment the last Python
# reference drops, leaving a blank widget behind, so every image handed out
# is retained here for the life of the process.
_cache = {}


def mark_path(theme_name=None):
    """Best available mark for a theme, falling back to the master art."""
    if theme_name and theme_name in THEME_MARKS:
        path = THEME_MARKS[theme_name]
        if os.path.exists(path):
            return path
    return MASTER_MARK if os.path.exists(MASTER_MARK) else None


def load_mark(theme_name=None, size=28):
    """Return a PhotoImage of the theme's mark, or None if unavailable.

    Requires an existing Tk root. Results are cached per (path, size).
    """
    path = mark_path(theme_name)
    if not path:
        return None

    key = (path, size)
    if key in _cache:
        return _cache[key]

    try:
        from PIL import Image, ImageTk
        with Image.open(path) as im:
            im = im.convert("RGBA")
            im = im.resize((size, size), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(im)
    except Exception:
        return None

    _cache[key] = photo
    return photo


def set_window_icon(window):
    """Apply the app icon to a Tk window. Returns True if anything stuck.

    Tries the multi-size .ico first (correct for the Windows title bar and
    taskbar), then falls back to a PNG via iconphoto for other platforms or
    a missing .ico.
    """
    applied = False

    if os.path.exists(APP_ICO):
        try:
            # default= applies to this window *and* every Toplevel opened
            # later, so tooltips and message boxes inherit it too.
            window.iconbitmap(default=APP_ICO)
            applied = True
        except Exception:
            try:
                window.iconbitmap(APP_ICO)
                applied = True
            except Exception:
                pass

    photo = load_mark(None, size=64)
    if photo is not None:
        try:
            window.iconphoto(True, photo)
            applied = True
        except Exception:
            pass

    return applied


def missing():
    """Runtime assets that are referenced but not present on disk."""
    expected = [APP_ICO, MASTER_MARK, TRANSPARENT_MARK] + list(THEME_MARKS.values())
    return [p for p in expected if not os.path.exists(p)]
