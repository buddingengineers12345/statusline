# AGENTS.md — statusline

> Canonical, model-agnostic agent guide. CLAUDE.md / GEMINI.md / CURSOR.md are thin wrappers that
> point here. Edit shared knowledge in THIS file only.

statusline is a minimal, column-aligned Claude Code statusline: braille mascot, session state, and usage bars in three vertically aligned columns. Claude Code runs the script once per prompt (JSON on stdin → plain text on stdout). It is a local process, not a model call.

The code is a src-layout package (`src/statusline/`: `config` / `models` / `errors` /
`parsing` / `rendering` / `cli`). `grid.py` at the repo root is a zero-install launcher
that puts `src/` on `sys.path` and calls `statusline.cli.main` — keep it that way; the
live Claude Code wiring invokes `python3 grid.py` directly with no venv.

## Setup commands

```bash
python3 grid.py < sample.json
python3 -m pytest tests/ -v      # pythonpath=src via pyproject.toml
```

Wire into Claude Code via the **project** settings (agentspace SSOT:
`/home/engineer/agentspace/.claude/settings.json`), not `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /home/engineer/agentspace/workspace_ops/status_line/grid.py",
    "refreshInterval": 30
  }
}
```

Live agentspace wiring uses `workspace_ops/status_line/grid.py` (this `statusline/`
repo is the portable/minimal copy for tests and standalone use).

## Code style

- Keep the package stdlib-only (`json`, `os`, `pathlib`, `unicodedata`, `datetime`); no new runtime deps.
- Module boundaries: constants in `config.py`, types in `models.py`, payload→Status in `parsing.py`, Status→text in `rendering.py`, stdin/stdout in `cli.py`. Don't let rendering read the payload or parsing touch widths.
- Pad columns by **display width** (emoji = 2, braille = 1, VS16/combining = 0, gear/pencil = 1), not string length.
- Prefer self-evident code over comments that only restate the code.

## Dev environment tips

- Python ≥ 3.10, stdlib only. Lint/format/pytest config lives in `pyproject.toml` (ruff section mirrors the workspace template).
- Statusline stdout is not a TTY — do not use `tput cols`.
- Contract: one JSON object on stdin, no network, no args required for normal render.
- Effort resolution order: `effort.level` → `$CLAUDE_EFFORT` → project
  `.claude/settings.json` `effortLevel` → `~/.claude/settings.json` → `?`.

## Testing instructions

```bash
python3 -m pytest tests/ -v
python3 grid.py < sample.json
```

## PR instructions

- Do not commit generated noise (`__pycache__`, `.ruff_cache`, `*.egg-info`); this repo is `src/statusline/` + `grid.py` + `sample.json` + `tests/` + docs.
- Prefer small diffs; document gotchas (emoji width, effort fallback, absent rate-limit fields) when behavior changes.
- Conventional commits; squash-merge to the default branch.

## Behavioral guidelines

- This repo is **only** the statusline script — not the agentspace workspace router.
- Do not invent installers, skills, or unrelated tooling.
- Prefer surgical edits; preserve the stdin/stdout contract.
- Do not keep `backup.py` / duplicate sample payloads in tree.
