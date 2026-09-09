# -*- coding: utf-8 -*-
"""Tests for the web job path.

Covers the two things that only matter once strangers can upload: that a
hostile file is refused before it reaches the pipeline, and that nothing a
client sends reaches the filesystem as a path.

The fixture is generated rather than committed — the same synthetic product
shape .github/workflows/tests.yml builds, so no photography is in the repo.

Run with:  .venv\Scripts\python.exe -m unittest discover -s tests -v
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from shelfready_web import jobs, params


def fixture_bytes(size=(800, 800), fmt="JPEG"):
    """A synthetic product photo: shape on a flat colored background."""
    im = Image.new("RGB", size, (40, 90, 200))
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    w, h = size
    d.rectangle([w * 0.31, h * 0.25, w * 0.69, h * 0.75], fill=(220, 60, 50))
    d.ellipse([w * 0.37, h * 0.31, w * 0.63, h * 0.5], fill=(250, 230, 40))
    buf = io.BytesIO()
    im.save(buf, format=fmt, quality=95)
    return buf.getvalue()


class TestInspectUpload(unittest.TestCase):
    def test_a_real_image_is_accepted(self):
        self.assertEqual(".jpg", jobs.inspect_upload(fixture_bytes()))
        self.assertEqual(".png", jobs.inspect_upload(fixture_bytes(fmt="PNG")))

    def test_empty_upload_is_refused(self):
        with self.assertRaises(jobs.UploadError):
            jobs.inspect_upload(b"")

    def test_a_non_image_is_refused_however_it_is_named(self):
        with self.assertRaises(jobs.UploadError):
            jobs.inspect_upload(b"MZ\x90\x00 not an image, whatever the name says")

    def test_oversized_upload_is_refused_before_decoding(self):
        with self.assertRaises(jobs.UploadError) as caught:
            jobs.inspect_upload(b"\xff" * (jobs.MAX_UPLOAD_BYTES + 1))
        self.assertIn("MB", str(caught.exception))

    def test_a_decompression_bomb_is_refused(self):
        """A small file that claims an enormous canvas never gets decoded."""
        bomb = Image.new("L", (1, 1))
        buf = io.BytesIO()
        bomb.save(buf, format="PNG")
        payload = buf.getvalue()

        original = jobs.MAX_INPUT_PIXELS
        try:
            jobs.MAX_INPUT_PIXELS = 0  # Everything is now "too many pixels".
            with self.assertRaises(jobs.UploadError) as caught:
                jobs.inspect_upload(payload)
            self.assertIn("megapixel", str(caught.exception))
        finally:
            jobs.MAX_INPUT_PIXELS = original


class TestDownloadName(unittest.TestCase):
    def test_traversal_in_the_client_name_cannot_escape(self):
        name = jobs.download_name("../../../Windows/System32/config")
        self.assertEqual("config_processed.jpg", name)
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertNotIn("..", name)

    def test_a_normal_name_stays_recognizable(self):
        self.assertEqual("hero-shot_1_processed.jpg",
                         jobs.download_name("hero-shot_1.png"))

    def test_a_nameless_or_hostile_upload_still_gets_a_name(self):
        for raw in ("", None, "...", "///"):
            self.assertEqual("shelfready_processed.jpg", jobs.download_name(raw))


class TestWorkspace(unittest.TestCase):
    def test_the_directory_is_removed_even_when_the_job_raises(self):
        seen = None
        with self.assertRaises(RuntimeError):
            with jobs.workspace() as work_dir:
                seen = work_dir
                open(os.path.join(work_dir, "leftover.jpg"), "wb").close()
                raise RuntimeError("boom")
        self.assertFalse(os.path.exists(seen))


class TestScrubLog(unittest.TestCase):
    """The toolkit prints for a desktop user; the web must not repeat it.

    Its "Saved ->" line names a server path that carries the account name
    and the temp layout — nothing a browser needs, and something an attacker
    would like.
    """

    def test_server_paths_never_reach_the_client(self):
        work_dir = os.path.join("C:" + os.sep + "Users", "someone", "sr-abc")
        log = ("AUTO_DETECT: work_on changed from 'image' to 'canvas'\n"
               + "Saved -> " + os.path.join(work_dir, "deadbeef_out.jpg"))
        scrubbed = jobs.scrub_log(log, work_dir)
        self.assertIn("AUTO_DETECT", scrubbed)
        self.assertNotIn("someone", scrubbed)
        self.assertNotIn("Saved ->", scrubbed)

    def test_diagnostics_survive(self):
        log = "QUALITY_REPORT: blur=0.42, color=0.90, overall=71/100"
        self.assertEqual(log, jobs.scrub_log(log, os.path.join("tmp", "x")))


class TestRunSingle(unittest.TestCase):
    def test_an_upload_is_processed_to_a_square_white_canvas(self):
        values = params.from_request({"op": "both", "size": "600"})
        with jobs.workspace() as work_dir:
            out_path, log, name = jobs.run_single(
                work_dir, fixture_bytes(), "product.jpg", values)

            self.assertTrue(os.path.exists(out_path))
            self.assertEqual("product_processed.jpg", name)
            with Image.open(out_path) as out:
                self.assertEqual((600, 600), out.size)
                self.assertEqual("JPEG", out.format)
                # The blue background must be gone from the corners.
                self.assertEqual((255, 255, 255), out.convert("RGB").getpixel((2, 2)))
            self.assertNotIn(work_dir, log)

    def test_the_client_filename_never_becomes_a_path(self):
        values = params.from_request({"size": "400"})
        with jobs.workspace() as work_dir:
            out_path, _, _ = jobs.run_single(
                work_dir, fixture_bytes(), "../../escape.jpg", values)
            self.assertEqual(os.path.realpath(work_dir),
                             os.path.dirname(os.path.realpath(out_path)))

    def test_settings_reach_the_pipeline(self):
        """A knob the client set must reach image_toolkit, not just validate.

        Quality is the clearest probe: same input, same size, and the only
        difference between the two runs is the flag under test.
        """
        sizes = {}
        for quality in ("20", "95"):
            values = params.from_request({"op": "both", "size": "600",
                                          "quality": quality})
            with jobs.workspace() as work_dir:
                out_path, _, _ = jobs.run_single(
                    work_dir, fixture_bytes(), "p.jpg", values)
                sizes[quality] = os.path.getsize(out_path)
        self.assertLess(sizes["20"], sizes["95"])


if __name__ == "__main__":
    unittest.main()
