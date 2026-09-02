"""Column-aligned grid statusline for Claude Code (stdin JSON → stdout grid)."""

from __future__ import annotations

from statusline.models import ContextUsage, RateLimitUsage, Status
from statusline.parsing import extract_status_info
from statusline.rendering import display_width, pad, render_bar, render_grid

__version__ = "1.0.0"

__all__ = [
    "ContextUsage",
    "RateLimitUsage",
    "Status",
    "__version__",
    "display_width",
    "extract_status_info",
    "pad",
    "render_bar",
    "render_grid",
]
