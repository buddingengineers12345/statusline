"""Render a :class:`~statusline.models.Status` into the 5-row 3-column grid.

Columns are padded by terminal display width — not ``len()`` — so the two
``│`` dividers stay vertical across all rows.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from statusline.config import (
    BAR_WIDTH,
    CP_EMOJI_START,
    CP_NARROW_SYMBOLS,
    CP_SYMBOL_BLOCK,
    DIVIDER,
    EMPTY,
    FILL,
    LABELS,
    MASCOT,
    STATE_MIN_WIDTH,
    STATE_PADDING,
    VS16,
)

if TYPE_CHECKING:
    from statusline.models import ContextUsage, RateLimitUsage, Status


def display_width(text: str) -> int:
    """Compute the terminal cell width of ``text``.

    VS16 and combining marks count 0; pencil (U+270D) counts 1; emoji,
    symbol-block, and CJK-wide characters count 2; everything else counts 1.

    Args:
        text (str): String to measure.

    Returns:
        int: Total display width in cells.

    Examples:
        display_width("🤖")
    """
    width = 0
    for ch in text:
        if ch == VS16 or unicodedata.combining(ch):
            continue
        cp = ord(ch)
        if cp in CP_NARROW_SYMBOLS:
            width += 1
        elif (
            cp >= CP_EMOJI_START
            or cp in CP_SYMBOL_BLOCK
            or unicodedata.east_asian_width(ch) in ("W", "F")
        ):
            width += 2
        else:
            width += 1
    return width


def pad(text: str, width: int) -> str:
    """Right-pad ``text`` with spaces to a display width.

    Args:
        text (str): String to pad.
        width (int): Target display width in cells.

    Returns:
        str: The padded string.

    Examples:
        pad("Model", 10)
    """
    current_width = display_width(text)
    missing = width - current_width
    missing = max(0, missing)
    spaces = " " * missing
    return text + spaces


def label_text(key: str) -> str:
    """Build the icon-plus-text label for a ``LABELS`` entry.

    Args:
        key (str): Key into ``LABELS``.

    Returns:
        str: ``"icon text"``.

    Raises:
        KeyError: If ``key`` is not in ``LABELS``.

    Examples:
        label_text("model")
    """
    icon, text = LABELS[key]
    if key == "style":
        return f" {icon} {text}"
    return f"{icon} {text}"


def render_bar(percent: float) -> str:
    """Render a usage bar.

    Args:
        percent (float): Usage percent; clamped to 0-100. Fill count uses
            banker's rounding.

    Returns:
        str: A ``BAR_WIDTH``-cell bar of fill/empty characters.

    Examples:
        render_bar(42)
    """
    pct = min(100.0, percent)
    pct = max(0.0, pct)
    ratio = pct / 100
    filled = round(ratio * BAR_WIDTH)
    empty = BAR_WIDTH - filled
    filled_cells = FILL * filled
    empty_cells = EMPTY * empty
    return filled_cells + empty_cells


def _gauge_cell(label: str, percent: int, label_w: int) -> str:
    """Build the ``[label][bar][pct%]`` prefix shared by every usage row.

    Args:
        label (str): Row label text.
        percent (int): Usage percent.
        label_w (int): Display width to pad ``label`` to.

    Returns:
        str: The formatted cell.
    """
    padded_label = pad(label, label_w)
    bar = render_bar(percent)
    pct_str = f"{percent:>3}%"
    return f"{padded_label}   {bar}   {pct_str}"


def _percent_row(label: str, usage: ContextUsage, label_w: int) -> str:
    """Build the context row.

    Args:
        label (str): Row label text.
        usage (ContextUsage): Context usage to render. Never resets on a
            timer.
        label_w (int): Display width to pad ``label`` to.

    Returns:
        str: The formatted row.
    """
    return _gauge_cell(label, usage.percent, label_w)


def _limit_row(label: str, usage: RateLimitUsage | None, clock_fmt: str, label_w: int) -> str:
    """Build a rate-limit row.

    Args:
        label (str): Row label text.
        usage (RateLimitUsage | None): Rate-limit usage to render, or
            ``None`` if absent.
        clock_fmt (str): ``strftime`` format for the reset clock.
        label_w (int): Display width to pad ``label`` to.

    Returns:
        str: The formatted row, or ``""`` if ``usage`` is ``None``.
    """
    if usage is None:
        return ""
    cell = _gauge_cell(label, usage.percent, label_w)
    if usage.resets_at is not None:
        clock_str = usage.resets_at.strftime(clock_fmt)
        return f"{cell}   ⏰ {clock_str}"
    return cell


def _state_rows(status: Status, labels: dict[str, str], label_w: int) -> list[str]:
    """Build column 2: one ``label : value`` row per state field.

    Args:
        status (Status): Status to render.
        labels (dict[str, str]): Label text keyed by ``Status`` field name.
        label_w (int): Display width to pad each label to.

    Returns:
        list[str]: Five formatted rows.
    """
    keys = ("model", "effort", "thinking", "style", "fast")
    return [f"{pad(labels[key], label_w)} : {getattr(status, key)}" for key in keys]


def _usage_rows(status: Status, labels: dict[str, str], label_w: int) -> list[str]:
    """Build column 3: usage bars, a spacer row, and the cwd row.

    Args:
        status (Status): Status to render.
        labels (dict[str, str]): Label text keyed by ``Status`` field name.
        label_w (int): Display width to pad each label to.

    Returns:
        list[str]: Five formatted rows; rate-limit rows blank out when data
            is missing.
    """
    return [
        _percent_row(labels["context"], status.context, label_w),
        _limit_row(labels["five_hour"], status.five_hour, "%H:%M", label_w),
        _limit_row(labels["seven_day"], status.seven_day, "%m-%d", label_w),
        f"🆔 {status.session_id}" if status.session_id != "?" else "",
        f"📁 {status.cwd}",
    ]


def render_grid(status: Status) -> str:
    """Assemble the full 5-line grid.

    Args:
        status (Status): Status to render.

    Returns:
        str: The rendered grid text.

    Examples:
        render_grid(extract_status_info(data))
    """
    labels = {key: label_text(key) for key in LABELS}
    label_w = max(display_width(label_str) for label_str in labels.values())
    left = _state_rows(status, labels, label_w=label_w + STATE_PADDING)
    right = _usage_rows(status, labels, label_w)
    assert len(left) == len(right) == len(MASCOT), "row count drift across columns"  # noqa: S101

    mascot_w = max(display_width(row) for row in MASCOT)
    state_w = max(STATE_MIN_WIDTH, *(display_width(state_line) for state_line in left))

    lines = []
    for mascot_line, state_line, usage_line in zip(MASCOT, left, right, strict=True):
        mascot = pad(mascot_line, mascot_w)
        state = pad(state_line, state_w)
        line = f"{mascot}   {DIVIDER}   {state}   {DIVIDER}   {usage_line}"
        line = line.rstrip()
        lines.append(line)
    return "\n".join(lines)
