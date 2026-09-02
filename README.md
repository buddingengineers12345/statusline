# statusline

![Made with Claude](https://img.shields.io/badge/Made%20with-Claude-D97757?logo=claude&logoColor=white)

A minimal, column-aligned Claude Code statusline — mascot, session state, and usage bars in three vertically-aligned columns.

## About

A Claude Code statusline is a small local script wired into project or user
`settings.json` (`statusLine`). In **agentspace**, the SSOT is
`/home/engineer/agentspace/.claude/settings.json` pointing at
`statusline/grid.py` (this repo is the portable/testable copy).
Claude Code runs it on session updates, piping a JSON blob (model, effort,
context/rate-limit usage, cwd) to stdin and printing stdout above the input box.
It costs no API tokens — it's a local process, not a model call.

This repo ships the `statusline` package (src layout) plus a zero-install
`grid.py` launcher and `sample.json` to try it against.

## Features

- Aligned 3-column grid: braille mascot | labeled state | usage bars, with the `│` dividers staying vertical across all 5 rows
- Zero runtime deps — stdlib only
- Pytest suite in `tests/`

## Layout

```
pyproject.toml          # packaging + pytest + ruff config
grid.py                 # zero-install launcher (puts src/ on sys.path)
sample.json             # example stdin payload
src/statusline/
├── __init__.py         # public API (Status, extract_status_info, render_grid, ...)
├── __main__.py         # python3 -m statusline
├── config.py           # layout constants, labels, mascot, width tables
├── models.py           # Status / ContextUsage / RateLimitUsage
├── errors.py           # handle_exception decorator
├── parsing.py          # payload → Status
├── rendering.py        # Status → grid text
└── cli.py              # stdin/stdout entry point
tests/                  # test_parsing / test_rendering / test_cli
```

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

No install is needed: `grid.py` bootstraps `src/` onto `sys.path`. An optional
`pip install .` also provides a `statusline-grid` console script.

## Usage

```bash
python3 grid.py < sample.json          # zero-install launcher
PYTHONPATH=src python3 -m statusline < sample.json
python3 -m pytest tests/ -v            # pythonpath=src comes from pyproject.toml
```

## Fields read

| Field | Notes |
|---|---|
| `model.id` | default `?` |
| `effort.level` | live value when the model supports effort; else `$CLAUDE_EFFORT`, else project `.claude/settings.json` `effortLevel`, else `~/.claude/settings.json`, else `?` |
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
