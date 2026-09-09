# ShelfReady

Professional e-commerce product image processing toolkit. Cleans backgrounds,
standardizes canvas size, and sharpens — from a desktop GUI on Windows, or from
any browser.

---

## Quick Start

> **Double-click `Launch ShelfReady.bat`**

The launcher will automatically create a virtual environment, install all dependencies, and open the GUI. No manual setup required.

```
Launch ShelfReady.bat          — standard launch
Launch ShelfReady (Debug).bat  — keeps console open after close (for troubleshooting)
install_codec.bat              — run once if AVIF/HEIC files fail to open
```

### Standalone executable

`.github/workflows/release.yml` builds a single-file `ShelfReady.exe` with
PyInstaller and attaches it to the GitHub release whenever a `v*` tag is
pushed:

```
git tag v1.0.0 && git push origin v1.0.0
```

To build one locally instead, install `requirements-dev.txt` and run
`pyinstaller ShelfReady.spec`. The exe is not code-signed, so Windows
SmartScreen warns that the publisher is unknown — **More info → Run anyway**.

---

## The web app

**Live at <https://shelfready.lefeelabs.site>** — one image at a time, no
install, any platform.

Run it locally with:

```
.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.venv\Scripts\python.exe -m uvicorn shelfready_web.app:app --reload
```

Then open <http://127.0.0.1:8000>.

The web front end replaces only the tkinter layer: it hands the same settings
dict to the same `shelfready_ui.settings` and `image_toolkit` code the desktop
app runs, so both produce identical output for identical settings. What it
adds is the handling untrusted input requires — an upload cap, content
sniffing, tightened numeric ranges (`shelfready_web/params.py`), per-IP rate
limiting, and a private temp directory per request that is deleted when the
response is sent.

The desktop app remains the better tool for volume: it processes folders and
ZIP archives, the web app takes one image per run.

### Deploying it

Live at **<https://shelfready.lefeelabs.site>**, hosted on Fly.io as the app
`shelfready-lefeelabs` — Fly app names are global and `shelfready` was taken,
which affects the CNAME target only, never the public address.

See **[docs/DEPLOY.md](docs/DEPLOY.md)** for the full walkthrough — Fly.io for
hosting, with the exact Namecheap DNS records. The short version:

```
fly launch --no-deploy       # once; app name and region live in fly.toml
fly deploy --remote-only     # builds on Fly, so no local Docker needed
fly certs add shelfready.lefeelabs.site   # creates the cert
fly certs setup shelfready.lefeelabs.site # reprints the CNAME to add
```

`fly.toml` runs one 1 GB `shared-cpu-1x` machine that scales to zero between
requests. 512 MB is not enough — numpy, scipy and Pillow together will OOM on
a large canvas. `primary_region` is where every upload travels to.

Pushing to `master` redeploys via `.github/workflows/deploy.yml`, which needs
a `FLY_API_TOKEN` repository secret (`fly tokens create deploy`).

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
├── requirements.txt               # Runtime deps for the desktop app
├── requirements-web.txt           # + FastAPI/uvicorn for the web front end
├── requirements-dev.txt           # + PyInstaller and httpx for builds & tests
├── shelfready_ui/                 # GUI support modules
│   ├── theme.py                   # Color palettes & fonts
│   ├── presets.py                 # Platform presets, fit-mode snaps, option lists
│   ├── settings.py                # Validation + CLI argument assembly (no tkinter)
│   ├── runner.py                  # Runs the toolkit in-process (no tkinter)
│   ├── assets.py                  # Icon/logo resolution & caching
│   └── version.py                 # Version, studio name & URL (single source)
├── assets/
│   ├── icons/                     # Loaded at runtime
│   │   ├── shelfready.ico         # Window & taskbar icon (16–256 px)
│   │   ├── shelfready_icon_1024.png        # Master mark (theme-neutral)
│   │   ├── shelfready_icon_green.png       # Title-bar mark — Terminal theme
│   │   ├── shelfready_icon_warm.png        # Title-bar mark — Warm theme
│   │   └── shelfready_mark_transparent.png # Mark alone, no plate
│   └── design/                    # Reference art, never loaded by the app
├── shelfready_web/                # The hosted web front end
│   ├── app.py                     # FastAPI routes
│   ├── params.py                  # Untrusted-input handling & web limits
│   ├── jobs.py                    # Temp workspace, upload checks, one job
│   ├── build_theme_css.py         # Generates static/theme.css from theme.py
│   └── static/                    # index.html, app.js, style.css
├── Dockerfile, fly.toml           # How the web app is built and hosted
├── ShelfReady.spec                # PyInstaller recipe for the standalone exe
├── .github/workflows/             # tests.yml, deploy.yml, release.yml
├── docs/DEPLOY.md                 # Full hosting + DNS walkthrough
├── LICENSE                        # MIT
└── tests/                         # Unit tests for the tkinter-free logic
```

The site's palette is generated from `shelfready_ui/theme.py` so it cannot
drift from the desktop app's. After editing `THEMES`, run:

```
.venv\Scripts\python.exe -m shelfready_web.build_theme_css
```

`tests/test_web.py` fails if you forget.

---

## Tests

```
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite covers the tkinter-free logic only — settings validation, theme
generation, asset resolution, and the whole web job path — so it needs no
display and no running server. `.github/workflows/tests.yml` runs it on
Windows against Python 3.12 and 3.13 on every push.

---

## License

MIT — see [LICENSE](LICENSE).

---

## AVIF / HEIC Support

If AVIF or HEIC files fail to open, run `install_codec.bat` once to force-install the codec. If issues persist on Python 3.14, install Python 3.12 and re-run the launcher.
