# -*- coding: utf-8 -*-
"""Turning an untrusted request payload into a settings dict.

The desktop GUI can trust its own widgets: a tk entry bound to a numeric
field only ever holds what the user typed into that box, and the worst case
is a dialog. A public endpoint has no such guarantee, so everything a client
sends is treated as hostile until it has been through from_request().

Defaults and bounds are NOT restated here. They come from
shelfready_ui.settings and shelfready_ui.presets, the same tables the GUI
builds its dropdowns and its Advanced panel from, so the two front ends can
never drift apart. What this module adds on top is a whitelist (unknown keys
are dropped rather than forwarded) and WEB_LIMITS, which tightens the bounds
that are safe on a desktop but not on a shared server.
"""

from shelfready_ui import presets, settings

# ── Defaults ──────────────────────────────────────────────────────────────────
# Mirrors the tk variable initializers in ShelfReady_Unified_GUI.py, so an
# untouched web form and an untouched desktop window process alike.
# Values are strings because that is what settings.validate/build_args expect
# from the GUI's StringVars.
DEFAULTS = {
    # Dropdowns
    "op": "both",
    "work_on": "image",
    "fit_mode": "pad",
    "mode": "auto",
    # Sizing & fit
    "size": "1500",
    "margin_pct": "0.015",
    "min_top_pad_px": "120",
    "vertical_bias": "0.58",
    "target_fill": "0.84",
    # Sharpening
    "sharpen_radius": "1.3",
    "sharpen_percent": "140",
    "sharpen_threshold": "2",
    "dehalo_px": "2",
    "edge_feather": "1.0",
    # Color & cleanup
    "product_contrast": "1.05",
    "top_clean_pct": "0.08",
    "white_floor": "245",
    "neutrality_tol": "18",
    # Output
    "quality": "95",
    # Quick toggles
    "allow_upscale": False,
    "auto_work_on": False,
    "auto_enhance": False,
    # Rare flags
    "no_downscale": False,
    "no_bg_clean": False,
    "no_largest_scrub": False,
    "no_progressive": False,
    "no_optimize": False,
    # Paired flag + value
    "set_dpi": False,
    "dpi_value": "300",
    "add_shadow": False,
    "shadow_alpha": "70",
    "qty_badge": False,
    "qty_badge_text": "",
}

# Keys a client may send. Input and output paths are deliberately absent:
# the server decides where files live, and a client-supplied path is exactly
# the traversal bug this whitelist exists to prevent.
ALLOWED_KEYS = frozenset(DEFAULTS)

# Free-text that gets rendered into the image. Long strings would be drawn
# off-canvas anyway; the cap keeps the font measuring bounded.
MAX_BADGE_CHARS = 24

# ── Web-only bounds ───────────────────────────────────────────────────────────
# settings.NUMERIC_FIELDS allows what makes sense with your own CPU and your
# own RAM. On a shared server the same values are a denial-of-service knob:
# size=20000 alone is a 20000x20000x3 working array, roughly 1.2 GB, before
# any of the intermediate masks. These override the ceiling for web traffic.
# (key -> (lo, hi)); anything not listed keeps its NUMERIC_FIELDS range.
WEB_LIMITS = {
    "size": (16, 4000),
    "sharpen_percent": (0, 500),
    "sharpen_radius": (0.0, 20.0),
    "dehalo_px": (0.0, 20.0),
    "edge_feather": (0.0, 20.0),
}

# Valid choices per dropdown, straight from the tables the GUI uses.
CHOICES = {
    "op": presets.OP_CHOICES,
    "work_on": presets.WORK_ON_CHOICES,
    "fit_mode": presets.FIT_MODE_CHOICES,
    "mode": presets.MODE_CHOICES,
}

# ── Form layout ───────────────────────────────────────────────────────────────
# Which control goes where. Served to the browser so the page's structure is
# decided in Python — the same decision the desktop app makes in its
# "Advanced settings" panel — instead of being restated in JavaScript.
DROPDOWNS = [
    ("op", "Operation",
     "convert = re-encode only · clean = background removal · both = full pipeline"),
    ("work_on", "Work On",
     "Apply settings to the product image itself, or to the full canvas."),
    ("fit_mode", "Fit Mode",
     "How the product is scaled onto the canvas (padding, cropping, fill)."),
    ("mode", "Mode",
     "How cautious the automatic cleanup is: safe < auto < aggressive."),
]

# The handful people actually flip per-run.
QUICK_TOGGLES = [
    ("allow_upscale", "Allow Upscale",
     "Let small source images be scaled up to hit the target canvas."),
    ("auto_work_on", "Auto Work Mode",
     "Automatically choose image vs. canvas mode per file."),
    ("auto_enhance", "Auto Enhance",
     "Tune sharpen/contrast per image instead of using fixed values."),
]

ADVANCED_GROUPS = [
    ("Sizing & Fit", ["margin_pct", "min_top_pad_px", "vertical_bias", "target_fill"]),
    ("Sharpening", ["sharpen_radius", "sharpen_percent", "sharpen_threshold",
                    "dehalo_px", "edge_feather"]),
    ("Color & Cleanup", ["product_contrast", "top_clean_pct", "white_floor",
                         "neutrality_tol"]),
]

