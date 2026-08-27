"""Shared assertion helpers for the statusline test suite."""

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
