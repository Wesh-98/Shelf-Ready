# -*- coding: utf-8 -*-
"""The web front end for ShelfReady.

Replaces the tkinter layer, not the pipeline: params.py and jobs.py hand a
settings dict to shelfready_ui.settings and shelfready_ui.runner, which are
the same modules the desktop GUI runs through. Anything that changes how an
image is processed belongs in image_toolkit.py, where both front ends see it.

params.py and jobs.py are free of FastAPI the way settings.py and runner.py
are free of tkinter, so the request-shaping and the job machinery can be
tested without starting a server.
"""
