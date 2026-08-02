#!/usr/bin/env python3
"""Column-aligned grid statusline for Claude Code.

Reads statusline JSON on stdin, prints a 3-column grid: mascot | state | usage.
The two `│` dividers stay vertical because each column is padded to a fixed
*display* width (emoji = 2 terminal cells, braille = 1). ccstatusline can't do
this: it lays out each line independently, so its bars never align across rows.

`grid.py --selfcheck` validates display_width().
"""
import sys
import json
import time
import unicodedata

GRAY, WHITE, RESET = "\033[90m", "\033[97m", "\033[0m"
DIV = f"{GRAY}│{RESET}"
BAR_W = 10
FILL, EMPTY = "█", "░"
MASCOT = [
    "⠤⢤⣤⣤⣤⣤⣤⣤⠀⠀⢰⣀⡆⠀⠀⢠⣤⣤⣤⣤⣤⣤⡤⠤⠀",
    "⠀⠀⠛⣿⣿⣿⣿⣿⣷⣤⣼⣿⣧⣤⣤⣾⣿⣿⣿⣿⣿⠛⠀⠀⠀",
    "⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
]


def display_width(s):
    """Terminal cell width (emoji=2, braille=1, VS16/combining=0)."""
    w = 0
    for c in s:
        if c == "️" or unicodedata.combining(c):
            continue
        o = ord(c)
        if o == 0x270D:  # ✍ writing hand: tmux renders narrow despite Unicode range
            w += 1
        elif o >= 0x1F000 or 0x2600 <= o <= 0x27BF or unicodedata.east_asian_width(c) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def pad(s, width):
    return s + " " * max(0, width - display_width(s))


def bar(pct):
    try:
        pct = max(0.0, min(100.0, float(pct)))
    except (TypeError, ValueError):
        pct = 0.0
    n = round(pct / 100 * BAR_W)
    return FILL * n + EMPTY * (BAR_W - n)


def reset_time(v, fmt):
    """resets_at (epoch seconds or ISO string) -> formatted local time."""
    if v is None:
        return ""
    try:
        epoch = float(v)
    except (TypeError, ValueError):
        try:
            epoch = time.mktime(time.strptime(str(v)[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            return ""
    return time.strftime(fmt, time.localtime(epoch))


def pct_int(o):
    return int(float((o or {}).get("used_percentage") or 0))


def build(d):
    get = lambda k, sub, default="?": (d.get(k) or {}).get(sub) or default
    onoff = lambda v: "on" if v else "off"

    cw = d.get("context_window") or {}
    rl = d.get("rate_limits") or {}
    h5 = rl.get("five_hour") or {}
    d7 = rl.get("seven_day") or {}
    cwd = d.get("cwd") or (d.get("workspace") or {}).get("current_dir") or "?"

    # Col-1: pad icon+name so every colon aligns (+4 = colon further right).
    names = ["\U0001F916 Model", "⚙️ Effort", "\U0001F9E0 Extended", "✍  Style", "⚡ Fast"]
    vals = [get("model", "id"), get("effort", "level"),
            onoff((d.get("thinking") or {}).get("enabled")),
            get("output_style", "name", "default"), onoff(d.get("fast_mode"))]
    wname = max(display_width(n) for n in names) + 4
    left = [f"{pad(n, wname)}: {v}" for n, v in zip(names, vals)]

    # Col-2 mini-grid: [label][bar][pct][clock], fixed sub-widths so bars start
    # and end at the same column and clocks likewise.
    labels = ["\U0001F4CA Context", "⏳ 5h", "\U0001F4C5 7d"]
    wlab = max(display_width(x) for x in labels)

    def usage_row(label, pct, clock):
        cell = f"{pad(label, wlab)}   {bar(pct)}   {pct:>3}%"
        return f"{cell}   ⏰ {clock}" if clock else cell

    right = [
        usage_row(labels[0], pct_int(cw), ""),
        usage_row(labels[1], pct_int(h5), reset_time(h5.get("resets_at"), "%H:%M")) if h5 else "",
        usage_row(labels[2], pct_int(d7), reset_time(d7.get("resets_at"), "%m-%d")) if d7 else "",
        "",
        f"\U0001F4C1 {cwd}",
    ]

    w0 = max(display_width(m) for m in MASCOT)
    w1 = max(max(display_width(x) for x in left), 26)  # min keeps 2nd divider put; grows for long values
    out = []
    for i in range(5):
        m = f"{GRAY}{pad(MASCOT[i], w0)}{RESET}"
        l = f"{WHITE}{pad(left[i], w1)}{RESET}"
        r = f"{WHITE}{right[i]}{RESET}" if right[i] else ""
        out.append(f"{m}   {DIV}   {l}   {DIV}   {r}".rstrip())
    return "\n".join(out)


def selfcheck():
    assert display_width("⠀") == 1, "braille width"
    assert display_width("\U0001F9E0") == 2, "emoji width"
    assert display_width("⚙️") == 2, "emoji+VS16 width"
    assert display_width("abc") == 3, "ascii width"
    assert len(bar(50)) == BAR_W and bar(0) == EMPTY * BAR_W and bar(100) == FILL * BAR_W
    assert reset_time(0, "%m-%d")
    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    print(build(data))
