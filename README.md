# statusline

![Made with Claude](https://img.shields.io/badge/Made%20with-Claude-D97757?logo=claude&logoColor=white)

A minimal, column-aligned Claude Code statusline — mascot, session state, and usage bars in three vertically-aligned columns.

## About

Claude Code runs a local script wired in `settings.json` (`statusLine`). It pipes session JSON to stdin and prints a grid to stdout — no API tokens.

Entry point: `src/main.py` (no pip install). `pyproject.toml` is for dev tooling (pytest, ruff) only.

## Installation

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/statusline/src/main.py",
    "refreshInterval": 30
  }
}
```

## Usage

```bash
python3 src/main.py --selfcheck
python3 src/main.py < assets/sample.json
python3 -m pytest tests/ -v
```

## Layout

```
assets/sample.json      # example stdin payload
src/main.py             # Claude Code entry point
src/statusline/         # config, parsing, rendering, cli
tests/
pyproject.toml          # pytest + ruff (dev only)
```

## Fields read

| Field | Notes |
|---|---|
| `model.id` | default `?` |
| `effort.level` | payload → `$CLAUDE_EFFORT` → project/user settings |
| `thinking.enabled` | only JSON `true` → `on` |
| `output_style.name` | default `default` |
| `fast_mode` | only JSON `true` → `on` |
| `context_window.used_percentage` | default 0 |
| `rate_limits.five_hour` / `seven_day` | blank if absent |
| `session_id`, `cwd` | row 4–5 in usage column |

## Gotchas

- Emoji and symbol-block icons (🤖 ⚙️) count as 2 cells; pencil (✍) counts as 1 with a space before and after in the Style label.
- Through a LiteLLM proxy, 5h/7d bars need bare `anthropic-ratelimit-*` headers forwarded to Claude Code.
- Bad stdin fails open (exit 0, empty defaults).
- Bar fill uses banker's rounding.

## License

MIT.
