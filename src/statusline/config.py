"""Layout constants, labels, and Unicode width classification data."""

from __future__ import annotations

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
CP_NARROW_SYMBOLS = {0x2699, 0x270D}  # gear, pencil
CP_EMOJI_START = 0x1F000
CP_SYMBOL_BLOCK = range(0x2600, 0x27C0)
VS16 = "️"
