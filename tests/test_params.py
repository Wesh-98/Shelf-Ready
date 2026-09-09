# -*- coding: utf-8 -*-
"""Tests for the web parameter surface.

Everything here is about untrusted input: what gets dropped, what gets
clamped, and what comes back as an error the browser can show.

Run with:  .venv\Scripts\python.exe -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shelfready_ui import presets, settings
from shelfready_web import params


class TestDefaults(unittest.TestCase):
    def test_defaults_cover_every_setting_the_builder_reads(self):
        """A missing default would silently emit an empty flag value."""
        for key in settings.VALUE_FLAGS + settings.BOOL_FLAGS:
            self.assertIn(key, params.DEFAULTS, f"{key} has no web default")

    def test_defaults_validate_untouched(self):
        """An untouched form must be processable without any input."""
        self.assertEqual([], settings.validate(params.DEFAULTS))

    def test_defaults_carry_no_paths(self):
        """Paths are the server's business; a client key would be a hole."""
        for key in ("in_file", "out_file", "in_dir", "out_dir", "in_zip", "out_zip"):
            self.assertNotIn(key, params.ALLOWED_KEYS)


class TestFromRequest(unittest.TestCase):
    def test_empty_payload_gives_defaults(self):
        self.assertEqual(params.DEFAULTS, params.from_request({}))
        self.assertEqual(params.DEFAULTS, params.from_request(None))

    def test_unknown_keys_are_dropped_not_forwarded(self):
        values = params.from_request({"in_file": "C:/Windows/win.ini", "bogus": 1})
        self.assertNotIn("in_file", values)
        self.assertNotIn("bogus", values)

    def test_known_values_come_through(self):
        values = params.from_request({"size": "2000", "op": "clean"})
        self.assertEqual("2000", values["size"])
        self.assertEqual("clean", values["op"])

    def test_booleans_accept_json_and_form_shapes(self):
        for raw in (True, "true", "on", "1", 1):
            self.assertIs(True, params.from_request({"add_shadow": raw})["add_shadow"])
        for raw in (False, "false", "off", "0", 0, ""):
            self.assertIs(False, params.from_request({"add_shadow": raw})["add_shadow"])

    def test_numbers_are_coerced_to_the_strings_the_builder_expects(self):
        values = params.from_request({"size": 2000, "target_fill": 0.9})
        self.assertEqual("2000", values["size"])
        self.assertEqual("0.9", values["target_fill"])

    def test_bad_choice_is_rejected(self):
        with self.assertRaises(params.ParamError) as caught:
            params.from_request({"fit_mode": "sideways"})
        self.assertIn("fit_mode", caught.exception.errors[0])

    def test_every_error_is_reported_at_once(self):
        with self.assertRaises(params.ParamError) as caught:
            params.from_request({"size": "abc", "quality": "999", "mode": "nope"})
        self.assertEqual(3, len(caught.exception.errors))


class TestWebLimits(unittest.TestCase):
    def test_desktop_legal_canvas_is_refused_on_the_web(self):
        """size=20000 passes settings.validate but is a ~1.2 GB array."""
        self.assertEqual([], settings.validate({**params.DEFAULTS, "size": "20000"}))
        with self.assertRaises(params.ParamError):
            params.from_request({"size": "20000"})

    def test_the_web_ceiling_itself_is_allowed(self):
        self.assertEqual("4000", params.from_request({"size": "4000"})["size"])

    def test_limits_only_narrow_never_widen(self):
        for key, (lo, hi) in params.WEB_LIMITS.items():
            desktop = [f for f in settings.NUMERIC_FIELDS if f[0] == key][0]
            self.assertGreaterEqual(lo, desktop[3], f"{key} lower bound widened")
            self.assertLessEqual(hi, desktop[4], f"{key} upper bound widened")

    def test_badge_text_is_capped(self):
        long_text = "X" * (params.MAX_BADGE_CHARS + 1)
        with self.assertRaises(params.ParamError):
            params.from_request({"qty_badge_text": long_text})


class TestFormConfig(unittest.TestCase):
    def test_config_reports_the_enforced_range_not_the_desktop_one(self):
        cfg = params.form_config()
        size = [f for f in cfg["numeric_fields"] if f["key"] == "size"][0]
        self.assertEqual(4000, size["max"])

    def test_config_serves_the_shared_preset_tables(self):
        cfg = params.form_config()
        self.assertEqual(presets.PLATFORM_PRESETS, cfg["platform_presets"])
        self.assertEqual(presets.FIT_MODE_CHOICES, cfg["choices"]["fit_mode"])

    def test_config_is_json_serializable(self):
        import json
        json.dumps(params.form_config())


if __name__ == "__main__":
    unittest.main()