RARE_FLAGS = [
    ("no_downscale", "No Downscale"),
    ("no_bg_clean", "Skip BG Clean"),
    ("no_largest_scrub", "No Largest Scrub"),
    ("no_progressive", "No Progressive"),
    ("no_optimize", "No Optimize"),
]

# Hover help, keyed by setting rather than by display label so a renamed
# label cannot orphan its tip.
TIPS = {
    "size": "Width and height of the square output canvas, in pixels.",
    "quality": "JPEG quality of the saved file. 95 is a safe default.",
    "margin_pct": "Empty space kept around the product, as a fraction of canvas size.",
    "min_top_pad_px": "Minimum pixels of empty space above the product.",
    "vertical_bias": "Where the product sits vertically — higher pushes it up.",
    "target_fill": "How much of the canvas the product should fill.",
    "product_contrast": "Contrast multiplier applied to the product.",
    "top_clean_pct": "Fraction of the top edge scrubbed of stray pixels.",
    "white_floor": "Minimum brightness treated as pure background white.",
    "neutrality_tol": "Color tolerance for what still counts as neutral background.",
    "sharpen_radius": "Unsharp-mask radius — larger affects a wider band around edges.",
    "sharpen_percent": "Strength of the sharpening effect.",
    "sharpen_threshold": "Minimum contrast difference before sharpening kicks in.",
    "dehalo_px": "Cleans up sharpening halos near edges.",
    "edge_feather": "Softens the cutout edge around the product.",
}


_BOOL_KEYS = frozenset(k for k, v in DEFAULTS.items() if isinstance(v, bool))
_NUMERIC = {k: (label, cast, lo, hi) for k, label, cast, lo, hi in settings.NUMERIC_FIELDS}


class ParamError(ValueError):
    """Bad client input. Carries every problem, not just the first.

    The caller turns `.errors` into a 400 body so a user fixing a form sees
    all of it at once, the way the GUI's validation dialog does.
    """

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def effective_range(key):
    """The (lo, hi) actually enforced for `key` — WEB_LIMITS narrows only."""
    label, cast, lo, hi = _NUMERIC[key]
    wlo, whi = WEB_LIMITS.get(key, (lo, hi))
    return max(lo, wlo), min(hi, whi)


def _as_bool(value):
    """Accept the several shapes JSON and form encodings give a checkbox."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def from_request(payload):
    """Merge a client payload over DEFAULTS and validate the result.

    Returns a settings dict shaped exactly like the GUI's collect_settings()
    output, minus the input/output paths — jobs.py fills those in once it
    knows the temp workspace. Raises ParamError listing every problem.
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ParamError(["settings must be a JSON object"])

    values = dict(DEFAULTS)
    errors = []

    for key, raw in payload.items():
        if key not in ALLOWED_KEYS:
            continue  # Silently dropped: an old client sending a dead key
            # should still process, not fail.
        if key in _BOOL_KEYS:
            values[key] = _as_bool(raw)
        elif key in CHOICES:
            val = str(raw).strip()
            if val not in CHOICES[key]:
                errors.append(f"{key}: '{val}' is not one of {', '.join(CHOICES[key])}")
            else:
                values[key] = val
        else:
            values[key] = str(raw).strip()

    badge = values["qty_badge_text"]
    if len(badge) > MAX_BADGE_CHARS:
        errors.append(f"Badge text: at most {MAX_BADGE_CHARS} characters")

    # Range-check against the web ceilings before handing the dict to
    # settings.validate, which would happily pass a desktop-legal size=20000.
    for key, (lo, hi) in WEB_LIMITS.items():
        raw = str(values.get(key, "")).strip()
        cast = _NUMERIC[key][1]
        try:
            val = cast(raw)
        except ValueError:
            continue  # settings.validate reports the type error itself.
        elo, ehi = effective_range(key)
        if not (elo <= val <= ehi):
            errors.append(f"{_NUMERIC[key][0]}: {val} is outside {elo}-{ehi}")

    # Everything else — types, empty fields, the untightened ranges, and the
    # conditional DPI/shadow numerics — is the GUI's own validator.
    errors.extend(settings.validate(values))

    if errors:
        raise ParamError(errors)
    return values


def form_config():
    """The tables the browser needs to build the form.

    Served rather than duplicated in JavaScript so the page's dropdowns,
    presets and field limits stay bound to the Python source of truth.
    """
    fields = []
    for key, label, cast, lo, hi in settings.NUMERIC_FIELDS:
        elo, ehi = effective_range(key)
        fields.append({
            "key": key,
            "label": label,
            "type": "int" if cast is int else "float",
            "min": elo,
            "max": ehi,
        })
    return {
        "defaults": DEFAULTS,
        "choices": CHOICES,
        "numeric_fields": fields,
        "platform_presets": presets.PLATFORM_PRESETS,
        "fit_mode_snaps": presets.FIT_MODE_SNAPS,
        "max_badge_chars": MAX_BADGE_CHARS,
        "dropdowns": [{"key": k, "label": lbl, "tip": tip} for k, lbl, tip in DROPDOWNS],
        "quick_toggles": [{"key": k, "label": lbl, "tip": tip}
                          for k, lbl, tip in QUICK_TOGGLES],
        "advanced_groups": [{"title": t, "keys": keys} for t, keys in ADVANCED_GROUPS],
        "rare_flags": [{"key": k, "label": lbl} for k, lbl in RARE_FLAGS],
        "tips": TIPS,
    }
