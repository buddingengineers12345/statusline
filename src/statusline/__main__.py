"""Run the statusline as a module: ``python3 -m statusline < payload.json``."""

from __future__ import annotations

import sys

from statusline.cli import main

if __name__ == "__main__":
    sys.exit(main())
