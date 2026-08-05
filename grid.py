#!/usr/bin/env python3
"""Column-aligned grid statusline for Claude Code.

Reads a statusline JSON payload on stdin and prints a 5-row 3-column grid.

Usage:
    python3 grid.py < payload.json
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unicodedata
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Layout
DIVIDER = "│"
BAR_WIDTH = 10
FILL = "█"
EMPTY = "░"
STATE_MIN_WIDTH = 26  # floor; grows for long values
STATE_PADDING = 5

MASCOT = (
    "⠤⢤⣤⣤⣤⣤⣤⣤⠀⠀⢰⣀⡆⠀⠀⢠⣤⣤⣤⣤⣤⣤⡤⠤⠀",
    "⠀⠀⠛⣿⣿⣿⣿⣿⣷⣤⣼⣿⣧⣤⣤⣾⣿⣿⣿⣿⣿⠛⠀⠀⠀",
    "⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
)

# Labels: (icon, text). Gear/pencil are EAW=Neutral (1 cell) despite VS16 —
# their icons bake in a compensating trailing space so all labels share width.
LABELS = {
    "model": ("🤖", "Model"),
    "effort": ("⚙️ ", "Effort"),
    "thinking": ("🧠", "Extended"),
    "style": ("✍ ", "Style"),
    "fast": ("⚡", "Fast"),
    "context": ("📊", "Context"),
    "five_hour": ("⏳", "5h"),
    "seven_day": ("📅", "7d"),
}

# Unicode width classification (display_width)
_CP_NARROW_SYMBOLS = {0x2699, 0x270D}  # gear, pencil
_CP_EMOJI_START = 0x1F000
_CP_SYMBOL_BLOCK = range(0x2600, 0x27C0)
_VS16 = "️"


# --------------------------------------------------------------------------
# Domain model
# --------------------------------------------------------------------------


class ContextUsage(NamedTuple):
    """Context-window usage.

    Attributes:
        percent: Usage percentage. Never resets on a timer.
    """

    percent: int = 0


class RateLimitUsage(NamedTuple):
    """A rate-limit gauge.

    Attributes:
        percent: Usage percentage.
        resets_at: When the limit resets, or ``None`` if unknown.
    """

    percent: int = 0
    resets_at: datetime | None = None


class Status(NamedTuple):
    """Everything the grid displays, parsed and typed.

    Attributes:
        model: Model id.
        effort: Effort level.
        style: Output style name.
        cwd: Current working directory.
        thinking: ``"on"`` or ``"off"``.
        fast: ``"on"`` or ``"off"``.
        context: Context-window usage.
        five_hour: 5-hour rate-limit usage, or ``None`` if absent.
        seven_day: 7-day rate-limit usage, or ``None`` if absent.
    """

    # Text fields
    model: str = "?"
    effort: str = "?"
    style: str = "default"

    # Path
    cwd: str = "?"

    # Boolean
    thinking: str = "off"
    fast: str = "off"

    # Parsed
    context: ContextUsage = ContextUsage()
    five_hour: RateLimitUsage | None = None
    seven_day: RateLimitUsage | None = None


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------


def handle_exception(
    default: Any, *exceptions: type[BaseException]
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that returns a copy of ``default`` instead of raising.

    Copies ``default`` to avoid aliasing a shared mutable value across calls.

    Args:
        default (Any): Value to return (copied) when the wrapped function raises.
        *exceptions (type[BaseException]): Exception types to catch.

    Returns:
        Callable[[Callable[..., Any]], Callable[..., Any]]: A decorator for
            the target function.

    Examples:
        @handle_exception(0, ValueError)
        def parse(value): ...
    """

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except exceptions:
                return copy.copy(default)

        return wrapper

    return decorate


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _as_dict(obj: Any) -> dict:
    """Coerce ``obj`` to a dict.

    Args:
        obj (Any): Value to coerce.

    Returns:
        dict: ``obj`` if it's a dict, else an empty dict.
    """
    if isinstance(obj, dict):
        return obj
    return {}


def _nested_get(data: Any, keys: list[str], default: Any = None) -> Any:
    """Walk ``keys`` through nested dicts.

    Falsy values (``0``, ``""``, ``None``) collapse to ``default`` too.

    Args:
        data (Any): Root value to walk.
        keys (list[str]): Sequence of keys to descend through.
        default (Any): Value returned on a missing or falsy result.

    Returns:
        Any: The resolved value, or ``default``.
    """
    value = data
    for key in keys:
        current_dict = _as_dict(value)
        value = current_dict.get(key)
    if value:
        return value
    return default


@handle_exception(0, TypeError, ValueError, OverflowError)
def process_percent(value: Any) -> int:
    """Coerce ``value`` to an integer percent clamped to 0-100.

    Args:
        value (Any): Raw percent value.

    Returns:
        int: Integer in the range [0, 100].

    Examples:
        process_percent("42.7")
    """
    pct = int(float(value))
    pct = max(0, pct)
    pct = min(100, pct)
    return pct


