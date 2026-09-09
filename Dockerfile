# ShelfReady web front end.
#
# 3.12 rather than the newest Python: it is what both CI workflows already
# standardize on for the best AVIF/HEIC wheel coverage, and the container is
# the one place where a missing codec wheel would mean building from source.
FROM python:3.12-slim

# Dependencies first, in their own layer — they are the slow part of the
# build and they change far less often than the application code.
WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY image_toolkit.py ./
COPY shelfready_ui/ ./shelfready_ui/
COPY shelfready_web/ ./shelfready_web/

# Nothing here needs root, and the process handles untrusted uploads.
RUN useradd --create-home --uid 10001 shelfready \
    && chown -R shelfready:shelfready /app
USER shelfready

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

EXPOSE 8080

# One worker per container: the pipeline is CPU-bound and already meters
# itself with a semaphore, so extra workers would multiply memory, not
# throughput. Scale by adding machines instead.
CMD ["sh", "-c", "exec uvicorn shelfready_web.app:app --host 0.0.0.0 --port ${PORT}"]
