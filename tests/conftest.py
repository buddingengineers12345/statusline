"""Shared fixtures and alignment helpers for the statusline test suite.

The package is imported from ``src/`` via ``pythonpath = ["src"]`` in
``pyproject.toml`` — no ``sys.path`` manipulation needed here.
"""

from datetime import datetime

import pytest

from statusline import ContextUsage, RateLimitUsage, Status
from statusline.config import DIVIDER
from statusline.rendering import display_width


def divider_columns(line: str) -> list[int]:
    """Display-width column each ``DIVIDER`` starts at, in order."""
    columns = []
    width = 0
    for part in line.split(DIVIDER)[:-1]:
        width += display_width(part)
        columns.append(width)
        width += display_width(DIVIDER)
    return columns


def assert_dividers_align(lines: list[str]) -> None:
    """Assert every line has exactly two dividers, all vertically aligned."""
    columns_per_line = [divider_columns(line) for line in lines]
    assert all(len(cols) == 2 for cols in columns_per_line), columns_per_line
    assert all(cols == columns_per_line[0] for cols in columns_per_line), columns_per_line


@pytest.fixture
def sample_status() -> Status:
    """A fully-populated Status object for testing."""
    return Status(
        model="claude-opus-4-8",
        effort="high",
        thinking="on",
        style="concise",
        fast="off",
        context=ContextUsage(percent=42),
        five_hour=RateLimitUsage(percent=30, resets_at=datetime(2026, 8, 2, 15, 29, 0)),
        seven_day=RateLimitUsage(percent=68, resets_at=datetime(2026, 8, 5, 0, 0, 0)),
        cwd="/tmp/demo",
    )


@pytest.fixture
def default_status() -> Status:
    """A Status with all defaults."""
    return Status()
