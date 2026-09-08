# -*- coding: utf-8 -*-
"""Settings validation and command-line assembly.

Deliberately free of tkinter: everything here works on a plain dict of
setting values (all strings and bools), so it can be exercised without
building a window. The GUI snapshots its tk variables into that dict and
writes any resolved output paths back.
"""

import os
from typing import NamedTuple

# ── Numeric entry fields ──────────────────────────────────────────────────────
# (key, display label, cast, min, max) — validated before we hand anything to
# the CLI so a typo surfaces as a dialog instead of an argparse traceback.
NUMERIC_FIELDS = [
    ("size",                "Canvas px",   int,   16,   20000),
    ("margin_pct",          "Margin %",    float, 0.0,  1.0),
    ("min_top_pad_px",      "Top Pad px",  int,   0,    20000),
    ("vertical_bias",       "V.Bias",      float, 0.0,  1.0),
    ("product_contrast",    "Contrast",    float, 0.1,  5.0),
    ("sharpen_radius",      "Shp.Radius",  float, 0.0,  50.0),
    ("sharpen_percent",     "Shp.%",       int,   0,    1000),
    ("sharpen_threshold",   "Shp.Thr",     int,   0,    255),
    ("dehalo_px",           "Dehalo px",   float, 0.0,  50.0),
    ("edge_feather",        "EdgeFeath",   float, 0.0,  50.0),
    ("top_clean_pct",       "TopClean %",  float, 0.0,  1.0),
    ("white_floor",         "White Floor", int,   0,    255),
    ("neutrality_tol",      "Neutrality",  int,   0,    255),
    ("target_fill",         "Fill Ratio",  float, 0.05, 2.0),
    ("quality",             "Quality",     int,   1,    100),
]

# Numeric fields that only apply when their enabling checkbox is ticked.
CONDITIONAL_NUMERICS = [
    # (enable key, value key, display label, min, max)
    ("set_dpi",    "dpi_value",    "DPI Value",  1, 2400),
    ("add_shadow", "shadow_alpha", "Shdw Alpha", 0, 100),
]

# ── Flag tables ───────────────────────────────────────────────────────────────
# Settings that always emit "--flag <value>".
VALUE_FLAGS = [
    "op", "work_on", "fit_mode", "size", "margin_pct", "min_top_pad_px",
    "vertical_bias", "product_contrast", "sharpen_radius", "sharpen_percent",
    "sharpen_threshold", "dehalo_px", "edge_feather", "top_clean_pct",
    "white_floor", "neutrality_tol", "target_fill", "quality", "mode",
]

# Settings that emit a bare "--flag" when true.
BOOL_FLAGS = [
    "no_downscale", "no_bg_clean", "allow_upscale", "no_largest_scrub",
    "no_progressive", "no_optimize", "auto_work_on", "auto_enhance",
]


class Command(NamedTuple):
    """A prepared image_toolkit.py invocation.

    Output locations are always resolved here rather than left to the
    toolkit's own defaults, so the caller knows where results landed.
    """
    args: list       # full argv, including the interpreter and script
    out_path: str    # resolved single-file output, or "" when not applicable
    out_dir: str     # resolved folder output, or "" when not applicable
    out_zip: str     # resolved output zip, or "" when not applicable


def output_for(in_path, out_dir, out_prefix="", out_suffix=""):
    """Where process_folder will write the result for one queued input."""
    stem = os.path.splitext(os.path.basename(in_path))[0]
    return os.path.join(out_dir, f"{out_prefix}{stem}{out_suffix}.jpg")


def validate(values):
    """Return a list of human-readable problems with the numeric settings."""
    errors = []
    for key, label, cast, lo, hi in NUMERIC_FIELDS:
        raw = str(values.get(key, "")).strip()
        if not raw:
            errors.append(f"{label}: cannot be empty")
            continue
        try:
            val = cast(raw)
        except ValueError:
            kind = "a whole number" if cast is int else "a number"
            errors.append(f"{label}: '{raw}' is not {kind}")
            continue
        if not (lo <= val <= hi):
            errors.append(f"{label}: {val} is outside {lo}-{hi}")

    for enable_key, value_key, label, lo, hi in CONDITIONAL_NUMERICS:
        if not values.get(enable_key):
            continue
        raw = str(values.get(value_key, "")).strip()
        if not raw.isdigit() or not (lo <= int(raw) <= hi):
            errors.append(f"{label}: '{raw}' must be a whole number {lo}-{hi}")

    return errors


def build_args(values, python_exe, script):
    """Assemble the image_toolkit.py argv from a settings dict.

    Returns a Command. Raises ValueError if no input was selected.
    Output paths that the GUI left blank are resolved here and handed
    back on the Command so the caller can echo them into its fields.
    """
    args = [python_exe, script]

    for key in VALUE_FLAGS:
        args += [f"--{key}", str(values.get(key, ""))]

    for key in BOOL_FLAGS:
        if values.get(key):
            args.append(f"--{key}")

    if values.get("set_dpi"):
        args += ["--set_dpi", str(values.get("dpi_value", ""))]
    if values.get("add_shadow"):
        args += ["--add_shadow", "--shadow_alpha", str(values.get("shadow_alpha", ""))]
    if values.get("qty_badge") and str(values.get("qty_badge_text", "")).strip():
        args += ["--qty_badge", str(values["qty_badge_text"]).strip()]

    for key, flag in (("out_prefix", "--out_prefix"), ("out_suffix", "--out_suffix")):
        val = str(values.get(key, "")).strip()
        if val:
            args += [flag, val]

    in_file = str(values.get("in_file", "")).strip()
    in_dir = str(values.get("in_dir", "")).strip()
    in_zip = str(values.get("in_zip", "")).strip()

    out_path = ""
    out_dir = ""
    out_zip = ""

    if in_file:
        args += ["--in", in_file]
        ov = str(values.get("out_file", "")).strip()
        # A directory here means "put it in there under a derived name".
        if ov and os.path.isdir(ov):
            stem = os.path.splitext(os.path.basename(in_file))[0]
            ov = os.path.join(ov, f"{stem}_processed.jpg")
        elif not ov:
            # Always resolve an explicit output. Leaving it to the toolkit
            # would derive the input's own path for a .jpg — destroying the
            # source — and the GUI would not know where the result landed,
            # so the before/after preview would have nothing to show.
            head, tail = os.path.split(in_file)
            stem = os.path.splitext(tail)[0]
            ov = os.path.join(head, f"{stem}_processed.jpg")
        args += ["--out", ov]
        out_path = ov
    elif in_dir:
        args += ["--in_dir", in_dir]
        # Resolve the default here too, so the caller knows where results
        # landed and can pair each queued input with its output.
        od = str(values.get("out_dir", "")).strip()
        if not od:
            od = os.path.join(in_dir, "_out")
        args += ["--out_dir", od]
        out_dir = od
    elif in_zip:
        args += ["--in_zip", in_zip]
        # Always resolve the output ZIP — default next to the input if unset.
        oz = str(values.get("out_zip", "")).strip()
        if not oz:
            oz = os.path.splitext(in_zip)[0] + "_processed.zip"
        args += ["--out_zip", oz]
        out_zip = oz
    else:
        raise ValueError("Select an input (file / folder / zip).")

    return Command(args, out_path, out_dir, out_zip)
