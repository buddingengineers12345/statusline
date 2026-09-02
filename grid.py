#!/usr/bin/env python3
"""Zero-install launcher for the statusline package.

Claude Code invokes this file directly (``python3 grid.py < payload.json``),
so it must work without the package being pip-installed: it puts ``src/`` on
``sys.path`` and delegates to :func:`statusline.cli.main`. ``--selfcheck``
passes through.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from statusline.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
