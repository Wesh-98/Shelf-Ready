# -*- coding: utf-8 -*-
"""Asset resolution.

Path-level checks only — loading a PhotoImage needs a Tk root, so those
paths are exercised by the GUI smoke test rather than here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shelfready_ui import assets, theme


class TestAssetLayout(unittest.TestCase):

    def test_project_dir_is_the_repo_root(self):
        self.assertTrue(os.path.exists(
            os.path.join(assets.PROJECT_DIR, "image_toolkit.py")))
        self.assertTrue(os.path.exists(
            os.path.join(assets.PROJECT_DIR, "ShelfReady_Unified_GUI.py")))

    def test_icons_dir_exists(self):
        self.assertTrue(os.path.isdir(assets.ICONS_DIR))

    def test_no_runtime_asset_is_missing(self):
        self.assertEqual(assets.missing(), [])

    def test_every_theme_has_a_mark(self):
        for name in theme.THEMES:
            self.assertIn(name, assets.THEME_MARKS,
                          f"theme '{name}' has no title-bar mark")
            self.assertTrue(os.path.exists(assets.THEME_MARKS[name]))

    def test_paths_are_absolute(self):
        for path in [assets.APP_ICO, assets.MASTER_MARK,
                     assets.TRANSPARENT_MARK] + list(assets.THEME_MARKS.values()):
            self.assertTrue(os.path.isabs(path), path)

    def test_design_reference_is_not_a_runtime_asset(self):
        """Reference art lives outside icons/ so it is never loaded."""
        design = os.path.join(assets.ASSETS_DIR, "design")
        if os.path.isdir(design):
            for name in os.listdir(design):
                self.assertNotIn(os.path.join(design, name),
                                 assets.missing())
                self.assertFalse(
                    os.path.exists(os.path.join(assets.ICONS_DIR, name)),
                    f"{name} should live in design/, not icons/")


class TestMarkPath(unittest.TestCase):

    def test_known_theme_returns_its_own_mark(self):
        self.assertEqual(assets.mark_path("green"), assets.THEME_MARKS["green"])
        self.assertEqual(assets.mark_path("warm"), assets.THEME_MARKS["warm"])

    def test_unknown_theme_falls_back_to_master(self):
        self.assertEqual(assets.mark_path("no-such-theme"), assets.MASTER_MARK)

    def test_none_falls_back_to_master(self):
        self.assertEqual(assets.mark_path(None), assets.MASTER_MARK)

    def test_missing_theme_art_falls_back_rather_than_raising(self):
        original = assets.THEME_MARKS["green"]
        assets.THEME_MARKS["green"] = os.path.join(assets.ICONS_DIR, "gone.png")
        try:
            self.assertEqual(assets.mark_path("green"), assets.MASTER_MARK)
        finally:
            assets.THEME_MARKS["green"] = original

    def test_missing_master_yields_none(self):
        original_marks = dict(assets.THEME_MARKS)
        original_master = assets.MASTER_MARK
        assets.THEME_MARKS.clear()
        assets.MASTER_MARK = os.path.join(assets.ICONS_DIR, "gone.png")
        try:
            self.assertIsNone(assets.mark_path("green"))
        finally:
            assets.MASTER_MARK = original_master
            assets.THEME_MARKS.update(original_marks)


if __name__ == "__main__":
    unittest.main(verbosity=2)
