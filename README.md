# statusline

![Made with Claude](https://img.shields.io/badge/Made%20with-Claude-D97757?logo=claude&logoColor=white)

A minimal, column-aligned Claude Code statusline — mascot, session state, and usage bars in three vertically-aligned columns.

## About

A Claude Code statusline is a small local script wired into `~/.claude/settings.json`. Claude Code runs it once per prompt, piping a JSON blob (model, effort, context/rate-limit usage, cwd) to its stdin and printing whatever it writes to stdout above the input box. It costs no API tokens — it's a local process, not a model call.

This repo ships `grid.py` plus `sample.json` to try it against.

## Features

- Aligned 3-column grid: braille mascot | labeled state | usage bars, with the `│` dividers staying vertical across all 5 rows
- Zero runtime deps — stdlib only
- Pytest suite in `tests/`

## How it works

- **Contract**: read one JSON object from stdin, print plain text to stdout. No arguments, no network calls.
- **Alignment**: pad columns by *display width* (emoji = 2 cells, braille = 1, VS16/combining = 0), not `len()`, so the two `│` dividers stay vertical across all 5 rows.

## Installation

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/statusline/grid.py",
    "refreshInterval": 30
  }
}
```

## Usage

```bash
python3 grid.py < sample.json
python3 -m pytest tests/ -v
```

## Fields read

| Field | Notes |
|---|---|
| `model.id` | default `?` |
| `effort.level` | live value when the model supports effort; else `$CLAUDE_EFFORT`, else `~/.claude/settings.json` `effortLevel`, else `?` |
| `thinking.enabled` | only actual JSON `true` → `on` |
| `output_style.name` | default `default` |
| `fast_mode` | only actual JSON `true` → `on` |
| `context_window.used_percentage` | default 0 |
| `rate_limits.five_hour` / `seven_day` | row blank if absent; supports epoch or ISO `resets_at` |
| `cwd` | falls back to `workspace.current_dir`, else `?` |

## Gotchas

- Haiku (and other models without the effort capability) omit `effort` from stdin — the grid falls back to settings/`$CLAUDE_EFFORT`.
- Emoji are 2 cells; gear/pencil are 1 cell despite VS16 — label icons compensate.
- Bar fill uses banker's rounding (`round(2.5) == 2`).
- Absent vs empty rate-limit objects both hide that usage row.
- Stdout is not a TTY — do not use `tput cols`; use `$COLUMNS` if needed.

## License

MIT.
