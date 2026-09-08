# -*- coding: utf-8 -*-
"""Theme palette invariants.

The GUI recolors live widgets through a {old_color: new_color} map keyed by
color value. That only works if a color value identifies its role
unambiguously — otherwise two roles collapse into one map entry and widgets
get recolored to whichever target was written last. These tests guard that
property; see the module docstring in shelfready_ui/theme.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shelfready_ui import theme


class TestThemeIntegrity(unittest.TestCase):

    def test_check_themes_reports_no_problems(self):
        self.assertEqual(theme.check_themes(), [])

    def test_every_theme_defines_every_color_key(self):
        for name, palette in theme.THEMES.items():
            for key in theme.COLOR_KEYS:
                self.assertIn(key, palette, f"{name} is missing {key}")

    def test_every_theme_has_a_display_name(self):
        for name in theme.THEMES:
            self.assertIn(name, theme.THEME_NAMES)

    def test_default_theme_exists(self):
        self.assertIn(theme.DEFAULT_THEME, theme.THEMES)

    def test_colors_are_hex_triplets(self):
        for name, palette in theme.THEMES.items():
            for key, value in palette.items():
                self.assertRegex(value, r"^#[0-9a-fA-F]{6}$",
                                 f"{name}.{key} = {value!r}")


class TestRecolorMap(unittest.TestCase):

    def test_map_is_unambiguous_in_both_directions(self):
        """No source color may need two different replacements."""
        for src in theme.THEMES:
            for dst in theme.THEMES:
                if src == dst:
                    continue
                seen = {}
                for key, value in theme.THEMES[src].items():
                    target = theme.THEMES[dst][key]
                    if value in seen:
                        self.assertEqual(
                            seen[value], target,
                            f"{src}->{dst}: {value} must map to one color, "
                            f"but {key} wants {target} and another role wants "
                            f"{seen[value]}")
                    seen[value] = target

    def test_text_roles_stay_distinguishable(self):
        """The exact regression: SLATE_MD, BLACK and WHITE all shared a value
        in the green theme, so dark panel text turned near-white in warm."""
        for name, palette in theme.THEMES.items():
            values = [palette["SLATE_MD"], palette["BLACK"], palette["WHITE"]]
            self.assertEqual(len(set(values)), 3,
                             f"{name}: SLATE_MD/BLACK/WHITE must be distinct")

    def test_surface_roles_stay_distinguishable(self):
        for name, palette in theme.THEMES.items():
            self.assertNotEqual(palette["FIELD_BG"], palette["LOG_BG"],
                                f"{name}: FIELD_BG and LOG_BG must differ")
            self.assertNotEqual(palette["GREY"], palette["LOG_DIV"],
                                f"{name}: GREY and LOG_DIV must differ")

    def test_round_trip_restores_every_color(self):
        for src in theme.THEMES:
            for dst in theme.THEMES:
                if src == dst:
                    continue
                out = theme.recolor_map(src, dst)
                back = theme.recolor_map(dst, src)
                for key, value in theme.THEMES[src].items():
                    moved = out.get(value, value)
                    self.assertEqual(back.get(moved, moved), value,
                                     f"{key} does not survive {src}->{dst}->{src}")

    def test_map_omits_unchanged_colors(self):
        out = theme.recolor_map("green", "warm")
        for value in out:
            self.assertNotEqual(value, out[value])


def _luminance(hex_color):
    parts = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class TestCheckboxIndicator(unittest.TestCase):
    """Tk fills the checkbox indicator with selectcolor in BOTH states and
    draws the checkmark in fg. A fill that matches fg makes the mark vanish,
    which is what made selected options unreadable in the warm theme."""

    MIN_MARK_CONTRAST = 3.0

    def test_normal_checkmark_is_legible_on_its_fill(self):
        for name, palette in theme.THEMES.items():
            ratio = _contrast(palette["SLATE_MD"], palette["CHECK_ON"])
            self.assertGreaterEqual(
                ratio, self.MIN_MARK_CONTRAST,
                f"{name}: checkmark on CHECK_ON has contrast {ratio:.2f}")

    def test_accent_checkmark_is_legible_on_its_fill(self):
        for name, palette in theme.THEMES.items():
            ratio = _contrast(palette["ACCENT"], palette["CHECK_ON_ACCENT"])
            self.assertGreaterEqual(
                ratio, self.MIN_MARK_CONTRAST,
                f"{name}: accent checkmark has contrast {ratio:.2f}")

    def test_accent_box_needs_its_own_fill(self):
        """The accent mark is ACCENT-coloured, so it cannot share CHECK_ON."""
        for name, palette in theme.THEMES.items():
            ratio = _contrast(palette["ACCENT"], palette["CHECK_ON"])
            if ratio >= self.MIN_MARK_CONTRAST:
                continue    # would be fine sharing, no separate role needed
            self.assertNotEqual(palette["CHECK_ON_ACCENT"], palette["CHECK_ON"],
                                f"{name}: accent box must not reuse CHECK_ON")

    def test_unchecked_is_lighter_than_checked(self):
        """Clear by default, darker once selected."""
        for name, palette in theme.THEMES.items():
            self.assertGreater(
                _luminance(palette["CHECK_OFF"]),
                _luminance(palette["CHECK_ON"]),
                f"{name}: CHECK_OFF should be the lighter of the two")
            self.assertGreater(
                _luminance(palette["CHECK_OFF"]),
                _luminance(palette["CHECK_ON_ACCENT"]),
                f"{name}: CHECK_OFF should be lighter than CHECK_ON_ACCENT")

    def test_states_are_distinguishable(self):
        for name, palette in theme.THEMES.items():
            self.assertNotEqual(palette["CHECK_OFF"], palette["CHECK_ON"],
                                f"{name}: on and off fills are identical")

    def test_old_fill_would_now_fail(self):
        """Regression guard: LOG_BG was the fill, and in warm it put the
        checkmark at 1.6:1 against its background."""
        warm = theme.THEMES["warm"]
        self.assertLess(_contrast(warm["SLATE_MD"], warm["LOG_BG"]),
                        self.MIN_MARK_CONTRAST)


class TestCheckThemesDetectsProblems(unittest.TestCase):
    """check_themes must actually catch the bug it exists to prevent."""

    def setUp(self):
        self.original = {k: dict(v) for k, v in theme.THEMES.items()}

    def tearDown(self):
        theme.THEMES.clear()
        theme.THEMES.update(self.original)

    def test_detects_an_ambiguous_collision(self):
        theme.THEMES["green"]["BLACK"] = theme.THEMES["green"]["SLATE_MD"]
        problems = theme.check_themes()
        self.assertTrue(problems)
        self.assertTrue(any("BLACK" in p or "SLATE_MD" in p for p in problems))

    def test_detects_a_missing_key(self):
        del theme.THEMES["warm"]["ACCENT"]
        self.assertTrue(theme.check_themes())

    def test_allows_a_benign_shared_color(self):
        """TEAL and ACCENT share a value in both themes — that is fine,
        because they map to the same target."""
        self.assertEqual(theme.THEMES["green"]["TEAL"],
                         theme.THEMES["green"]["ACCENT"])
        self.assertEqual(theme.check_themes(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
