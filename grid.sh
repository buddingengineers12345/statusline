#!/usr/bin/env bash
# Column-aligned grid statusline for Claude Code — bash/jq port of grid.py.
#
# Reads statusline JSON on stdin, prints the same 3-column grid as grid.py:
# mascot | state | usage. Byte-identical stdout to `python3 grid.py` for the
# same input (verify with `diff <(python3 grid.py < x) <(bash grid.sh < x)`).
#
# All label strings below are FIXED constants, so their display widths
# (emoji=2 cells, braille=1, VS16=0) are precomputed once by hand/python
# rather than reimplemented in bash. Only the data-dependent values
# (model id, effort level, style name) need runtime width — done via jq's
# `explode`, mirroring grid.py's display_width() classification.
#
# `bash grid.sh --selfcheck` validates bar()/reset_time()/dw().
set -euo pipefail

GRAY=$'\033[90m'; WHITE=$'\033[97m'; RESET=$'\033[0m'
DIV="${GRAY}│${RESET}"
FILL="█"; EMPTY="░"

# --- precomputed constants (see grid.py's MASCOT / names / labels) --------
MASCOT=(
  '⠤⢤⣤⣤⣤⣤⣤⣤⠀⠀⢰⣀⡆⠀⠀⢠⣤⣤⣤⣤⣤⣤⡤⠤⠀'
  '⠀⠀⠛⣿⣿⣿⣿⣿⣷⣤⣼⣿⣧⣤⣤⣾⣿⣿⣿⣿⣿⠛⠀⠀⠀'
  '⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀'
  '⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀'
  '⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀'
)
# w0 = max mascot display width; every line above is already 25 wide, so no
# per-line padding is needed (pad(MASCOT[i], w0) is a no-op here).

# Col-1 name+colon prefixes, pre-padded to wname=15 (max name width + 4).
PREFIX_MODEL='🤖 Model       : '
PREFIX_EFFORT='⚙️ Effort      : '
PREFIX_EXT='🧠 Extended    : '
PREFIX_STYLE='✍  Style       : '
PREFIX_FAST='⚡ Fast        : '
PREFIX_W=17  # wname(15) + ": " (2)

# Col-2 usage-row labels, pre-padded to wlab=10 (max label width).
LBL_CONTEXT='📊 Context'
LBL_5H='⏳ 5h     '
LBL_7D='📅 7d     '

W1_FLOOR=26

DW_FILTER='
def dw:
  (explode | map(
      if . == 65039 then 0
      elif . == 9997 then 1
      elif . >= 126976 then 2
      elif . >= 9728 and . <= 10175 then 2
      else 1
      end
    ) | add) // 0;
$s | dw
'

FIELD_FILTER='
def pyfalse:
  if . == null or . == false or . == 0 or . == "" or . == [] or . == {}
  then false else . end;
