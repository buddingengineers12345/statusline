"""Typed domain model for everything the grid displays."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from datetime import datetime


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
