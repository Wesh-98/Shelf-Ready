# -*- coding: utf-8 -*-
"""Color palettes and fonts.

Pure data. The GUI binds these into module-level names it can rebind on a
theme switch, and walks the live widget tree to recolor what's already on
screen — that machinery stays in the GUI because it needs the root window.

IMPORTANT — why some colors differ by a single digit:

The GUI recolors a live widget by looking up its *current* color in a
{old_value: new_value} map. That lookup is keyed by color value, so if two
roles share one value in the source theme, they collapse into a single map
entry and the last one written wins — every widget using either role gets
whichever target color came last. SLATE_MD, BLACK and WHITE were all
"#eafff2" in green, so dark-on-light text turned near-white in warm.

Roles that must recolor differently therefore need distinct values. Where
two roles genuinely want to look identical, they differ by 1/255 in one
channel: invisible on screen, unambiguous to the map. check_themes() below
enforces the rule, and tests/test_theme.py runs it.
"""

THEMES = {
    "green": {
        "NAVY": "#17251c", "NAVY_DARK": "#081310", "NAVY_LT": "#1f3a2a",
        "SLATE": "#0d140f", "SLATE_MD": "#eafff2",
        "GREY": "#3a6b4d", "GREY_LT": "#24402f",
        "BG": "#0a0f0d", "PANEL": "#101915",
        # BLACK/WHITE read as SLATE_MD on this dark theme; nudged apart so
        # they can map to genuinely different warm colors.
        "BLACK": "#eafff1", "WHITE": "#eafff3",
        "FIELD_BG": "#08110d", "LOG_BG": "#08110e", "LOG_FG": "#8fcaa8",
        # Text roles that need to invert with the surface they sit on:
        # ON_BG rides the window-background bar, MUTED is hint text on PANEL.
        "ON_BG": "#eafff4", "MUTED": "#6f9e82",
        # Checkbox indicator. selectcolor fills the box in BOTH states, so
        # the fill is swapped on toggle: clear when off, filled when on.
        # The checkmark is drawn in the widget's fg, which is SLATE_MD for
        # normal boxes and ACCENT for the accent one - hence two ON fills,
        # each chosen to keep its own mark legible.
        "CHECK_OFF": "#eafff5", "CHECK_ON": "#1f3a2b",
        "CHECK_ON_ACCENT": "#081311",
        "TEAL": "#39ff88", "ACCENT": "#39ff88",
        "ACCENT_HOVER": "#2fe578", "TEXT_ON_ACCENT": "#062615",
        "LOG_CMD": "#5cd9a0", "LOG_DIV": "#3a6b4e",
    },
    "warm": {
        "NAVY": "#3a2e26", "NAVY_DARK": "#1c140e", "NAVY_LT": "#4a3b30",
        "SLATE": "#2f251d", "SLATE_MD": "#4a3626",
        "GREY": "#d9c7a8", "GREY_LT": "#ecdfc9",
        "BG": "#2b211a", "PANEL": "#ffffff",
        "BLACK": "#2c2118", "WHITE": "#f5ead9",
        # FIELD_BG matches PANEL visually; LOG_BG matches NAVY_DARK.
        "FIELD_BG": "#fffffe", "LOG_BG": "#1c140f", "LOG_FG": "#c9a06a",
        "ON_BG": "#f5eada", "MUTED": "#8a7358",
        "CHECK_OFF": "#fffffd", "CHECK_ON": "#d99a40",
        "CHECK_ON_ACCENT": "#3a2e27",
        "TEAL": "#d99a3f", "ACCENT": "#d99a3f",
        "ACCENT_HOVER": "#c78a34", "TEXT_ON_ACCENT": "#2c1a04",
        "LOG_CMD": "#c78a35", "LOG_DIV": "#5c4530",
    },
}

# Shown in the theme menu.
THEME_NAMES = {
    "green": "Terminal",
    "warm": "Warm",
}

DEFAULT_THEME = "green"

# Color names every widget-creation call site expects to find.
COLOR_KEYS = (
    "NAVY", "NAVY_DARK", "NAVY_LT", "SLATE", "SLATE_MD", "GREY", "GREY_LT",
    "BG", "PANEL", "BLACK", "WHITE", "FIELD_BG", "LOG_BG", "LOG_FG", "TEAL",
    "ACCENT", "ACCENT_HOVER", "TEXT_ON_ACCENT", "ON_BG", "MUTED",
    "CHECK_OFF", "CHECK_ON", "CHECK_ON_ACCENT",
)

F_HEAD = ("Arial", 13, "bold")
F_SEC  = ("Arial",  9, "bold")
F_LBL  = ("Arial",  8)
F_TINY = ("Arial",  7)
F_ENT  = ("Arial",  9)
F_RUN  = ("Arial", 12, "bold")
F_MONO = ("Courier", 8)


def recolor_map(src, dst):
    """{current color: replacement} for switching theme src -> dst."""
    old, new = THEMES[src], THEMES[dst]
    return {old[k]: new[k] for k in old if old[k] != new[k]}


def check_themes():
    """Return a list of problems that would make a theme switch misbehave.

    Two roles may share a color only if they also share it in every other
    theme — otherwise the recolor map cannot tell them apart. Also verifies
    every theme defines the full set of keys.
    """
    problems = []
    names = list(THEMES)

    reference = set(THEMES[DEFAULT_THEME])
    for name in names:
        missing = reference - set(THEMES[name])
        extra = set(THEMES[name]) - reference
        if missing:
            problems.append(f"theme '{name}' is missing keys: {sorted(missing)}")
        if extra:
            problems.append(f"theme '{name}' has unexpected keys: {sorted(extra)}")
        for key in COLOR_KEYS:
            if key not in THEMES[name]:
                problems.append(f"theme '{name}' is missing required color '{key}'")

    for src in names:
        for dst in names:
            if src == dst:
                continue
            targets = {}
            for key, value in THEMES[src].items():
                if key not in THEMES[dst]:
                    continue
                mapped = THEMES[dst][key]
                if value in targets and targets[value][1] != mapped:
                    other = targets[value][0]
                    problems.append(
                        f"{src} -> {dst}: '{key}' and '{other}' share "
                        f"{value} but map to {mapped} and {targets[value][1]}; "
                        f"one of them will be recolored wrongly")
                targets.setdefault(value, (key, mapped))

    return problems
