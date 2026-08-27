"""CLI entry point: statusline JSON on stdin, rendered grid on stdout."""

from __future__ import annotations

import json
import sys
from json import JSONDecodeError
from typing import Any

from statusline.errors import handle_exception
from statusline.parsing import extract_status_info
from statusline.rendering import render_grid


@handle_exception({}, JSONDecodeError, OSError)
def load_data() -> Any:
    """Load a statusline payload from stdin.

    Returns:
        Any: The parsed JSON payload (usually a dict, but any valid JSON
            value passes through), or ``{}`` on malformed input.

    Examples:
        load_data()
    """
    return json.load(sys.stdin)


def main() -> int:
    """CLI entry point.

    Returns:
        int: Process exit code.

    Examples:
        main()
    """
    data = load_data()
    status = extract_status_info(data)
    grid_text = render_grid(status)
    print(grid_text)  # noqa: T201 (statusline contract)
    return 0