def go(k; default): ((.[k] | pyfalse) // default);
def onoff:
  if . == null or . == false or . == 0 or . == "" or . == [] or . == {}
  then "off" else "on" end;
def dw:
  (explode | map(
      if . == 65039 then 0
      elif . == 9997 then 1
      elif . >= 126976 then 2
      elif . >= 9728 and . <= 10175 then 2
      else 1
      end
    ) | add) // 0;
def s: if . == null then "" elif type == "string" then . else tostring end;
. as $d
| ($d | go("model"; {})) as $model
| ($model | go("id"; "?")) as $model_id
| ($d | go("effort"; {})) as $effort
| ($effort | go("level"; "?")) as $effort_level
| ($d.thinking.enabled | onoff) as $thinking
| ($d | go("output_style"; {})) as $ostyle
| ($ostyle | go("name"; "default")) as $style_name
| ($d.fast_mode | onoff) as $fast
| ($d | go("context_window"; {})) as $cw
| ($cw | go("used_percentage"; 0)) as $cw_pct
| ($d | go("rate_limits"; {})) as $rl
| ($rl.five_hour // {}) as $h5raw
| ($h5raw | pyfalse) as $h5f
| (if $h5f == false then {} else $h5f end) as $h5
| ($h5 != {}) as $h5_present
| ($h5 | go("used_percentage"; 0)) as $h5_pct
| ($h5.resets_at) as $h5_resets
| ($rl.seven_day // {}) as $d7raw
| ($d7raw | pyfalse) as $d7f
| (if $d7f == false then {} else $d7f end) as $d7
| ($d7 != {}) as $d7_present
| ($d7 | go("used_percentage"; 0)) as $d7_pct
| ($d7.resets_at) as $d7_resets
| ($d | go("cwd"; false)) as $cwd1
| (if $cwd1 == false then (($d.workspace // {}) | go("current_dir"; "?")) else $cwd1 end) as $cwd
| [$model_id, $effort_level, $thinking, $style_name, $fast,
   $cw_pct, ($h5_present|tostring), $h5_pct, $h5_resets,
   ($d7_present|tostring), $d7_pct, $d7_resets, $cwd,
   ($model_id|dw), ($effort_level|dw), ($style_name|dw)]
| map(s) | join("")
'
# fields joined with \x1f (unit separator), not tab: bash `read` collapses
# runs of IFS *whitespace* chars (tab included) and drops empty fields —
# \x1f is non-blank so empty fields (e.g. missing resets_at) survive intact.

dw() { jq -rn --arg s "$1" "$DW_FILTER"; }

# round-half-to-even, mirrors Python's round(pct/100*10) for integer pct 0-100
bar_fill_count() {
  local pct=$1 q r n
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  q=$(( pct / 10 )); r=$(( pct % 10 ))
  if (( r < 5 )); then n=$q
  elif (( r > 5 )); then n=$((q + 1))
  elif (( q % 2 == 0 )); then n=$q
  else n=$((q + 1))
  fi
  printf '%d' "$n"
}

bar() {
  local n=$(bar_fill_count "$1") i out=""
  for ((i = 0; i < n; i++)); do out+="$FILL"; done
  for ((i = n; i < 10; i++)); do out+="$EMPTY"; done
  printf '%s' "$out"
}

reset_time() {
  local v="$1" fmt="$2" out
  [ -z "$v" ] && return 0
  if [[ "$v" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
    out=$(date -d "@${v%%.*}" +"$fmt" 2>/dev/null) || out=""
  else
    out=$(date -d "${v:0:19}" +"$fmt" 2>/dev/null) || out=""
  fi
  printf '%s' "$out"
}

usage_row() {
  local label="$1" pct="$2" clock="$3" cell
  cell="${label}   $(bar "$pct")   $(printf '%3d' "$pct")%"
  if [ -n "$clock" ]; then
    printf '%s   ⏰ %s' "$cell" "$clock"
  else
    printf '%s' "$cell"
  fi
}

selfcheck() {
  [ "$(bar 50)" = "█████░░░░░" ] || { echo "bar(50) failed" >&2; exit 1; }
  [ "$(bar 0)" = "░░░░░░░░░░" ] || { echo "bar(0) failed" >&2; exit 1; }
  [ "$(bar 100)" = "██████████" ] || { echo "bar(100) failed" >&2; exit 1; }
  [ "$(bar_fill_count 25)" = "2" ] || { echo "round-half-even 2.5->2 failed" >&2; exit 1; }
  [ "$(bar_fill_count 75)" = "8" ] || { echo "round-half-even 7.5->8 failed" >&2; exit 1; }
  [ -n "$(reset_time 0 %m-%d)" ] || { echo "reset_time failed" >&2; exit 1; }
  [ "$(dw '⠀')" = "1" ] || { echo "dw braille failed" >&2; exit 1; }
  [ "$(dw '🧠')" = "2" ] || { echo "dw emoji failed" >&2; exit 1; }
  [ "$(dw '⚙️')" = "2" ] || { echo "dw emoji+VS16 failed" >&2; exit 1; }
  [ "$(dw 'abc')" = "3" ] || { echo "dw ascii failed" >&2; exit 1; }
  echo "selfcheck ok"
}

if [[ "${1:-}" == "--selfcheck" ]]; then
  selfcheck
  exit 0
fi

json="$(cat)"
jq -e . >/dev/null 2>&1 <<<"$json" || json='{}'

IFS=$'\x1f' read -r model_id effort_level thinking style_name fast_mode \
  cw_pct_raw h5_present h5_pct_raw h5_resets \
  d7_present d7_pct_raw d7_resets cwd \
  dw_model dw_effort dw_style \
  <<<"$(jq -r "$FIELD_FILTER" <<<"$json")"

cw_pct=${cw_pct_raw%%.*}
h5_pct=${h5_pct_raw%%.*}
d7_pct=${d7_pct_raw%%.*}

left=(
  "${PREFIX_MODEL}${model_id}"
  "${PREFIX_EFFORT}${effort_level}"
  "${PREFIX_EXT}${thinking}"
  "${PREFIX_STYLE}${style_name}"
  "${PREFIX_FAST}${fast_mode}"
)
left_dw=(
  $(( PREFIX_W + dw_model ))
  $(( PREFIX_W + dw_effort ))
  $(( PREFIX_W + ${#thinking} ))
  $(( PREFIX_W + dw_style ))
  $(( PREFIX_W + ${#fast_mode} ))
)

w1=$W1_FLOOR
for w in "${left_dw[@]}"; do (( w > w1 )) && w1=$w; done

right=(
  "$(usage_row "$LBL_CONTEXT" "$cw_pct" "")"
  ""
  ""
  ""
  "📁 ${cwd}"
)
if [ "$h5_present" = "true" ]; then
  right[1]="$(usage_row "$LBL_5H" "$h5_pct" "$(reset_time "$h5_resets" "%H:%M")")"
fi
if [ "$d7_present" = "true" ]; then
  right[2]="$(usage_row "$LBL_7D" "$d7_pct" "$(reset_time "$d7_resets" "%m-%d")")"
fi

for i in 0 1 2 3 4; do
  m="${GRAY}${MASCOT[$i]}${RESET}"
  pad_n=$(( w1 - left_dw[i] ))
  spaces=""
  if (( pad_n > 0 )); then
    spaces="$(printf '%*s' "$pad_n" '')"
  fi
  l="${WHITE}${left[$i]}${spaces}${RESET}"
  r=""
  [ -n "${right[$i]}" ] && r="${WHITE}${right[$i]}${RESET}"
  line="${m}   ${DIV}   ${l}   ${DIV}   ${r}"
  printf '%s\n' "$line" | sed -e 's/[[:space:]]*$//'
done
