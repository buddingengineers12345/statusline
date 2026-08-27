"""Tests for statusline.rendering: display width, bars, and grid assembly."""

from datetime import datetime

import pytest

from statusline import rendering
from statusline.config import BAR_WIDTH, EMPTY, FILL, LABELS, VS16
from statusline.models import RateLimitUsage, Status
from tests.helpers import assert_dividers_align


class TestDisplayWidth:
    def test_basic_latin_one_cell_per_char(self) -> None:
        assert rendering.display_width("hello") == 5

    def test_braille_patterns_one_cell_each(self) -> None:
        """MASCOT is braille — must stay 1 cell/char or columns drift."""
        assert rendering.display_width("⠤⢤⣤") == 3
        assert rendering.display_width("⠀") == 1

    def test_emoji_two_cells(self) -> None:
        assert rendering.display_width("🧠") == 2
        assert rendering.display_width("🧠🎉") == 4

    def test_symbol_block_and_vs16_still_two_cells(self) -> None:
        assert rendering.display_width("☀") == 2
        assert rendering.display_width("☀️") == 2

    def test_narrow_symbols_one_cell(self) -> None:
        """Gear/pencil are EAW=Neutral; LABELS bake compensating spaces for this."""
        assert rendering.display_width("✍") == 1
        assert rendering.display_width("⚙") == 1
        assert rendering.display_width("⚙️") == 1

    def test_east_asian_wide_char_two_cells(self) -> None:
        assert rendering.display_width("中") == 2
        assert rendering.display_width("日本") == 4

    def test_symbol_block_boundaries(self) -> None:
        """Inclusive U+2600, exclusive U+27C0 — off-by-one would mis-width labels."""
        assert rendering.display_width("☀") == 2
        assert rendering.display_width("➿") == 2
        assert rendering.display_width("⟀") == 1

    def test_combining_mark_and_vs16_zero_cells(self) -> None:
        assert rendering.display_width("é") == 1
        assert rendering.display_width("x" + VS16) == rendering.display_width("x")

    def test_empty_string_zero_width(self) -> None:
        assert rendering.display_width("") == 0


class TestLabelIconWidths:
    def test_all_icons_consume_equal_space(self) -> None:
        widths = {key: rendering.display_width(icon + " ") for key, (icon, _text) in LABELS.items()}
        assert len(set(widths.values())) == 1, widths


class TestPad:
    def test_pad_short_string_to_target_width(self) -> None:
        result = rendering.pad("hi", 5)
        assert result == "hi   "
        assert rendering.display_width(result) == 5

    def test_pad_already_at_or_over_width_unchanged(self) -> None:
        assert rendering.pad("hello", 5) == "hello"
        assert rendering.pad("hello world", 5) == "hello world"

    def test_pad_uses_display_width_not_len(self) -> None:
        assert rendering.pad("🧠", 5) == "🧠   "
        assert rendering.pad("⚙", 4) == "⚙   "  # narrow symbol, not emoji-wide

    def test_pad_nonpositive_width_unchanged(self) -> None:
        assert rendering.pad("test", 0) == "test"
        assert rendering.pad("test", -5) == "test"


class TestRenderBar:
    def test_endpoints_and_half(self) -> None:
        assert rendering.render_bar(0) == EMPTY * BAR_WIDTH
        assert rendering.render_bar(100) == FILL * BAR_WIDTH
        assert rendering.render_bar(50) == FILL * 5 + EMPTY * 5

    def test_clamps(self) -> None:
        assert rendering.render_bar(-50) == EMPTY * BAR_WIDTH
        assert rendering.render_bar(150) == FILL * BAR_WIDTH

    @pytest.mark.parametrize(
        "percent,expected_filled",
        [
            (10, 1),
            (15, 2),  # 1.5 → 2 (banker's round to even)
            (25, 2),  # 2.5 → 2
            (35, 4),  # 3.5 → 4
            (75, 8),
            (95, 10),
        ],
    )
    def test_bankers_rounding(self, percent: float, expected_filled: int) -> None:
        assert rendering.render_bar(percent).count(FILL) == expected_filled


class TestLimitRow:
    def test_clock_formatting(self) -> None:
        assert rendering._limit_row("5h", None, "%H:%M", 4) == ""
        bare = RateLimitUsage(percent=30, resets_at=None)
        assert "⏰" not in rendering._limit_row("5h", bare, "%H:%M", 4)
        timed = RateLimitUsage(percent=30, resets_at=datetime(2026, 8, 2, 15, 29, 0))
        assert "⏰ 15:29" in rendering._limit_row("5h", timed, "%H:%M", 4)
        assert "⏰ 08-02" in rendering._limit_row("7d", timed, "%m-%d", 4)


class TestRenderGrid:
    def test_dividers_align_sample_and_default(
        self, sample_status: Status, default_status: Status
    ) -> None:
        assert_dividers_align(rendering.render_grid(sample_status).split("\n"))
        lines = rendering.render_grid(default_status).split("\n")
        assert len(lines) == 5
        assert_dividers_align(lines)

    def test_dividers_align_when_state_column_grows(self) -> None:
        status = Status(model="claude-opus-4-8-20240101-extremely-long-model-name")
        lines = rendering.render_grid(status).split("\n")
        assert_dividers_align(lines)
        assert status.model in lines[0]

    def test_missing_rate_limits_leave_empty_usage_cells(self) -> None:
        lines = rendering.render_grid(Status(model="x")).split("\n")
        assert len(lines) == 5
        for i in (1, 2):
            assert lines[i].count("│") == 2

    def test_long_cwd_not_truncated(self) -> None:
        path = "/very/long/path/to/working/directory/for/testing"
        assert path in rendering.render_grid(Status(cwd=path))

    def test_snapshot_known_status(self, sample_status: Status) -> None:
        lines = rendering.render_grid(sample_status).split("\n")
        assert len(lines) == 5
        assert "claude-opus-4-8" in lines[0]
        assert "high" in lines[1]
        assert "on" in lines[2]
        assert "concise" in lines[3]
        assert "off" in lines[4] and "demo" in lines[4]
        assert "⏰ 15:29" in "\n".join(lines)
        assert "⏰ 08-05" in "\n".join(lines)

    def test_extreme_lengths_keep_alignment(self) -> None:
        status = Status(
            model="m" * 4000,
            cwd="/" + "/".join(f"s{i}" for i in range(200)),
            five_hour=RateLimitUsage(percent=99, resets_at=datetime(2026, 1, 1)),
        )
        lines = rendering.render_grid(status).split("\n")
        assert len(lines) == 5
        assert_dividers_align(lines)

    def test_wide_unicode_fields_keep_alignment(self) -> None:
        status = Status(model="🤖-模型", effort="高", cwd="/home/中文/目录")
        lines = rendering.render_grid(status).split("\n")
        assert len(lines) == 5
        assert_dividers_align(lines)
