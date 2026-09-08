# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the ShelfReady desktop app.

    pip install -r requirements-dev.txt
    pyinstaller ShelfReady.spec

Produces a single windowed dist/ShelfReady.exe that needs no Python install.

Two details matter here:

* assets/icons is bundled as data and resolved at runtime through
  shelfready_ui.assets, which reads sys._MEIPASS when frozen.
* image_toolkit runs in-process (see shelfready_ui/runner.py), so scipy and
  numpy must be reachable from the frozen bundle - hence the hidden import
  for scipy.ndimage, which PyInstaller does not always pick up through the
  `from scipy.ndimage import label` alias.
"""

import os

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Keep the built exe's version in step with the app.
version_globals = {}
with open(os.path.join("shelfready_ui", "version.py"), encoding="utf-8") as fh:
    exec(fh.read(), version_globals)
APP_VERSION = version_globals["__version__"]

hidden = [
    "scipy.ndimage",
    "scipy._lib.array_api_compat.numpy.fft",
    "PIL._tkinter_finder",
]
# pillow-heif registers its openers dynamically; pull the package in whole so
# HEIC/AVIF support survives freezing.
hidden += collect_submodules("pillow_heif")

a = Analysis(
    ["ShelfReady_Unified_GUI.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/icons/*", "assets/icons"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim test frameworks and headless plotting stacks we never touch.
    excludes=["pytest", "matplotlib", "tkinter.test", "test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ShelfReady",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # windowed: no console flashes on a run
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icons/shelfready.ico",
    version_info={"version": APP_VERSION},
)
