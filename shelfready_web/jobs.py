# -*- coding: utf-8 -*-
"""Running one upload through the toolkit, safely and without a trace.

Free of FastAPI so the whole job path can be tested without a server.

Three things separate this from the GUI's run path:

* The input is bytes from a stranger, not a file the user picked. It is
  sniffed and bounded before anything expensive touches it.
* Nothing persists. Every job gets a private temp directory that is removed
  when the response has been sent, so one user's photo can never surface in
  another user's request.
* The work is CPU-bound and the server is shared, so jobs are metered by a
  semaphore instead of running as fast as requests arrive.

The batch seam: run_single() is deliberately thin over _process_one(), and
the workspace and the semaphore are already per-job rather than per-file.
A run_batch() that loops _process_one() and zips the results slots in beside
it without disturbing any of this.
"""

import asyncio
import io
import os
import re
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager, contextmanager

from PIL import Image

from shelfready_ui import runner, settings

# Importing runner has already imported image_toolkit, which registers the
# HEIF/AVIF openers. Reading SUPPORTED_EXTS from it keeps the formats the web
# advertises identical to the ones the toolkit actually accepts.
import image_toolkit

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# A 50 MP ceiling comfortably clears a 8000x6000 camera file while stopping
# the classic decompression bomb: a few-KB PNG that expands to gigabytes.
MAX_INPUT_PIXELS = 50_000_000

# Pillow's own bomb guard. Its default (~178 MP) only warns; ours refuses,
# and refuses well below the point where the process would be in trouble.
Image.MAX_IMAGE_PIXELS = MAX_INPUT_PIXELS

# Concurrent jobs. The pipeline is CPU-bound and single-threaded per image,
# so more in flight than cores buys nothing and costs memory.
CONCURRENCY = max(1, min(os.cpu_count() or 1, 4))

# How long one image may take before it is abandoned. Generous for a 4000px
# canvas, short enough that a wedged job frees its slot.
JOB_TIMEOUT_SECONDS = 120

_slots = asyncio.Semaphore(CONCURRENCY)

_SAFE_STEM = re.compile(r"[^A-Za-z0-9._-]+")


class UploadError(ValueError):
    """The upload is not something we will process.

    Carries the status the HTTP layer should use, so the distinction between
    "too big" (413), "wrong kind of file" (415) and "malformed" (400) is
    decided here, next to the check that made it, rather than by matching on
    the message string in app.py.
    """

    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


class ProcessingError(RuntimeError):
    """The toolkit ran and failed. Carries its log for the response."""

    def __init__(self, message, log=""):
        self.log = log
        super().__init__(message)


@asynccontextmanager
async def reserve_slot():
    """Hold one of the CONCURRENCY processing slots for the duration."""
    async with _slots:
        yield


@contextmanager
def workspace():
    """A private directory for one job, removed however the job ends."""
    path = tempfile.mkdtemp(prefix="shelfready-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def inspect_upload(data):
    """Validate bytes as an image and return the extension to store it under.

    Identification is by content, never by the client's filename: the name is
    a label chosen by the caller and says nothing true about the bytes.
    """
    if not data:
        raise UploadError("The upload is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise UploadError(f"Image is larger than {mb} MB.", status=413)

    try:
        probe = Image.open(io.BytesIO(data))
        fmt, size = probe.format, probe.size
        probe.verify()  # Consumes the object; reopened later by the toolkit.
    except UploadError:
        raise
    except Exception:
        raise UploadError("That file is not an image we can read.", status=415)

    if not fmt:
        raise UploadError("That file is not an image we can read.", status=415)

    width, height = size
    if width * height > MAX_INPUT_PIXELS:
        mp = MAX_INPUT_PIXELS // 1_000_000
        raise UploadError(f"Image is larger than {mp} megapixels.", status=413)

    return _extension_for(fmt)


# Pillow lists several extensions per format and its first match is not always
# the obvious one (JPEG resolves to ".jfif"). Naming the common cases keeps the
# temp filename predictable; anything else falls back to Pillow's table.
PREFERRED_EXT = {
    "JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif",
    "BMP": ".bmp", "TIFF": ".tif", "HEIF": ".heic", "AVIF": ".avif",
}


def _extension_for(fmt):
    """The extension to store a sniffed `fmt` under, or refuse it."""
    ext = PREFERRED_EXT.get(fmt)
    if ext and ext in image_toolkit.SUPPORTED_EXTS:
        return ext
    for ext, name in Image.registered_extensions().items():
        if name == fmt and ext.lower() in image_toolkit.SUPPORTED_EXTS:
            return ext.lower()
    raise UploadError(f"{fmt} images are not supported.", status=415)


def download_name(filename):
    """A safe, recognizable name for the returned file.

    The client's name is used for the *label only* — never as a path — and is
    stripped of anything that could make it one.
    """
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    stem = _SAFE_STEM.sub("_", stem).strip("._-")[:64]
    return f"{stem or 'shelfready'}_processed.jpg"


def scrub_log(log, work_dir):
    """Strip server filesystem detail out of the toolkit's output.

    The toolkit prints for a desktop user, so it names the paths it wrote.
    Those are the server's paths — they carry the account name and the temp
    layout, and they mean nothing to someone in a browser. The diagnostics
    that DO mean something (auto-detection, quality analysis, warnings) are
    kept verbatim.
    """
    kept = []
    for line in (log or "").splitlines():
        if line.startswith("Saved ->"):
            continue
        for path in (os.path.realpath(work_dir), work_dir):
            line = line.replace(path, "[workspace]")
        kept.append(line)
    return "\n".join(kept).strip()


def _process_one(work_dir, data, ext, values):
    """Write one upload into `work_dir`, process it, return (path, log).

    The stored name is a fresh UUID, so nothing a client sends reaches the
    filesystem. Paths are injected here rather than accepted from params.py,
    which is why that module has no input/output keys to abuse.
    """
    stem = uuid.uuid4().hex
    in_path = os.path.join(work_dir, stem + ext)
    with open(in_path, "wb") as fh:
        fh.write(data)

    values = dict(values)
    values["in_file"] = in_path
    values["out_file"] = os.path.join(work_dir, stem + "_out.jpg")

    # The [interpreter, script] prefix is what made the GUI's log line
    # copy-pasteable; run_toolkit slices it off, so placeholders are fine.
    command = settings.build_args(values, "python", "image_toolkit.py")
    code, log = runner.run_toolkit(command.args)

    log = scrub_log(log, work_dir)
    if code != 0:
        raise ProcessingError("Processing failed.", log)
    if not os.path.exists(command.out_path):
        raise ProcessingError("Processing produced no output.", log)
    return command.out_path, log


def run_single(work_dir, data, filename, values):
    """Process one uploaded image. Returns (out_path, log, download_name).

    Blocking and CPU-bound — the caller runs it off the event loop, inside a
    reserve_slot() and a workspace().
    """
    ext = inspect_upload(data)
    out_path, log = _process_one(work_dir, data, ext, values)
    return out_path, log, download_name(filename)


def process_to_bytes(data, filename, values):
    """Process one upload and return (jpeg_bytes, log, download_name).

    The workspace opens and closes inside this call, so the result is already
    in memory by the time the temp directory goes away — the HTTP layer never
    holds a path to a file that is about to be deleted. Blocking; run it in a
    worker thread.
    """
    with workspace() as work_dir:
        out_path, log, name = run_single(work_dir, data, filename, values)
        with open(out_path, "rb") as fh:
            return fh.read(), log, name