@handle_exception(None, TypeError, ValueError, OverflowError, OSError)
def _parse_epoch(value: Any) -> datetime | None:
    """Convert epoch seconds to a local wall-clock ``datetime``.

    Args:
        value (Any): Epoch seconds (int, float, or str).

    Returns:
        datetime | None: The parsed datetime, or ``None`` on failure.
    """
    seconds = float(value)
    return datetime.fromtimestamp(seconds)  # noqa: DTZ006 (wall-clock by design)


@handle_exception(None, ValueError)
def _parse_iso(value: str) -> datetime | None:
    """Convert an ISO-8601 string to a ``datetime``.

    Args:
        value (str): ISO-8601 string (``YYYY-MM-DDTHH:MM:SS``); any suffix
            past the 19th character is ignored.

    Returns:
        datetime | None: The parsed datetime, or ``None`` on failure.
    """
    trimmed = value[:19]
    return datetime.fromisoformat(trimmed)


def _parse_resets_at(value: Any) -> datetime | None:
    """Parse ``resets_at`` as epoch seconds or ISO-8601.

    Args:
        value (Any): Raw ``resets_at`` value.

    Returns:
        datetime | None: A local datetime, or ``None`` if unparseable.
    """
    epoch_result = _parse_epoch(value)
    if epoch_result is not None:
        return epoch_result
    return _parse_iso(str(value))


def _parse_limit(obj: Any) -> RateLimitUsage | None:
    """Build a rate-limit gauge from a payload section.

    Args:
        obj (Any): Raw ``five_hour``/``seven_day`` payload value.

    Returns:
        RateLimitUsage | None: The parsed gauge, or ``None`` if ``obj`` has
            no data.
    """
    obj_dict = _as_dict(obj)
    if not obj_dict:
        return None
    percent = process_percent(_nested_get(obj_dict, ["used_percentage"]))
    resets_at = _parse_resets_at(obj_dict.get("resets_at"))
    return RateLimitUsage(percent=percent, resets_at=resets_at)


@handle_exception(None, OSError, JSONDecodeError, TypeError, ValueError)
def _settings_effort_level() -> str | None:
    """Read ``effortLevel`` from ``~/.claude/settings.json``, if present."""
    raw = json.loads(Path.home().joinpath(".claude", "settings.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    level = raw.get("effortLevel")
    if isinstance(level, str) and level.strip():
        return level.strip()
    return None


def _resolve_effort(data: dict) -> str:
    """Resolve effort: live ``effort.level``, else ``$CLAUDE_EFFORT``, else settings.

    Claude Code omits ``effort`` from the statusline payload when the current
    model does not support the effort parameter (e.g. Haiku). Fall back to the
    configured ``effortLevel`` so the grid still reflects the user's setting.
    """
    level = _nested_get(data, ["effort", "level"])
    if isinstance(level, str) and level:
        return level
    env = os.environ.get("CLAUDE_EFFORT", "").strip()
    if env:
        return env
    configured = _settings_effort_level()
    if configured:
        return configured
    return "?"


def extract_status_info(data: dict) -> Status:
    """Build a ``Status`` from a statusline payload.

    Args:
        data (dict): Parsed JSON payload; every field is junk-tolerant.

    Returns:
        Status: The extracted status.

    Examples:
        extract_status_info({"model": {"id": "claude-opus-5"}})
    """
    model = _nested_get(data, ["model", "id"], "?")
    effort = _resolve_effort(data)
    style = _nested_get(data, ["output_style", "name"], "default")

    thinking_enabled = _nested_get(data, ["thinking", "enabled"])
    fast_mode = _nested_get(data, ["fast_mode"])

    thinking = "on" if thinking_enabled is True else "off"
    fast = "on" if fast_mode is True else "off"

    cwd = _nested_get(data, ["cwd"])
    if not cwd:
        cwd = _nested_get(data, ["workspace", "current_dir"], "?")

    context_window = _nested_get(data, ["context_window", "used_percentage"])
    context_percent = process_percent(context_window)
    context = ContextUsage(percent=context_percent)

    five_hour_data = _nested_get(data, ["rate_limits", "five_hour"])
    five_hour = _parse_limit(five_hour_data)
    seven_day_data = _nested_get(data, ["rate_limits", "seven_day"])
    seven_day = _parse_limit(seven_day_data)

    return Status(
        model=model,
        effort=effort,
        style=style,
        cwd=cwd,
        thinking=thinking,
        fast=fast,
        context=context,
        five_hour=five_hour,
        seven_day=seven_day,
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def display_width(text: str) -> int:
    """Compute the terminal cell width of ``text``.

    VS16 and combining marks count 0; gear/pencil count 1; emoji,
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
        if ch == _VS16 or unicodedata.combining(ch):
            continue
        cp = ord(ch)
        if cp in _CP_NARROW_SYMBOLS:
            width += 1
        elif (
            cp >= _CP_EMOJI_START
            or cp in _CP_SYMBOL_BLOCK
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
        "",
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


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


@handle_exception({}, JSONDecodeError, OSError)
def load_data() -> dict:
    """Load a statusline payload from stdin.

    Returns:
        dict: The parsed payload, or ``{}`` on malformed input.

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


if __name__ == "__main__":
    sys.exit(main())
