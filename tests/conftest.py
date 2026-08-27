"""Shared fixtures for the statusline test suite.

The package is imported from ``src/`` via ``pythonpath = ["src"]`` in
``pyproject.toml`` — no ``sys.path`` manipulation needed here. Assertion
helpers live in ``tests/helpers.py``.
"""

from datetime import datetime

import pytest

from statusline import ContextUsage, RateLimitUsage, Status


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
