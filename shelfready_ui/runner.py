# -*- coding: utf-8 -*-
"""Running the toolkit and reading back what it printed.

Free of tkinter, so the run path can be tested without a display.

The toolkit runs **in-process** rather than as a subprocess. A frozen build
has no Python interpreter to re-invoke — sys.executable is the app itself —
so shelling out would relaunch the GUI instead of processing anything. Doing
the work here also skips a fresh numpy/scipy import on every run and avoids
console windows flashing on Windows.
"""

import io
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import image_toolkit

def run_toolkit(argv):
    """Run image_toolkit with `argv`, returning (exit_code, captured output).

    `argv` is what settings.build_args produced, i.e. it still carries the
    [interpreter, script] prefix that made the logged command copy-pasteable;
    only the flags after it are meaningful here.

    Never raises: a failure inside the toolkit comes back as a non-zero code
    with the traceback in the output, so the GUI can show it in the log
    instead of dying with it.
    """
    flags = list(argv[2:]) if len(argv) > 2 else []
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            image_toolkit.main(flags)
        return 0, buf.getvalue().strip()
    except SystemExit as e:
        # argparse calls sys.exit on a bad flag; 0/None still means success.
        code = e.code
        if code is None or code == 0:
            return 0, buf.getvalue().strip()
        return (code if isinstance(code, int) else 1), buf.getvalue().strip()
    except Exception:
        return 1, (buf.getvalue() + "\n" + traceback.format_exc()).strip()
