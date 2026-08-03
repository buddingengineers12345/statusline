#!/usr/bin/env bash
# grid.sh — column-aligned grid statusline for Claude Code (bash twin of grid.py).
#
# Reads a statusline JSON payload on stdin and prints a 5-line, 3-column ANSI
# grid: mascot | session state | usage bars. Output is byte-identical to
# `python3 grid.py` on the same input for realistic payloads (see README):
#
#     diff <(python3 grid.py < payload.json) <(bash grid.sh < payload.json)
#
# Usage:
#     bash grid.sh < payload.json
#     bash grid.sh --selfcheck
#
# Dependencies: bash >= 4.2 (printf '%()T'), jq >= 1.6 (rint, $ARGS),
# GNU date (only for ISO-8601 resets_at values).
#
# Design: every Unicode display-width computation lives in ONE jq library
# (JQ_LIB), used by a single jq invocation that extracts, measures, and
# pre-pads all data-dependent fields. Bash never counts display cells; it
# only formats clocks, builds bars from jq-computed fill counts, and
# assembles the lines. Malformed JSON falls back to the all-defaults grid.

set -euo pipefail
shopt -s extglob # for trailing-whitespace trimming in render()

# ---------------------------------------------------------------------------
# Rendering constants (grid.py mirrors these: keep the two files in sync)
# ---------------------------------------------------------------------------

readonly GRAY=$'\033[90m' WHITE=$'\033[97m' RESET=$'\033[0m'
readonly DIV="${GRAY}│${RESET}"

readonly BAR_W=10       # usage bar cells
readonly FILL='█' EMPTY='░'
readonly STATE_MIN_W=26 # column-2 floor; grows for long values

# Braille-art mascot, one string per output row. Braille chars are 1 cell
# each, so a line's char count IS its display width (used in render()).
readonly -a MASCOT=(
    '⠤⢤⣤⣤⣤⣤⣤⣤⠀⠀⢰⣀⡆⠀⠀⢠⣤⣤⣤⣤⣤⣤⡤⠤⠀'
    '⠀⠀⠛⣿⣿⣿⣿⣿⣷⣤⣼⣿⣧⣤⣤⣾⣿⣿⣿⣿⣿⠛⠀⠀⠀'
    '⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀'
    '⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀'
    '⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀'
)

# Column-2 row labels. ✍ carries TWO trailing spaces because it renders
# 1 cell wide (tmux), unlike the 2-cell emoji on the other rows.
readonly -a STATE_NAMES=('🤖 Model' '⚙️ Effort' '🧠 Extended' '✍  Style' '⚡ Fast')

# Column-3 row labels.
readonly -a USAGE_LABELS=('📊 Context' '⏳ 5h' '📅 7d')

# Bar atoms: BAR_W repetitions of FILL / EMPTY, sliced per row in usage_row().
BAR_FULL='' BAR_EMPTY=''
for ((_i = 0; _i < BAR_W; _i++)); do BAR_FULL+="$FILL"; BAR_EMPTY+="$EMPTY"; done
readonly BAR_FULL BAR_EMPTY
unset _i

# ---------------------------------------------------------------------------
# jq library — the single home of all display-width and truthiness logic
# ---------------------------------------------------------------------------
#
# dw mirrors grid.py's display_width(): VS16/combining marks = 0 cells,
# ✍ = 1, emoji and East-Asian Wide/Fullwidth = 2, everything else 1. The
# EAW and combining sets are block-range approximations of Python's
# unicodedata tables.
# ponytail: covers CJK/Hangul/fullwidth/common combining blocks; exotic
# codepoints may drift a cell — grid.py's unicodedata is ground truth.
#
# pyfalse/pyor replicate Python truthiness (`x or default`): null, false,
# 0, "", [], {} all count as absent — jq's own // treats only null/false so.
# shellcheck disable=SC2016  # $-names below are jq bindings, not shell vars
readonly JQ_LIB='
def dw:
  [ explode[]
    | if . == 65039 then 0                                # VS16
      elif (. >= 768 and . <= 879)
        or (. >= 6832 and . <= 6911)
        or (. >= 7616 and . <= 7679)
        or (. >= 8400 and . <= 8447)
        or (. >= 65056 and . <= 65071) then 0             # combining marks
      elif . == 9997 then 1                               # ✍: tmux renders narrow
      elif . == 8986 or . == 8987
        or (. >= 9193 and . <= 9196)
        or . == 9200 or . == 9203 then 2                  # ⌚⌛⏩-⏬⏰⏳ (EAW Wide)
      elif . >= 126976 then 2                             # emoji / astral planes
      elif . >= 9728 and . <= 10175 then 2                # U+2600-U+27BF symbols
      elif (. >= 4352 and . <= 4447)
        or (. >= 11904 and . <= 42191)
        or (. >= 44032 and . <= 55203)
        or (. >= 63744 and . <= 64255)
        or (. >= 65072 and . <= 65103)
        or (. >= 65281 and . <= 65376)
        or (. >= 65504 and . <= 65510) then 2             # CJK / fullwidth (EAW W/F)
      else 1
      end
  ] | add // 0;
