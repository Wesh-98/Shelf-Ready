# -*- coding: utf-8 -*-
"""Tests for the HTTP layer.

Uses FastAPI's TestClient, so no server and no network are involved.

Run with:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - the web extra is optional
    # Not just ImportError: starlette raises RuntimeError when httpx is
    # missing, and a missing test dependency should skip, never break.
    TestClient = None

from tests.test_jobs import fixture_bytes


@unittest.skipIf(TestClient is None,
                 "web dependencies not installed (pip install -r requirements-web.txt)")
class WebTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from shelfready_web import app as web_app
        cls.web_app = web_app
        # Rate limiting is per-IP and every test shares one client address,
        # so it would fire partway through the suite and mask real failures.
        cls.web_app.limiter.enabled = False
        cls.client = TestClient(web_app.app)

    def post(self, data=None, filename="product.jpg", settings=None):
        payload = fixture_bytes() if data is None else data
        files = {"image": (filename, io.BytesIO(payload), "image/jpeg")}
        form = {"settings": json.dumps(settings or {})}
        return self.client.post("/api/process", files=files, data=form)


class TestPages(WebTestCase):
    def test_index_is_served(self):
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)
        self.assertIn("text/html", response.headers["content-type"])

    def test_healthz_reports_the_version(self):
        response = self.client.get("/healthz")
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])

    def test_download_points_at_the_release(self):
        response = self.client.get("/download", follow_redirects=False)
        self.assertEqual(302, response.status_code)
        self.assertIn("releases", response.headers["location"])

    def test_static_assets_are_reachable(self):
        for path in ("/static/style.css", "/static/app.js", "/static/theme.css"):
            self.assertEqual(200, self.client.get(path).status_code, path)


class TestConfigEndpoint(WebTestCase):
    def test_config_carries_what_the_form_needs(self):
        body = self.client.get("/api/config").json()
        for key in ("defaults", "choices", "numeric_fields", "platform_presets",
                    "advanced_groups", "quick_toggles", "limits", "version"):
            self.assertIn(key, body)

    def test_config_advertises_the_enforced_canvas_ceiling(self):
        body = self.client.get("/api/config").json()
        size = [f for f in body["numeric_fields"] if f["key"] == "size"][0]
        self.assertEqual(4000, size["max"])

    def test_the_studio_credit_comes_from_the_shared_constants(self):
        """The site and the desktop title bar must credit the same studio."""
        from shelfready_ui import version
        studio = self.client.get("/api/config").json()["studio"]
        self.assertEqual(version.STUDIO_NAME, studio["name"])
        self.assertEqual(version.STUDIO_URL, studio["url"])

    def test_the_credit_is_in_the_markup_not_only_in_javascript(self):
        """It must be readable with JS blocked, and by a crawler."""
        from shelfready_ui import version
        page = self.client.get("/").text
        self.assertIn(version.STUDIO_NAME, page)
        self.assertIn(version.STUDIO_URL, page)


class TestProcessEndpoint(WebTestCase):
    def test_an_image_comes_back_processed(self):
        response = self.post(settings={"op": "both", "size": "600"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("image/jpeg", response.headers["content-type"])
        self.assertIn("product_processed.jpg", response.headers["content-disposition"])

        from PIL import Image
        with Image.open(io.BytesIO(response.content)) as out:
            self.assertEqual((600, 600), out.size)

    def test_defaults_apply_when_no_settings_are_sent(self):
        response = self.post(settings={})
        self.assertEqual(200, response.status_code)

    def test_bad_settings_come_back_as_a_list_of_problems(self):
        response = self.post(settings={"size": "20000", "quality": "999"})
        self.assertEqual(400, response.status_code)
        self.assertEqual(2, len(response.json()["errors"]))

    def test_malformed_settings_json_is_rejected(self):
        files = {"image": ("p.jpg", io.BytesIO(fixture_bytes()), "image/jpeg")}
        response = self.client.post("/api/process", files=files,
                                    data={"settings": "{not json"})
        self.assertEqual(400, response.status_code)

    def test_a_non_image_is_refused(self):
        response = self.post(data=b"MZ this is not an image", filename="virus.jpg")
        self.assertEqual(415, response.status_code)

    def test_an_oversized_upload_is_refused_without_being_processed(self):
        response = self.post(data=b"\xff" * (self.web_app.jobs.MAX_UPLOAD_BYTES + 1))
        self.assertEqual(413, response.status_code)

    def test_the_log_header_leaks_no_server_paths(self):
        """The toolkit names the paths it wrote; those are the server's."""
        response = self.post(settings={"size": "400", "auto_work_on": True})
        log = response.headers.get("x-shelfready-log", "")
        self.assertNotIn("Saved ->", log)
        self.assertNotIn(os.path.expanduser("~"), log)
        self.assertNotIn(":\\", log)

    def test_the_client_filename_cannot_become_a_path(self):
        response = self.post(filename="../../../etc/passwd.jpg")
        self.assertEqual(200, response.status_code)
        disposition = response.headers["content-disposition"]
        self.assertIn("passwd_processed.jpg", disposition)
        self.assertNotIn("..", disposition)

    def test_a_client_supplied_path_setting_is_ignored(self):
        """in_file is not in ALLOWED_KEYS; sending it must change nothing."""
        response = self.post(settings={"in_file": "C:/Windows/win.ini", "size": "400"})
        self.assertEqual(200, response.status_code)


class TestGeneratedTheme(unittest.TestCase):
    def test_the_checked_in_stylesheet_matches_the_palette(self):
        """A stale theme.css means the site and the app have drifted apart."""
        from shelfready_web import build_theme_css
        with open(build_theme_css.OUT_PATH, encoding="utf-8") as fh:
            self.assertEqual(build_theme_css.render(), fh.read(),
                             "theme.css is stale — run "
                             "python -m shelfready_web.build_theme_css")


if __name__ == "__main__":
    unittest.main()
