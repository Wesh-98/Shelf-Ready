# ShelfReady

Professional e-commerce product image processing toolkit. Cleans backgrounds, standardizes canvas size, sharpens, and runs automated quality control — all from a simple desktop GUI.

---

## Quick Start

> **Double-click `Launch ShelfReady.bat`**

The launcher will automatically create a virtual environment, install all dependencies, and open the GUI. No manual setup required.

```
Launch ShelfReady.bat          — standard launch
Launch ShelfReady (Debug).bat  — keeps console open after close (for troubleshooting)
install_codec.bat              — run once if AVIF/HEIC files fail to open
```

---

## Features

- **Background cleaning** — removes and replaces backgrounds with pure white
- **Canvas standardization** — pads or crops to a square canvas (default 1500×1500)
- **Sharpening & contrast** — configurable unsharp mask and product contrast boost
- **Batch processing** — process a folder or ZIP archive in one click; step
  through the queued images with the ◀ ▶ arrows (or Left/Right keys) to check
  them before and after a run
- **Shadow & badge overlays** — optional soft drop shadow and quantity badge
- **AVIF / HEIC support** — reads modern image formats out of the box
- **Themes** — pick a color theme from the title bar; the app mark follows it

---

## Requirements

- Windows 10/11
- Python 3.10+ (3.12 recommended for best AVIF support)

Python packages are installed automatically by the launcher:

```
numpy
Pillow
pillow-heif[avif]
scipy
```

---

## Project Structure

```
ShelfReady/
├── Launch ShelfReady.bat          # Main launcher
├── Launch ShelfReady (Debug).bat  # Debug launcher
├── install_codec.bat              # AVIF/HEIC codec installer
├── ShelfReady_Unified_GUI.py      # GUI application (window + layout)
├── image_toolkit.py               # Core image processing engine
├── requirements.txt
├── shelfready_ui/                 # GUI support modules
│   ├── theme.py                   # Color palettes & fonts
│   ├── presets.py                 # Platform presets, fit-mode snaps, option lists
│   ├── settings.py                # Validation + CLI argument assembly (no tkinter)
│   ├── runner.py                  # Runs the toolkit in-process (no tkinter)
│   └── assets.py                  # Icon/logo resolution & caching
├── assets/
│   ├── icons/                     # Loaded at runtime
│   │   ├── shelfready.ico         # Window & taskbar icon (16–256 px)
│   │   ├── shelfready_icon_1024.png        # Master mark (theme-neutral)
│   │   ├── shelfready_icon_green.png       # Title-bar mark — Terminal theme
│   │   ├── shelfready_icon_warm.png        # Title-bar mark — Warm theme
│   │   └── shelfready_mark_transparent.png # Mark alone, no plate
│   └── design/                    # Reference art, never loaded by the app
├── tests/                         # Unit tests for the tkinter-free logic
└── samples/                       # Sample images for testing
```

---

## AVIF / HEIC Support

If AVIF or HEIC files fail to open, run `install_codec.bat` once to force-install the codec. If issues persist on Python 3.14, install Python 3.12 and re-run the launcher.
