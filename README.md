# statusline

![Made with Claude](https://img.shields.io/badge/Made%20with-Claude-D97757?logo=claude&logoColor=white)

A minimal, column-aligned Claude Code statusline — mascot, session state, and usage bars in three vertically-aligned columns.

## About

A Claude Code statusline is a small local script wired into `~/.claude/settings.json`. Claude Code runs it once per prompt, piping a JSON blob (model, effort, context/rate-limit usage, cwd) to its stdin and printing whatever it writes to stdout above the input box. It costs no API tokens — it's a local process, not a model call.

This repo ships two interchangeable implementations of the same statusline, `grid.py` and `grid.sh`, plus a sample payload to try them against.

## Features

- Aligned 3-column grid: braille mascot | labeled state | usage bars, with the `│` dividers staying vertical across all 5 rows
- `grid.py` is zero-dependency — stdlib only (`json`, `time`, `unicodedata`)
- `grid.sh` is a bash/`jq` port that produces byte-identical output to `grid.py`
- Both support `--selfcheck` to sanity-check their internals without needing a JSON payload

## How it works

- **Contract**: read one JSON object from stdin, print plain text (with ANSI color codes) to stdout. No arguments, no network calls.
- **Alignment trick**: terminal cells aren't 1-character-per-glyph. Emoji render 2 cells wide, braille dot-patterns render 1 cell wide, and variation selectors (like the `️` in `⚙️`) render 0 cells wide. Padding every column to a fixed *display width* — not string length — is what keeps the two `│` dividers lined up across all 5 rows even though each row mixes emoji and braille.
- `grid.sh` precomputes the display width of every fixed label at write-time (there's no reason to reimplement Unicode width tables in bash for constants) and only computes width at runtime for the handful of data-dependent values (model id, effort level, style name), via `jq`'s `explode`.

## Installation

Point Claude Code's `statusLine` setting at either script. Edit `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/statusline/grid.py"
  }
}
```

Swap in `bash /path/to/statusline/grid.sh` for the bash/`jq` version — same output, no Python required.

## Usage

```bash
# render the grid against the sample payload
python3 grid.py < sample.json
bash grid.sh < sample.json

# sanity-check internals (rounding, width helpers) without a payload
python3 grid.py --selfcheck
bash grid.sh --selfcheck
```

## Fields read

Both scripts read the same fields from the input JSON, with the same defaults when a field is absent:

- `model.id` (default `?`)
- `effort.level` (default `?`)
- `thinking.enabled` (default off)
- `output_style.name` (default `default`)
- `fast_mode` (default off)
- `context_window.used_percentage` (default 0)
- `rate_limits.five_hour.used_percentage` / `.resets_at` (row hidden entirely if `five_hour` is absent)
- `rate_limits.seven_day.used_percentage` / `.resets_at` (row hidden entirely if `seven_day` is absent)
- `cwd`, falling back to `workspace.current_dir` (default `?`)

## Gotchas

- Emoji count as 2 terminal cells — naive `len()`/`${#s}`-based padding will misalign the grid the moment a label has an emoji in it.
- The usage-bar fill count uses Python's banker's rounding (`round(2.5) == 2`, not 3) — `grid.sh` replicates round-half-to-even explicitly rather than the more common round-half-up.
- `grid.sh` needs `jq`; `grid.py` needs nothing beyond the stdlib.
- Some fields are absent rather than `null` depending on session state (e.g. no `rate_limits.seven_day` at all vs. `seven_day: {}`) — both scripts treat both cases as "hide this row."
- A statusline script's stdout is captured, not a TTY, so `tput cols` won't report terminal width. Read the `$COLUMNS` env var instead if you need width-aware output.

## License

MIT.
