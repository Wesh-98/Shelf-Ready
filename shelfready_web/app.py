# -*- coding: utf-8 -*-
"""The HTTP layer.

Thin on purpose. Request shaping lives in params.py, the work lives in
jobs.py, and the pipeline lives in image_toolkit.py — this module only maps
between those and HTTP: read the upload under a cap, take a slot, run the job
off the event loop, hand back a JPEG.

Run locally with:
    .venv\Scripts\python.exe -m uvicorn shelfready_web.app:app --reload
"""

import asyncio
import json
import os
import re
import sys

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shelfready_ui.version import __version__, STUDIO_NAME, STUDIO_URL
from shelfready_web import jobs, params

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Where the download button points. The release workflow publishes the exe on
# a v* tag; /latest resolves to whatever the newest one is.
RELEASE_URL = "https://github.com/Wesh-98/Shelf-Ready/releases/latest"

# Per-IP budget. Processing is the expensive verb, so it is limited far more
# tightly than fetching the page or the form config.
PROCESS_RATE_LIMIT = os.environ.get("SHELFREADY_RATE_LIMIT", "20/minute")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="ShelfReady", version=__version__, docs_url=None, redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Header values must be latin-1; the toolkit's log is multi-line ASCII.
_HEADER_UNSAFE = re.compile(r"[^\x20-\x7e]+")
MAX_LOG_HEADER = 900


def _log_header(log):
    """Flatten the toolkit's log into one header-safe line."""
    return _HEADER_UNSAFE.sub(" | ", log or "").strip()[:MAX_LOG_HEADER]


async def _read_capped(upload):
    """Read an upload, refusing anything past the cap mid-stream.

    Content-Length is a claim, not a fact, so the cap is enforced while
    reading rather than trusted up front — a lying header cannot make the
    server buffer 2 GB.
    """
    chunks, total = [], 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > jobs.MAX_UPLOAD_BYTES:
            mb = jobs.MAX_UPLOAD_BYTES // (1024 * 1024)
            raise HTTPException(413, f"Image is larger than {mb} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Liveness for the platform's health check."""
    return {"status": "ok", "version": __version__}


@app.get("/download", include_in_schema=False)
async def download():
    """The desktop app, for people processing more than a few images."""
    return RedirectResponse(RELEASE_URL, status_code=302)


@app.get("/api/config")
async def config():
    """Everything the browser needs to build the form.

    Served from the Python tables rather than duplicated in JavaScript, so
    the web form, the desktop dropdowns and the validator cannot drift.
    """
    cfg = params.form_config()
    cfg["limits"] = {
        "max_upload_bytes": jobs.MAX_UPLOAD_BYTES,
        "max_input_pixels": jobs.MAX_INPUT_PIXELS,
        "supported_extensions": sorted(jobs.PREFERRED_EXT.values()),
    }
    cfg["version"] = __version__
    cfg["release_url"] = RELEASE_URL
    # The footer's credit comes from the same constants the desktop title bar
    # reads, so the two front ends cannot end up crediting different things.
    cfg["studio"] = {"name": STUDIO_NAME, "url": STUDIO_URL}
    return cfg


@app.post("/api/process")
@limiter.limit(PROCESS_RATE_LIMIT)
async def process(request: Request,
                  image: UploadFile = File(...),
                  settings: str = Form("{}")):
    """Process one uploaded image and return the cleaned JPEG."""
    try:
        payload = json.loads(settings or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "settings must be valid JSON.")

    try:
        values = params.from_request(payload)
    except params.ParamError as bad:
        return JSONResponse({"errors": bad.errors}, status_code=400)

    data = await _read_capped(image)

    # One slot per core, and a ceiling on how long any one image may hold it.
    try:
        async with jobs.reserve_slot():
            result = await asyncio.wait_for(
                run_in_threadpool(jobs.process_to_bytes,
                                  data, image.filename, values),
                timeout=jobs.JOB_TIMEOUT_SECONDS)
    except jobs.UploadError as bad:
        raise HTTPException(bad.status, str(bad))
    except asyncio.TimeoutError:
        raise HTTPException(504, "Processing took too long. Try a smaller canvas.")
    except jobs.ProcessingError as failed:
        return JSONResponse(
            {"errors": [str(failed)], "log": failed.log}, status_code=500)

    jpeg, log, name = result
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-ShelfReady-Log": _log_header(log),
            "Access-Control-Expose-Headers": "X-ShelfReady-Log",
            "Cache-Control": "no-store",
        },
    )