def pyfalse: . == null or . == false or . == 0 or . == "" or . == [] or . == {};
def pyor(alt): if pyfalse then alt else . end;
def s: if . == null then "" elif type == "string" then . else tostring end;
def pad($w): . + ((" " * ($w - dw)) // "");
def toint:                                        # int(float(x)); junk -> 0
  (tonumber? // 0)
  | if isnan then 0
    elif . < 0 then 0 - ((0 - .) | floor)         # truncate toward zero
    else floor
    end;
def fillcount($w):                                # bar cells: clamp + rint
  (if . < 0 then 0 elif . > 100 then 100 else . end) / 100 * $w | rint;
def onoff: if pyfalse then "off" else "on" end;
'

# Extracts everything the grid needs in ONE jq pass. Emits 19 \x1f-joined
# values, in exactly the order render()'s read consumes them:
#   1-5   column-2 rows, fully padded to the state-column width
#   6-8   column-3 labels, padded to the label width
#   9-10  context: pct, bar-fill count
#   11-14 five_hour: present, pct, fill, raw resets_at
#   15-18 seven_day: present, pct, fill, raw resets_at
#   19    cwd
# shellcheck disable=SC2016  # $-names below are jq bindings, not shell vars
readonly FIELD_FILTER="$JQ_LIB"'
def val($k; $sub; $dflt): (.[$k] | pyor({})) | (.[$sub] | pyor($dflt)) | s;
def limitrow($k):
  (.[$k] | pyor({}))
  | { present: (pyfalse | not),
      pct: (.used_percentage | pyor(0) | toint),
      resets: (.resets_at | s) };

. as $d
| $ARGS.positional[0:5] as $names
| $ARGS.positional[5:8] as $labels
| (([$names[] | dw] | max) + 4) as $name_w
| [ ($d | val("model"; "id"; "?")),
    ($d | val("effort"; "level"; "?")),
    ($d.thinking | pyor({}) | .enabled | onoff),
    ($d | val("output_style"; "name"; "default")),
    ($d.fast_mode | onoff) ] as $vals
| [ range(5) | ($names[.] | pad($name_w)) + ": " + $vals[.] ] as $rows
| (([$rows[] | dw] + [$minw]) | max) as $state_w
| ([$labels[] | dw] | max) as $label_w
| ($d.context_window | pyor({}) | .used_percentage | pyor(0) | toint) as $cw_pct
| ($d.rate_limits | pyor({})) as $rl
| ($rl | limitrow("five_hour")) as $h5
| ($rl | limitrow("seven_day")) as $d7
| ($d.cwd | pyor(($d.workspace | pyor({}) | .current_dir) | pyor("?")) | s) as $cwd
| [ ($rows[] | pad($state_w)),
    ($labels[] | pad($label_w)),
    $cw_pct, ($cw_pct | fillcount($barw)),
    $h5.present, $h5.pct, ($h5.pct | fillcount($barw)), $h5.resets,
    $d7.present, $d7.pct, ($d7.pct | fillcount($barw)), $d7.resets,
    $cwd ]
| map(s) | join("")
'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# extract <json> — run FIELD_FILTER over a payload; stdout is the \x1f record.
extract() {
    jq -r --argjson barw "$BAR_W" --argjson minw "$STATE_MIN_W" \
        --args "$FIELD_FILTER" "${STATE_NAMES[@]}" "${USAGE_LABELS[@]}" \
        <<<"$1" 2>/dev/null
}

# reset_time <raw-resets_at> <strftime-fmt> — sets REPLY to the local-time
# clock string, or '' when the value is absent/unparseable (clock hidden).
# Mirrors grid.py: epoch seconds (int/float; JSON true/false coerce to 1/0
# like Python float(True)) or strict ISO-8601 YYYY-MM-DDTHH:MM:SS (any
# extra suffix ignored).
reset_time() {
    local v=$1 fmt=$2
    REPLY=''
    if [[ -z $v ]]; then return 0; fi
    if [[ $v == true ]]; then v=1; fi
    if [[ $v == false ]]; then v=0; fi
    if [[ $v =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
        if [[ $v == -* ]]; then
            # printf '%()T' treats -1/-2 as "now"/"shell start"; use date.
            REPLY=$(date -d "@${v%%.*}" +"$fmt" 2>/dev/null) || REPLY=''
        else
            printf -v REPLY "%($fmt)T" "${v%%.*}"
        fi
    elif [[ ${v:0:19} =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
        REPLY=$(date -d "${v:0:19}" +"$fmt" 2>/dev/null) || REPLY=''
    fi
}

# usage_row <padded-label> <pct> <fill> <clock> — sets REPLY to one
# "[label]   [bar]   [pct]%[   ⏰ clock]" row. No subshells.
usage_row() {
    local bar="${BAR_FULL:0:$3}${BAR_EMPTY:0:BAR_W - $3}"
    printf -v REPLY '%s   %s   %3d%%' "$1" "$bar" "$2"
    if [[ -n $4 ]]; then
        REPLY+="   ⏰ $4"
    fi
}

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

render() {
    local json out
    json=$(cat)
    out=$(extract "$json") || out=$(extract '{}')

    # \x1f (unit separator) join: unlike whitespace IFS, bash read neither
    # collapses runs of it nor drops empty fields, so absent values (e.g. a
    # missing resets_at) keep every later field in its slot.
    local l0 l1 l2 l3 l4 ul0 ul1 ul2 cw_pct cw_fill \
        h5_present h5_pct h5_fill h5_resets \
        d7_present d7_pct d7_fill d7_resets cwd
    IFS=$'\x1f' read -r l0 l1 l2 l3 l4 ul0 ul1 ul2 cw_pct cw_fill \
        h5_present h5_pct h5_fill h5_resets \
        d7_present d7_pct d7_fill d7_resets cwd <<<"$out"

    local left=("$l0" "$l1" "$l2" "$l3" "$l4")
    local right=('' '' '' '' '')
    local clock

    usage_row "$ul0" "$cw_pct" "$cw_fill" ''
    right[0]=$REPLY
    if [[ $h5_present == true ]]; then
        reset_time "$h5_resets" '%H:%M'
        clock=$REPLY
        usage_row "$ul1" "$h5_pct" "$h5_fill" "$clock"
        right[1]=$REPLY
    fi
    if [[ $d7_present == true ]]; then
        reset_time "$d7_resets" '%m-%d'
        clock=$REPLY
        usage_row "$ul2" "$d7_pct" "$d7_fill" "$clock"
        right[2]=$REPLY
    fi
    right[4]="📁 ${cwd}"

    # Mascot column width: braille chars are 1 cell, so char count == width.
    local mascot_w=0 m
    for m in "${MASCOT[@]}"; do
        if ((${#m} > mascot_w)); then mascot_w=${#m}; fi
    done

    local i line spaces
    for ((i = 0; i < 5; i++)); do
        printf -v spaces '%*s' $((mascot_w - ${#MASCOT[i]})) ''
        line="${GRAY}${MASCOT[i]}${spaces}${RESET}   ${DIV}   ${WHITE}${left[i]}${RESET}   ${DIV}   "
        if [[ -n ${right[i]} ]]; then
            line+="${WHITE}${right[i]}${RESET}"
        fi
        line="${line%%*([[:space:]])}" # rstrip, no sed fork
        printf '%s\n' "$line"
    done
}

# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

selfcheck() {
    local got

    got=$(jq -rn "$JQ_LIB"'
        [("⠀"|dw), ("🧠"|dw), ("⚙️"|dw), ("abc"|dw), ("中"|dw), ("✍"|dw), ("⏳"|dw), ("é"|dw)]
        | map(tostring) | join(" ")')
    if [[ $got != '1 2 2 3 2 1 2 1' ]]; then
        echo "selfcheck FAIL: dw table ($got)"
        exit 1
    fi

    # Round-half-to-even via jq rint, matching Python round(): 45->4, 55->6.
    got=$(jq -rn --argjson barw "$BAR_W" "$JQ_LIB"'
        [0, 45, 55, 75, 100, 150, -5] | map(fillcount($barw) | tostring) | join(" ")')
    if [[ $got != '0 4 6 8 10 10 0' ]]; then
        echo "selfcheck FAIL: fillcount ($got)"
        exit 1
    fi

    reset_time 0 '%m-%d'
    if [[ -z $REPLY ]]; then
        echo 'selfcheck FAIL: reset_time epoch'
        exit 1
    fi
    reset_time '2026-08-02 13:45:00' '%H:%M'
    if [[ -n $REPLY ]]; then
        echo 'selfcheck FAIL: reset_time must reject non-ISO strings'
        exit 1
    fi

    echo 'selfcheck ok'
}

main() {
    if [[ ${1:-} == '--selfcheck' ]]; then
        selfcheck
        return 0
    fi
    render
}

main "$@"
