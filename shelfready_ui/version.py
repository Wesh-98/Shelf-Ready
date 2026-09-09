# -*- coding: utf-8 -*-
"""Single source of the application's identity.

Read by the window title and by ShelfReady.spec when stamping the built
executable, and served to the web front end through /api/config, so a
release only needs these lines changed — and the desktop app and the site
can never credit different things.
"""

__version__ = "1.0.0"

# Who made it. Shown in the desktop title bar and in the website footer.
STUDIO_NAME = "LeFee Labs"
STUDIO_URL = "https://lefeelabs.site"
