# -*- coding: utf-8 -*-
"""Preset tables and static option lists for the GUI."""

# Canvas size / quality defaults per marketplace.
PLATFORM_PRESETS = {
    "Custom":  {},
    "Amazon":  {"size": "2000", "quality": "95"},
    "Shopify": {"size": "2048", "quality": "90"},
    "eBay":    {"size": "1600", "quality": "85"},
    "Etsy":    {"size": "2000", "quality": "90"},
    "Walmart": {"size": "2000", "quality": "95"},
}

# Choosing a fit mode snaps the framing params to values that suit it,
# so the user doesn't have to know which of the 15 knobs matter.
# (target_fill, margin_pct, min_top_pad_px, allow_upscale) — None = leave alone.
FIT_MODE_SNAPS = {
    "fill_width":  {"fill": "0.99", "margin": "0.0",   "tpad": None,  "upscale": True},
    "fill_height": {"fill": "0.97", "margin": None,    "tpad": "30",  "upscale": True},
    "pad":         {"fill": "0.84", "margin": "0.015", "tpad": "120", "upscale": None},
    "fit":         {"fill": "0.84", "margin": "0.015", "tpad": "120", "upscale": None},
}

# Dropdown choices, mirroring image_toolkit.py's argparse choices.
OP_CHOICES = ["convert", "clean", "both"]
WORK_ON_CHOICES = ["image", "canvas"]
FIT_MODE_CHOICES = ["pad", "fit", "crop_fill", "fill_height", "fill_width"]
MODE_CHOICES = ["safe", "auto", "aggressive"]

# Extensions the batch queue will list — matches SUPPORTED_EXTS in the toolkit.
QUEUE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp",
              ".gif", ".tif", ".tiff", ".heic", ".avif", ".jfif")
