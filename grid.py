#!/usr/bin/env python3
"""Column-aligned grid statusline for Claude Code.

Reads a statusline JSON payload on stdin and prints a 5-line, 3-column
ANSI grid: mascot | session state | usage bars.

The two ``│`` dividers stay vertical because each column is padded to a
fixed *display* width (emoji = 2 terminal cells, braille = 1) rather than
its character count. Tools that lay out each line independently (e.g.
ccstatusline) cannot do this — their bars never align across rows.

Usage:
    python3 grid.py < payload.json
    python3 grid.py --selfcheck     # validate parser/formatter/renderer

The script is dependency-free (stdlib only, Python >= 3.10) and never fails
on malformed input: bad JSON renders the all-defaults grid, and junk field
values fall back to their defaults.

Architecture: ``StatusParser`` turns the raw payload dict into an immutable
``Status`` domain object (the only place that touches dict keys or coerces
junk); ``GridRenderer`` turns a ``Status`` into the ANSI grid using ``Theme``
(colors) and ``Layout`` (geometry + labels) configuration.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

#: Codepoint boundaries for terminal cell-width classification (see
#: ``TerminalFormatter.display_width``). Named to keep the width rules readable.
_CP_PENCIL = 0x270D  # ✍ — renders 1 cell despite sitting in the symbol block
_CP_EMOJI_START = 0x1F000  # emoji and above: 2 cells
_CP_SYMBOL_BLOCK = range(0x2600, 0x27C0)  # U+2600..U+27BF miscellaneous symbols: 2 cells


@dataclass(frozen=True, slots=True)
class Theme:
    """ANSI colors for the grid."""

    gray: str = "\033[90m"
    white: str = "\033[97m"
    reset: str = "\033[0m"

    @property
    def divider(self) -> str:
        """Column divider, rendered dim so the content stands out."""
        return f"{self.gray}│{self.reset}"


@dataclass(frozen=True, slots=True)
class Layout:
    """Grid geometry, labels, and mascot art."""

    #: Usage bar geometry: 10 cells, filled left-to-right.
    bar_width: int = 10
    fill: str = "█"
    empty: str = "░"

    #: Column-2 minimum display width — keeps the second divider from jumping
    #: left when every value is short; grows automatically for long values.
    state_min_width: int = 26

    #: Braille-art mascot, one string per output row (5 rows total).
    mascot: tuple[str, ...] = (
        "⠤⢤⣤⣤⣤⣤⣤⣤⠀⠀⢰⣀⡆⠀⠀⢠⣤⣤⣤⣤⣤⣤⡤⠤⠀",
        "⠀⠀⠛⣿⣿⣿⣿⣿⣷⣤⣼⣿⣧⣤⣤⣾⣿⣿⣿⣿⣿⠛⠀⠀⠀",
        "⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀",
        "⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
        "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    )

    #: Column-2 (state) row labels. ``✍`` is followed by TWO spaces because it
    #: renders 1 cell wide (see display_width), unlike the 2-cell emoji above it.
    state_names: tuple[str, ...] = (
        "\U0001f916 Model",
        "⚙️ Effort",
        "\U0001f9e0 Extended",
        "✍  Style",
        "⚡ Fast",
    )

    #: Column-3 (usage) row labels.
    usage_labels: tuple[str, ...] = ("\U0001f4ca Context", "⏳ 5h", "\U0001f4c5 7d")


# --------------------------------------------------------------------------
# Domain model
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Usage:
    """One usage gauge: percent used plus an optional reset time."""

    percent: int = 0
    resets_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Status:
    """Everything the grid displays, parsed and typed."""

    model: str = "?"
    effort: str = "?"
    thinking: bool = False
    style: str = "default"
    fast: bool = False
    context: Usage = field(default_factory=Usage)
    five_hour: Usage | None = None
    seven_day: Usage | None = None
    cwd: Path = Path("?")


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


class StatusParser:
    """Sole owner of payload dict access: raw JSON dict -> ``Status``.

    Every field is junk-tolerant — a missing key, wrong type, or garbage
    value collapses to its default so a bad field can never take down the
    whole statusline.
    """

    def parse(self, raw: dict) -> Status:
        """Build a ``Status`` from a statusline payload dict."""

        def get(key: str, sub: str, default: str = "?") -> str:
            return (raw.get(key) or {}).get(sub) or default

        return Status(
            model=get("model", "id"),
            effort=get("effort", "level"),
            thinking=bool((raw.get("thinking") or {}).get("enabled")),
            style=get("output_style", "name", "default"),
            fast=bool(raw.get("fast_mode")),
            context=Usage(percent=self._percent(raw.get("context_window"))),
            five_hour=self._limit((raw.get("rate_limits") or {}).get("five_hour")),
            seven_day=self._limit((raw.get("rate_limits") or {}).get("seven_day")),
            cwd=Path(raw.get("cwd") or (raw.get("workspace") or {}).get("current_dir") or "?"),
        )

    def _limit(self, obj: Any) -> Usage | None:
        """A rate-limit gauge, or ``None`` when the payload has no data for it."""
        if not obj:
            return None
        return Usage(percent=self._percent(obj), resets_at=self._resets_at(obj.get("resets_at")))

    @staticmethod
    def _percent(obj: Any) -> int:
        """Extract ``used_percentage`` as an int; junk (NaN, strings, inf) -> 0."""
        try:
            return int(float((obj or {}).get("used_percentage") or 0))
        except (TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _resets_at(value: Any) -> datetime | None:
        """Parse a ``resets_at`` timestamp to a local ``datetime``.

        Accepts epoch seconds (int/float/str) or an ISO-8601 string
        (``YYYY-MM-DDTHH:MM:SS``, any extra suffix ignored). Returns ``None``
        for missing or unparseable input — the renderer hides the clock then.
        """
        if value is None:
            return None
        try:
            # wall-clock; a tz-aware value would change the displayed clock and
            # break grid.sh byte-parity.
            return datetime.fromtimestamp(float(value))  # noqa: DTZ006
        except (TypeError, ValueError, OverflowError, OSError):
            try:
                return datetime.fromisoformat(str(value)[:19])
            except ValueError:
                return None


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


class TerminalFormatter:
    """Terminal display-width math: cell counting and cell-aware padding."""

    @staticmethod
    def display_width(s: str) -> int:
        """Return the terminal cell width of ``s``.

        Rules (matching how mainstream terminals actually render):

        - variation selectors (VS16) and combining marks: 0 cells
        - ``✍`` (U+270D): 1 cell — tmux renders it narrow despite its range
        - emoji (>= U+1F000), the U+2600-U+27BF symbol block, and East-Asian
          Wide/Fullwidth characters: 2 cells
        - everything else (ASCII, braille patterns, ...): 1 cell
        """
        width = 0
        for ch in s:
            if ch == "️" or unicodedata.combining(ch):
                continue
            cp = ord(ch)
            if cp == _CP_PENCIL:
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

    @classmethod
    def pad(cls, s: str, width: int) -> str:
        """Right-pad ``s`` with spaces up to ``width`` display cells."""
        return s + " " * max(0, width - cls.display_width(s))


class ProgressBar:
    """Fixed-width ``█░`` progress bar."""

    def __init__(self, layout: Layout) -> None:
        """Bind the bar to a ``Layout`` (width, fill/empty glyphs)."""
        self.layout = layout

    def render(self, percent: float) -> str:
        """Render ``percent`` (clamped to 0-100) as a bar.

        The fill count uses Python's ``round`` (banker's rounding:
        ``round(2.5) == 2``).
        """
        pct = max(0.0, min(100.0, percent))
        filled = round(pct / 100 * self.layout.bar_width)
        return self.layout.fill * filled + self.layout.empty * (self.layout.bar_width - filled)


class GridRenderer:
    """``Status`` -> the 5-line ANSI grid string."""

    def __init__(self, theme: Theme, layout: Layout) -> None:
        """Bind the renderer to its ``Theme`` (colors) and ``Layout`` (geometry)."""
        self.theme = theme
        self.layout = layout
        self.fmt = TerminalFormatter()
        self.bar = ProgressBar(layout)

    def render(self, status: Status) -> str:
        """Assemble the full 5-line grid."""
        left = self._state_rows(status)
        right = self._usage_rows(status)

        mascot_w = max(self.fmt.display_width(m) for m in self.layout.mascot)
        # Column 2 grows past its floor when a value (e.g. a long model id) needs it.
        state_w = max(*(self.fmt.display_width(x) for x in left), self.layout.state_min_width)

        theme, div = self.theme, self.theme.divider
        lines = []
        for i in range(5):
            mascot = f"{theme.gray}{self.fmt.pad(self.layout.mascot[i], mascot_w)}{theme.reset}"
            state = f"{theme.white}{self.fmt.pad(left[i], state_w)}{theme.reset}"
            usage = f"{theme.white}{right[i]}{theme.reset}" if right[i] else ""
            lines.append(f"{mascot}   {div}   {state}   {div}   {usage}".rstrip())
        return "\n".join(lines)

    def _state_rows(self, status: Status) -> list[str]:
        """Build column 2: five ``label : value`` rows with aligned colons."""
        onoff = {True: "on", False: "off"}
        values = [
            status.model,
            status.effort,
            onoff[status.thinking],
            status.style,
            onoff[status.fast],
        ]
        # +4 pushes every colon 4 cells right of the longest label.
        name_w = max(self.fmt.display_width(n) for n in self.layout.state_names) + 4
        return [
            f"{self.fmt.pad(n, name_w)}: {v}"
            for n, v in zip(self.layout.state_names, values, strict=True)
        ]

    def _usage_rows(self, status: Status) -> list[str]:
        """Build column 3: usage bars, a spacer row, and the cwd row.

        The 5-hour / 7-day rate-limit rows are omitted (empty string) when the
        payload carried no data for them.
        """
        labels = self.layout.usage_labels
        return [
            self._usage_row(labels[0], status.context, None),
            self._usage_row(labels[1], status.five_hour, "%H:%M"),
            self._usage_row(labels[2], status.seven_day, "%m-%d"),
            "",
            f"\U0001f4c1 {status.cwd}",
        ]

    def _usage_row(self, label: str, usage: Usage | None, clock_fmt: str | None) -> str:
        """One ``[label][bar][pct%][⏰ clock]`` row with fixed sub-widths."""
        if usage is None:
            return ""
        label_w = max(self.fmt.display_width(x) for x in self.layout.usage_labels)
        cell = f"{self.fmt.pad(label, label_w)}   {self.bar.render(usage.percent)}   {usage.percent:>3}%"
        if clock_fmt and usage.resets_at is not None:
            return f"{cell}   ⏰ {usage.resets_at.strftime(clock_fmt)}"
        return cell


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


def selfcheck() -> None:
    """Assert parser/formatter/renderer behavior; print ``selfcheck ok``."""
    fmt = TerminalFormatter()
    assert fmt.display_width("⠀") == 1, "braille width"
    assert fmt.display_width("\U0001f9e0") == 2, "emoji width"
    assert fmt.display_width("⚙️") == 2, "emoji+VS16 width"
    assert fmt.display_width("abc") == 3, "ascii width"
    assert fmt.display_width("中") == 2, "east-asian wide width"
    assert fmt.display_width("é") == 1, "combining mark width"

    bar = ProgressBar(Layout())
    assert len(bar.render(50)) == Layout().bar_width, "bar length"
    assert bar.render(0) == Layout().empty * Layout().bar_width, "empty bar"
    assert bar.render(100) == Layout().fill * Layout().bar_width, "full bar"

    parser = StatusParser()
    assert parser.parse({}) == Status(), "empty payload -> all defaults"
    assert parser._percent({"used_percentage": "junk"}) == 0, "junk pct falls back to 0"
    assert parser._limit({}) is None, "empty rate-limit dict -> row omitted"
    assert parser._resets_at("garbage") is None, "junk resets_at -> no clock"
    assert parser._resets_at(0) is not None, "epoch resets_at parses"
    assert parser._resets_at("2026-08-02T15:29:00Z") == datetime(2026, 8, 2, 15, 29), "ISO parses"

    # End-to-end: a fixed Status renders to an exact snapshot.
    status = Status(
        model="claude-opus-4-8",
        effort="high",
        thinking=True,
        style="concise",
        fast=False,
        context=Usage(42),
        five_hour=Usage(30, datetime(2026, 8, 2, 15, 29)),
        seven_day=Usage(68, datetime(2026, 8, 5)),
        cwd=Path("/tmp/demo"),
    )
    out = GridRenderer(Theme(), Layout()).render(status)
    assert out == EXPECTED_SNAPSHOT, "end-to-end render snapshot"
    print("selfcheck ok")  # noqa: T201


#: Exact render of the ``Status`` fixture in ``selfcheck`` — fails on any
#: unintended output change (alignment, colors, spacing).
EXPECTED_SNAPSHOT = "\n".join(
    (
        "\x1b[90m⠤⢤⣤⣤⣤⣤⣤⣤⠀⠀⢰⣀⡆⠀⠀⢠⣤⣤⣤⣤⣤⣤⡤⠤⠀\x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m🤖 Model       : claude-opus-4-8\x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m📊 Context   ████░░░░░░    42%\x1b[0m",
        "\x1b[90m⠀⠀⠛⣿⣿⣿⣿⣿⣷⣤⣼⣿⣧⣤⣤⣾⣿⣿⣿⣿⣿⠛⠀⠀⠀\x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m⚙️ Effort      : high           \x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m⏳ 5h        ███░░░░░░░    30%   ⏰ 15:29\x1b[0m",
        "\x1b[90m⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀\x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m🧠 Extended    : on             \x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m📅 7d        ███████░░░    68%   ⏰ 08-05\x1b[0m",
        "\x1b[90m⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m✍  Style       : concise        \x1b[0m   \x1b[90m│\x1b[0m",
        "\x1b[90m⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m⚡ Fast        : off            \x1b[0m   \x1b[90m│\x1b[0m   "
        "\x1b[97m📁 /tmp/demo\x1b[0m",
    )
)


def main(argv: list[str]) -> int:
    """CLI entry point: run ``--selfcheck`` or render stdin JSON."""
    if "--selfcheck" in argv:
        selfcheck()
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}  # malformed input → render the all-defaults grid
    status = StatusParser().parse(data)
    print(GridRenderer(Theme(), Layout()).render(status))  # noqa: T201 (statusline contract)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
