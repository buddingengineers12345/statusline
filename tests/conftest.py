"""Pytest configuration and fixtures for statusline tests.

This module handles imports and provides shared fixtures for all tests.
Since grid.py is not installed as a package, we insert the parent directory
into sys.path to allow imports.
"""

import sys
from pathlib import Path

# Add parent directory to sys.path so we can import grid module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import grid module early so it's available for fixtures
import pytest

import grid


@pytest.fixture
def sample_status():
    """A fully-populated Status object for testing."""
    from datetime import datetime

    return grid.Status(
        model="claude-opus-4-8",
        effort="high",
        thinking="on",
        style="concise",
        fast="off",
        context=grid.ContextUsage(percent=42),
        five_hour=grid.RateLimitUsage(percent=30, resets_at=datetime(2026, 8, 2, 15, 29, 0)),
        seven_day=grid.RateLimitUsage(percent=68, resets_at=datetime(2026, 8, 5, 0, 0, 0)),
        cwd="/tmp/demo",
    )


@pytest.fixture
def default_status():
    """A Status with all defaults."""
    return grid.Status()
