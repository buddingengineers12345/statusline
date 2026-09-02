"""CLI entry point: statusline JSON on stdin, rendered grid on stdout.

``--selfcheck`` validates display_width(), render_bar(), and empty-payload
rendering instead of reading stdin.
"""

from __future__ import annotations

import json
import sys
from json import JSONDecodeError
from typing import Any

from statusline.config import BAR_WIDTH, EMPTY, FILL
from statusline.errors import handle_exception
from statusline.parsing import extract_status_info
from statusline.rendering import display_width, render_bar, render_grid


@handle_exception({}, JSONDecodeError, UnicodeDecodeError, OSError)
def load_data() -> Any:
    """Load a statusline payload from stdin.

    Returns:
        Any: The parsed JSON payload (usually a dict, but any valid JSON
            value passes through), or ``{}`` on malformed or mis-encoded
            input.

    Examples:
        load_data()
    """
    return json.load(sys.stdin)


def selfcheck() -> None:
    """Assert-based smoke check for width math, bars, and empty-payload render."""
    assert display_width("⠀") == 1, "braille width"
    assert display_width("\U0001f9e0") == 2, "emoji width"
    assert display_width("⚙️") == 2, "gear+VS16 width"
    assert display_width("abc") == 3, "ascii width"
    assert len(render_bar(50)) == BAR_WIDTH
    assert render_bar(0) == EMPTY * BAR_WIDTH
    assert render_bar(100) == FILL * BAR_WIDTH
    assert "📁" in render_grid(extract_status_info({})), "empty payload renders the grid"
    print("selfcheck ok")  # noqa: T201 (selfcheck contract)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``--selfcheck`` or render stdin JSON.

    Returns:
        int: Process exit code.

    Examples:
        main()
    """
    args = sys.argv[1:] if argv is None else argv
    if "--selfcheck" in args:
        selfcheck()
        return 0
    data = load_data()
    status = extract_status_info(data)
    grid_text = render_grid(status)
    print(grid_text)  # noqa: T201 (statusline contract)
    return 0
