# -*- coding: utf-8 -*-
"""Support modules for the ShelfReady GUI.

theme.py and presets.py hold pure data (colors, fonts, preset tables).
settings.py and runner.py hold the tkinter-free logic — validating the
settings dict, turning it into an image_toolkit.py argv, running that
subprocess and parsing what it prints back. Keeping those two free of
tkinter is what makes them testable without a display.
"""
