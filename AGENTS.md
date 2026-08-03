# AGENTS.md — statusline

> Canonical, model-agnostic agent guide. CLAUDE.md / GEMINI.md / CURSOR.md are thin wrappers that
> point here. Edit shared knowledge in THIS file only.

statusline is a minimal, column-aligned Claude Code statusline: braille mascot, session state, and usage bars in three vertically aligned columns. Claude Code runs the script once per prompt (JSON on stdin → plain text/ANSI on stdout). It is a local process, not a model call.

## Setup commands

```bash
# render against sample payload
python3 grid.py < sample.json
bash grid.sh < sample.json

# self-check without a payload
python3 grid.py --selfcheck
bash grid.sh --selfcheck
```

Wire into Claude Code via `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/statusline/grid.py"
  }
}
```

Use `bash /path/to/statusline/grid.sh` for the bash/jq port (byte-identical output).

## Code style

- Keep `grid.py` stdlib-only (`json`, `time`, `unicodedata`); no new runtime deps.
- Keep `grid.sh` output byte-identical to `grid.py` for the same payload.
- Pad columns by **display width** (emoji = 2 cells, braille = 1, variation selectors = 0), not string length.
- Match Python banker's rounding in bash via `jq`'s `rint`.

## Dev environment tips

- `grid.py`: Python ≥ 3.10, stdlib only.
- `grid.sh`: bash ≥ 4.2, `jq` ≥ 1.6, GNU `date`.
- Statusline stdout is not a TTY — do not use `tput cols`; use `$COLUMNS` if width-aware output is needed.
- Contract: one JSON object on stdin, no network, no args required for normal render.

## Testing instructions

```bash
python3 grid.py --selfcheck
bash grid.sh --selfcheck
python3 grid.py < sample.json
bash grid.sh < sample.json
# Prefer comparing both implementations on the same payload when changing layout/width logic.
```

## PR instructions

- Keep both implementations in sync when changing fields, layout, or width math.
- Do not commit generated noise; this repo is the scripts + `sample.json` + README.
- Prefer small diffs; document gotchas (emoji width, absent vs null rate-limit fields) when behavior changes.

## Behavioral guidelines

- This repo is **only** the statusline scripts — not the agentspace workspace router. Do not write agentspace-root docs here.
- Do not invent installers, skills, or unrelated tooling.
- Prefer surgical edits; preserve the stdin/stdout contract.
