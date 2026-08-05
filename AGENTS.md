# AGENTS.md — statusline

> Canonical, model-agnostic agent guide. CLAUDE.md / GEMINI.md / CURSOR.md are thin wrappers that
> point here. Edit shared knowledge in THIS file only.

statusline is a minimal, column-aligned Claude Code statusline: braille mascot, session state, and usage bars in three vertically aligned columns. Claude Code runs the script once per prompt (JSON on stdin → plain text on stdout). It is a local process, not a model call.

## Setup commands

```bash
python3 grid.py < sample.json
python3 -m pytest tests/ -v
```

Wire into Claude Code via `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/statusline/grid.py",
    "refreshInterval": 30
  }
}
```

## Code style

- Keep `grid.py` stdlib-only (`json`, `os`, `pathlib`, `unicodedata`, `datetime`); no new runtime deps.
- Pad columns by **display width** (emoji = 2, braille = 1, VS16/combining = 0, gear/pencil = 1), not string length.
- Prefer self-evident code over comments that only restate the code.

## Dev environment tips

- `grid.py`: Python ≥ 3.10, stdlib only.
- Statusline stdout is not a TTY — do not use `tput cols`.
- Contract: one JSON object on stdin, no network, no args required for normal render.
- Effort resolution order: `effort.level` → `$CLAUDE_EFFORT` → settings `effortLevel` → `?`.

## Testing instructions

```bash
python3 -m pytest tests/ -v
python3 grid.py < sample.json
```

## PR instructions

- Do not commit generated noise (`__pycache__`, `.ruff_cache`); this repo is `grid.py` + `sample.json` + `tests/` + docs.
- Prefer small diffs; document gotchas (emoji width, effort fallback, absent rate-limit fields) when behavior changes.
- Conventional commits; squash-merge to the default branch.

## Behavioral guidelines

- This repo is **only** the statusline script — not the agentspace workspace router.
- Do not invent installers, skills, or unrelated tooling.
- Prefer surgical edits; preserve the stdin/stdout contract.
- Do not keep `backup.py` / duplicate sample payloads in tree.
