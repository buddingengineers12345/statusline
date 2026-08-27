"""Turn a raw statusline JSON payload into a typed :class:`~statusline.models.Status`.

Every field is junk-tolerant: wrong types, missing keys, and malformed
values degrade to defaults instead of raising.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from statusline.errors import handle_exception
from statusline.models import ContextUsage, RateLimitUsage, Status


def _as_dict(obj: Any) -> dict[str, Any]:
    """Coerce ``obj`` to a dict.

    Args:
        obj (Any): Value to coerce.

    Returns:
        dict[str, Any]: ``obj`` if it's a dict, else an empty dict.
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


def _resolve_effort(data: Any) -> str:
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


def extract_status_info(data: Any) -> Status:
    """Build a ``Status`` from a statusline payload.

    Args:
        data (Any): Parsed JSON payload — usually a dict, but any JSON value
            is tolerated; every field is junk-tolerant.

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
