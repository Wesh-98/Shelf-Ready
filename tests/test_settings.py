# -*- coding: utf-8 -*-
"""Tests for the tkinter-free GUI logic.

Run with:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shelfready_ui import settings

PY = "python.exe"
SCRIPT = "image_toolkit.py"

DEFAULTS = {
    "op": "both", "work_on": "image", "fit_mode": "pad", "mode": "auto",
    "size": "1500", "margin_pct": "0.015", "min_top_pad_px": "120",
    "vertical_bias": "0.58", "product_contrast": "1.05",
    "sharpen_radius": "1.3", "sharpen_percent": "140",
    "sharpen_threshold": "2", "dehalo_px": "2", "edge_feather": "1.0",
    "top_clean_pct": "0.08", "white_floor": "245", "neutrality_tol": "18",
    "target_fill": "0.84", "quality": "95",
    "dpi_value": "300", "shadow_alpha": "70",
}


def opts(**over):
    v = dict(DEFAULTS)
    v.update(over)
    return v


def pairs(args):
    """Flag -> value mapping from an argv list."""
    out, i = {}, 2  # skip interpreter + script
    while i < len(args):
        a = args[i]
        if a.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            out[a] = args[i + 1]; i += 2
        else:
            out[a] = True; i += 1
    return out


class TestValidate(unittest.TestCase):

    def test_defaults_are_valid(self):
        self.assertEqual(settings.validate(opts()), [])

    def test_non_numeric_reported_with_label(self):
        errs = settings.validate(opts(size="abc"))
        self.assertEqual(len(errs), 1)
        self.assertIn("Canvas px", errs[0])
        self.assertIn("whole number", errs[0])

    def test_float_field_rejects_letters(self):
        errs = settings.validate(opts(margin_pct="wide"))
        self.assertIn("Margin %", errs[0])
        self.assertIn("is not a number", errs[0])

    def test_out_of_range_reported(self):
        errs = settings.validate(opts(margin_pct="5"))
        self.assertEqual(len(errs), 1)
        self.assertIn("outside 0.0-1.0", errs[0])

    def test_empty_reported(self):
        errs = settings.validate(opts(quality=""))
        self.assertIn("cannot be empty", errs[0])

    def test_multiple_problems_all_reported(self):
        errs = settings.validate(opts(size="x", quality="", margin_pct="9"))
        self.assertEqual(len(errs), 3)

    def test_int_field_rejects_float_string(self):
        errs = settings.validate(opts(size="1500.5"))
        self.assertIn("Canvas px", errs[0])

    def test_boundaries_are_inclusive(self):
        self.assertEqual(settings.validate(opts(quality="1")), [])
        self.assertEqual(settings.validate(opts(quality="100")), [])
        self.assertEqual(len(settings.validate(opts(quality="101"))), 1)

    def test_dpi_only_checked_when_enabled(self):
        self.assertEqual(settings.validate(opts(dpi_value="-5")), [])
        errs = settings.validate(opts(set_dpi=True, dpi_value="-5"))
        self.assertIn("DPI Value", errs[0])

    def test_shadow_alpha_only_checked_when_enabled(self):
        self.assertEqual(settings.validate(opts(shadow_alpha="999")), [])
        errs = settings.validate(opts(add_shadow=True, shadow_alpha="999"))
        self.assertIn("Shdw Alpha", errs[0])


class TestBuildArgs(unittest.TestCase):

    def test_requires_an_input(self):
        with self.assertRaises(ValueError):
            settings.build_args(opts(), PY, SCRIPT)

    def test_value_flags_present(self):
        cmd = settings.build_args(opts(in_file="a.jpg"), PY, SCRIPT)
        p = pairs(cmd.args)
        self.assertEqual(p["--size"], "1500")
        self.assertEqual(p["--fit_mode"], "pad")
        self.assertEqual(p["--in"], "a.jpg")

    def test_bool_flags_omitted_when_false(self):
        cmd = settings.build_args(opts(in_file="a.jpg"), PY, SCRIPT)
        self.assertNotIn("--allow_upscale", cmd.args)

    def test_bool_flags_emitted_when_true(self):
        cmd = settings.build_args(
            opts(in_file="a.jpg", allow_upscale=True, auto_enhance=True), PY, SCRIPT)
        self.assertIn("--allow_upscale", cmd.args)
        self.assertIn("--auto_enhance", cmd.args)

    def test_blank_badge_text_suppresses_flag(self):
        cmd = settings.build_args(
            opts(in_file="a.jpg", qty_badge=True, qty_badge_text="   "), PY, SCRIPT)
        self.assertNotIn("--qty_badge", cmd.args)

    def test_badge_text_is_stripped(self):
        cmd = settings.build_args(
            opts(in_file="a.jpg", qty_badge=True, qty_badge_text="  20 OZ  "), PY, SCRIPT)
        self.assertEqual(pairs(cmd.args)["--qty_badge"], "20 OZ")

    def test_whitespace_rename_suppressed(self):
        cmd = settings.build_args(
            opts(in_file="a.jpg", out_prefix="   "), PY, SCRIPT)
        self.assertNotIn("--out_prefix", cmd.args)

    def test_blank_output_is_resolved_not_left_to_the_toolkit(self):
        """A blank Output field used to mean no --out, which made the toolkit
        derive the input's own path for a .jpg (destroying the source) and
        left the GUI with nothing to show as 'after'."""
        cmd = settings.build_args(
            opts(in_file=os.path.join("shots", "bottle.jpg")), PY, SCRIPT)
        self.assertTrue(cmd.out_path.endswith("bottle_processed.jpg"))
        self.assertEqual(pairs(cmd.args)["--out"], cmd.out_path)
        self.assertNotEqual(os.path.abspath(cmd.out_path),
                            os.path.abspath(os.path.join("shots", "bottle.jpg")))

    def test_resolved_output_keeps_the_input_directory(self):
        cmd = settings.build_args(
            opts(in_file=os.path.join("a", "b", "x.png")), PY, SCRIPT)
        self.assertEqual(os.path.dirname(cmd.out_path), os.path.join("a", "b"))

    def test_folder_output_is_resolved(self):
        cmd = settings.build_args(opts(in_dir="shots"), PY, SCRIPT)
        self.assertEqual(cmd.out_dir, os.path.join("shots", "_out"))
        self.assertEqual(pairs(cmd.args)["--out_dir"], cmd.out_dir)

    def test_explicit_folder_output_respected(self):
        cmd = settings.build_args(
            opts(in_dir="shots", out_dir="elsewhere"), PY, SCRIPT)
        self.assertEqual(cmd.out_dir, "elsewhere")

    def test_directory_out_file_gets_derived_name(self):
        here = os.path.dirname(os.path.abspath(__file__))
        cmd = settings.build_args(
            opts(in_file=os.path.join("x", "bottle.jpg"), out_file=here), PY, SCRIPT)
        self.assertTrue(cmd.out_path.endswith("bottle_processed.jpg"))
        self.assertEqual(pairs(cmd.args)["--out"], cmd.out_path)

    def test_zip_output_derived_when_blank(self):
        cmd = settings.build_args(opts(in_zip="batch.zip"), PY, SCRIPT)
        self.assertEqual(cmd.out_zip, "batch_processed.zip")
        self.assertEqual(pairs(cmd.args)["--out_zip"], "batch_processed.zip")

    def test_zip_output_respected_when_given(self):
        cmd = settings.build_args(
            opts(in_zip="batch.zip", out_zip="mine.zip"), PY, SCRIPT)
        self.assertEqual(cmd.out_zip, "mine.zip")

    def test_file_input_wins_over_dir_and_zip(self):
        cmd = settings.build_args(
            opts(in_file="a.jpg", in_dir="d", in_zip="z.zip"), PY, SCRIPT)
        self.assertIn("--in", cmd.args)
        self.assertNotIn("--in_dir", cmd.args)
        self.assertNotIn("--in_zip", cmd.args)

    def test_dir_input_wins_over_zip(self):
        cmd = settings.build_args(opts(in_dir="d", in_zip="z.zip"), PY, SCRIPT)
        self.assertIn("--in_dir", cmd.args)
        self.assertNotIn("--in_zip", cmd.args)

    def test_folder_mode_reports_no_out_path(self):
        cmd = settings.build_args(opts(in_dir="d"), PY, SCRIPT)
        self.assertEqual(cmd.out_path, "")
        self.assertEqual(cmd.out_zip, "")
        self.assertTrue(cmd.out_dir)


class TestOutputFor(unittest.TestCase):
    """Pairing a queued input with the file process_folder writes for it."""

    def test_plain_name(self):
        self.assertEqual(settings.output_for("in/bottle.jpg", "out"),
                         os.path.join("out", "bottle.jpg"))

    def test_extension_is_normalised_to_jpg(self):
        self.assertEqual(settings.output_for("in/shot.png", "out"),
                         os.path.join("out", "shot.jpg"))

    def test_prefix_and_suffix(self):
        self.assertEqual(settings.output_for("in/bottle.webp", "out", "SR_", "_web"),
                         os.path.join("out", "SR_bottle_web.jpg"))

    def test_matches_what_build_args_asks_the_toolkit_for(self):
        cmd = settings.build_args(
            opts(in_dir="shots", out_prefix="p_", out_suffix="_s"), PY, SCRIPT)
        paired = settings.output_for("shots/a.jpg", cmd.out_dir, "p_", "_s")
        self.assertEqual(paired, os.path.join("shots", "_out", "p_a_s.jpg"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
