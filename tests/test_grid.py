"""Pytest suite for statusline grid.py."""

from datetime import datetime
from io import StringIO

import pytest

import grid


def _divider_columns(line: str) -> list[int]:
    """Display-width column each ``grid.DIVIDER`` starts at, in order."""
    columns = []
    width = 0
    for part in line.split(grid.DIVIDER)[:-1]:
        width += grid.display_width(part)
        columns.append(width)
        width += grid.display_width(grid.DIVIDER)
    return columns


def _assert_dividers_align(lines: list[str]) -> None:
    columns_per_line = [_divider_columns(line) for line in lines]
    assert all(len(cols) == 2 for cols in columns_per_line), columns_per_line
    assert all(cols == columns_per_line[0] for cols in columns_per_line), columns_per_line


class TestDisplayWidth:
    def test_basic_latin_one_cell_per_char(self) -> None:
        assert grid.display_width("hello") == 5

    def test_braille_patterns_one_cell_each(self) -> None:
        """MASCOT is braille — must stay 1 cell/char or columns drift."""
        assert grid.display_width("⠤⢤⣤") == 3
        assert grid.display_width("⠀") == 1

    def test_emoji_two_cells(self) -> None:
        assert grid.display_width("🧠") == 2
        assert grid.display_width("🧠🎉") == 4

    def test_symbol_block_and_vs16_still_two_cells(self) -> None:
        assert grid.display_width("☀") == 2
        assert grid.display_width("☀️") == 2

    def test_narrow_symbols_one_cell(self) -> None:
        """Gear/pencil are EAW=Neutral; LABELS bake compensating spaces for this."""
        assert grid.display_width("✍") == 1
        assert grid.display_width("⚙") == 1
        assert grid.display_width("⚙️") == 1

    def test_east_asian_wide_char_two_cells(self) -> None:
        assert grid.display_width("中") == 2
        assert grid.display_width("日本") == 4

    def test_symbol_block_boundaries(self) -> None:
        """Inclusive U+2600, exclusive U+27C0 — off-by-one would mis-width labels."""
        assert grid.display_width("\u2600") == 2
        assert grid.display_width("\u27bf") == 2
        assert grid.display_width("\u27c0") == 1

    def test_combining_mark_and_vs16_zero_cells(self) -> None:
        assert grid.display_width("é") == 1
        assert grid.display_width("x" + grid._VS16) == grid.display_width("x")

    def test_empty_string_zero_width(self) -> None:
        assert grid.display_width("") == 0


class TestLabelIconWidths:
    def test_all_icons_consume_equal_space(self) -> None:
        widths = {key: grid.display_width(icon + " ") for key, (icon, _text) in grid.LABELS.items()}
        assert len(set(widths.values())) == 1, widths


class TestPad:
    def test_pad_short_string_to_target_width(self) -> None:
        result = grid.pad("hi", 5)
        assert result == "hi   "
        assert grid.display_width(result) == 5

    def test_pad_already_at_or_over_width_unchanged(self) -> None:
        assert grid.pad("hello", 5) == "hello"
        assert grid.pad("hello world", 5) == "hello world"

    def test_pad_uses_display_width_not_len(self) -> None:
        assert grid.pad("🧠", 5) == "🧠   "
        assert grid.pad("⚙", 4) == "⚙   "  # narrow symbol, not emoji-wide

    def test_pad_nonpositive_width_unchanged(self) -> None:
        assert grid.pad("test", 0) == "test"
        assert grid.pad("test", -5) == "test"


class TestRenderBar:
    def test_endpoints_and_half(self) -> None:
        assert grid.render_bar(0) == grid.EMPTY * grid.BAR_WIDTH
        assert grid.render_bar(100) == grid.FILL * grid.BAR_WIDTH
        assert grid.render_bar(50) == grid.FILL * 5 + grid.EMPTY * 5

    def test_clamps(self) -> None:
        assert grid.render_bar(-50) == grid.EMPTY * grid.BAR_WIDTH
        assert grid.render_bar(150) == grid.FILL * grid.BAR_WIDTH

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
        assert grid.render_bar(percent).count(grid.FILL) == expected_filled


class TestHandleException:
    def test_returns_fresh_copy_of_mutable_default(self) -> None:
        @grid.handle_exception({}, ValueError)
        def boom() -> dict:
            raise ValueError("nope")

        a, b = boom(), boom()
        a["x"] = 1
        assert b == {}


class TestAsDict:
    def test_dict_passthrough_else_empty(self) -> None:
        d = {"a": 1}
        assert grid._as_dict(d) is d
        assert grid._as_dict(None) == {}
        assert grid._as_dict("x") == {}


class TestNestedGet:
    def test_walks_nested_dicts(self) -> None:
        assert grid._nested_get({"a": {"b": {"c": 42}}}, ["a", "b", "c"]) == 42

    def test_missing_or_wrong_type_returns_default(self) -> None:
        assert grid._nested_get({"a": {}}, ["a", "b"], "fallback") == "fallback"
        assert grid._nested_get({"a": "not-dict"}, ["a", "b"], "fallback") == "fallback"
        assert grid._nested_get(None, ["a"], "fallback") == "fallback"

    def test_falsy_value_collapses_to_default(self) -> None:
        """Real 0 / '' / None / False are indistinguishable from missing."""
        for falsy in (0, "", None, False):
            assert grid._nested_get({"a": falsy}, ["a"], "default") == "default"


class TestProcessPercent:
    def test_int_and_float_truncate(self) -> None:
        assert grid.process_percent(42) == 42
        assert grid.process_percent(42.7) == 42
        assert grid.process_percent("42.5") == 42

    def test_clamps_to_0_100(self) -> None:
        assert grid.process_percent(-1) == 0
        assert grid.process_percent(101) == 100

    def test_junk_becomes_zero(self) -> None:
        assert grid.process_percent(None) == 0
        assert grid.process_percent("junk") == 0
        assert grid.process_percent("42%") == 0
        assert grid.process_percent(float("nan")) == 0
        assert grid.process_percent(float("inf")) == 0


class TestParseResetsAt:
    def test_epoch_int_and_string(self) -> None:
        ts = 1785665340
        assert int(grid._parse_resets_at(ts).timestamp()) == ts
        assert int(grid._parse_resets_at(str(ts)).timestamp()) == ts

    def test_iso_and_suffix_truncation(self) -> None:
        assert grid._parse_resets_at("2026-08-02T15:29:00") == datetime(2026, 8, 2, 15, 29, 0)
        assert grid._parse_resets_at("2026-08-02T15:29:00Z") == datetime(2026, 8, 2, 15, 29, 0)
        assert grid._parse_resets_at("2026-08-02T15:29:00.123456Z") == datetime(
            2026, 8, 2, 15, 29, 0
        )

    def test_unparseable_or_overflow_returns_none(self) -> None:
        assert grid._parse_resets_at("not a timestamp") is None
        assert grid._parse_resets_at(None) is None
        assert grid._parse_resets_at(10**20) is None


class TestParseLimit:
    def test_empty_or_non_dict_returns_none(self) -> None:
        assert grid._parse_limit(None) is None
        assert grid._parse_limit({}) is None
        assert grid._parse_limit([1]) is None

    def test_valid_with_and_without_reset(self) -> None:
        with_reset = grid._parse_limit({"used_percentage": 42, "resets_at": "2026-08-02T15:29:00"})
        assert with_reset == grid.RateLimitUsage(
            percent=42, resets_at=datetime(2026, 8, 2, 15, 29, 0)
        )
        bare = grid._parse_limit({"used_percentage": 30})
        assert bare == grid.RateLimitUsage(percent=30, resets_at=None)

    def test_missing_or_zero_percent_and_bad_reset(self) -> None:
        missing = grid._parse_limit({"resets_at": "2026-08-02T15:29:00"})
        assert missing is not None and missing.percent == 0
        zero = grid._parse_limit({"used_percentage": 0})
        assert zero is not None and zero.percent == 0
        bad_reset = grid._parse_limit({"used_percentage": 55, "resets_at": "nope"})
        assert bad_reset == grid.RateLimitUsage(percent=55, resets_at=None)


class TestParseStatus:
    def test_empty_dict_produces_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(grid, "_settings_effort_level", lambda: None)
        assert grid.extract_status_info({}) == grid.Status()

    def test_effort_prefers_payload_over_fallbacks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_EFFORT", "low")
        monkeypatch.setattr(grid, "_settings_effort_level", lambda: "medium")
        assert grid.extract_status_info({"effort": {"level": "xhigh"}}).effort == "xhigh"

    def test_effort_falls_back_to_env_when_payload_omits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Haiku omits effort from stdin; $CLAUDE_EFFORT still applies when set."""
        monkeypatch.setenv("CLAUDE_EFFORT", "high")
        monkeypatch.setattr(grid, "_settings_effort_level", lambda: "medium")
        assert grid.extract_status_info({"model": {"id": "claude-haiku-4-5"}}).effort == "high"

    def test_effort_falls_back_to_settings_when_payload_and_env_omit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(grid, "_settings_effort_level", lambda: "high")
        assert grid.extract_status_info({}).effort == "high"

    def test_full_valid_payload(self) -> None:
        payload = {
            "model": {"id": "claude-opus-4-8"},
            "effort": {"level": "high"},
            "thinking": {"enabled": True},
            "output_style": {"name": "concise"},
            "fast_mode": False,
            "context_window": {"used_percentage": 42},
            "rate_limits": {
                "five_hour": {"used_percentage": 30, "resets_at": 1785665340},
                "seven_day": {"used_percentage": 68, "resets_at": 1785917340},
            },
            "cwd": "/home/user/project",
        }
        result = grid.extract_status_info(payload)
        assert result.model == "claude-opus-4-8"
        assert result.effort == "high"
        assert result.thinking == "on"
        assert result.style == "concise"
        assert result.fast == "off"
        assert result.context.percent == 42
        assert result.five_hour is not None and result.five_hour.percent == 30
        assert result.seven_day is not None and result.seven_day.percent == 68
        assert result.cwd == "/home/user/project"

    def test_bool_fields_require_actual_true(self) -> None:
        assert grid.extract_status_info({"fast_mode": True}).fast == "on"
        assert grid.extract_status_info({"fast_mode": "true"}).fast == "off"
        assert grid.extract_status_info({"fast_mode": 1}).fast == "off"
        assert grid.extract_status_info({"thinking": {"enabled": True}}).thinking == "on"
        assert grid.extract_status_info({"thinking": {"enabled": "yes"}}).thinking == "off"

    def test_empty_text_fields_fall_back_to_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(grid, "_settings_effort_level", lambda: None)
        payload = {
            "model": {"id": ""},
            "effort": {"level": ""},
            "output_style": {"name": ""},
        }
        result = grid.extract_status_info(payload)
        assert result.model == "?"
        assert result.effort == "?"
        assert result.style == "default"

    def test_cwd_fallback_and_precedence(self) -> None:
        assert grid.extract_status_info({"workspace": {"current_dir": "/ws"}}).cwd == "/ws"
        assert (
            grid.extract_status_info({"cwd": "", "workspace": {"current_dir": "/ws"}}).cwd == "/ws"
        )
        assert (
            grid.extract_status_info({"cwd": "/explicit", "workspace": {"current_dir": "/ws"}}).cwd
            == "/explicit"
        )

    def test_whitespace_cwd_does_not_fall_back(self) -> None:
        """Spaces are truthy — unlike '' they skip workspace.current_dir."""
        payload = {"cwd": "   ", "workspace": {"current_dir": "/real"}}
        assert grid.extract_status_info(payload).cwd == "   "

    def test_partial_and_wrong_type_rate_limits(self) -> None:
        only_five = grid.extract_status_info(
            {"rate_limits": {"five_hour": {"used_percentage": 30}}}
        )
        assert only_five.five_hour is not None and only_five.seven_day is None
        only_seven = grid.extract_status_info(
            {"rate_limits": {"seven_day": {"used_percentage": 10}}}
        )
        assert only_seven.five_hour is None and only_seven.seven_day is not None
        junk = grid.extract_status_info({"rate_limits": "oops"})
        assert junk.five_hour is None and junk.seven_day is None


class TestLimitRow:
    def test_clock_formatting(self) -> None:
        assert grid._limit_row("5h", None, "%H:%M", 4) == ""
        bare = grid.RateLimitUsage(percent=30, resets_at=None)
        assert "⏰" not in grid._limit_row("5h", bare, "%H:%M", 4)
        timed = grid.RateLimitUsage(percent=30, resets_at=datetime(2026, 8, 2, 15, 29, 0))
        assert "⏰ 15:29" in grid._limit_row("5h", timed, "%H:%M", 4)
        assert "⏰ 08-02" in grid._limit_row("7d", timed, "%m-%d", 4)


class TestRenderGrid:
    def test_dividers_align_sample_and_default(
        self, sample_status: grid.Status, default_status: grid.Status
    ) -> None:
        _assert_dividers_align(grid.render_grid(sample_status).split("\n"))
        lines = grid.render_grid(default_status).split("\n")
        assert len(lines) == 5
        _assert_dividers_align(lines)

    def test_dividers_align_when_state_column_grows(self) -> None:
        status = grid.Status(model="claude-opus-4-8-20240101-extremely-long-model-name")
        lines = grid.render_grid(status).split("\n")
        _assert_dividers_align(lines)
        assert status.model in lines[0]

    def test_missing_rate_limits_leave_empty_usage_cells(self) -> None:
        lines = grid.render_grid(grid.Status(model="x")).split("\n")
        assert len(lines) == 5
        for i in (1, 2):
            assert lines[i].count("│") == 2

    def test_long_cwd_not_truncated(self) -> None:
        path = "/very/long/path/to/working/directory/for/testing"
        assert path in grid.render_grid(grid.Status(cwd=path))

    def test_snapshot_known_status(self, sample_status: grid.Status) -> None:
        lines = grid.render_grid(sample_status).split("\n")
        assert len(lines) == 5
        assert "claude-opus-4-8" in lines[0]
        assert "high" in lines[1]
        assert "on" in lines[2]
        assert "concise" in lines[3]
        assert "off" in lines[4] and "demo" in lines[4]
        assert "⏰ 15:29" in "\n".join(lines)
        assert "⏰ 08-05" in "\n".join(lines)


class TestLoadDataAndMain:
    def test_load_valid_and_malformed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(grid.sys, "stdin", StringIO('{"a": 1}'))
        assert grid.load_data() == {"a": 1}
        monkeypatch.setattr(grid.sys, "stdin", StringIO("{not-json"))
        assert grid.load_data() == {}

    def test_main_happy_and_bad_stdin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(grid.sys, "stdin", StringIO('{"model": {"id": "x"}}'))
        assert grid.main() == 0
        out = capsys.readouterr().out
        assert len(out.rstrip("\n").split("\n")) == 5
        assert "x" in out

        monkeypatch.setattr(grid.sys, "stdin", StringIO("{{{"))
        assert grid.main() == 0
        assert len(capsys.readouterr().out.rstrip("\n").split("\n")) == 5

    def test_non_dict_json_still_renders(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(grid.sys, "stdin", StringIO("[]"))
        assert grid.main() == 0
        assert len(capsys.readouterr().out.rstrip("\n").split("\n")) == 5


class TestHostilePayloads:
    """Inputs Claude Code should not send — but parse/render must not crash."""

    def test_kitchen_sink_wrong_types(self) -> None:
        payload = {
            "model": "claude-opus-4-8",
            "effort": ["high"],
            "thinking": True,
            "fast_mode": "true",
            "context_window": 42,
            "rate_limits": {
                "five_hour": [{"used_percentage": 10}],
                "seven_day": "68%",
            },
            "cwd": 12345,
        }
        status = grid.extract_status_info(payload)
        assert status.model == "?"
        assert status.cwd == 12345
        lines = grid.render_grid(status).split("\n")
        assert len(lines) == 5
        _assert_dividers_align(lines)

    def test_truthy_non_str_fields_still_render(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(grid, "_settings_effort_level", lambda: None)
        status = grid.extract_status_info(
            {
                "model": {"id": {"nested": "nope"}},
                "effort": {"level": ["high"]},  # non-str → ignored, effort stays "?"
                "context_window": {"used_percentage": {"v": 50}},
            }
        )
        assert status.model == {"nested": "nope"}
        assert status.effort == "?"
        assert status.context.percent == 0
        lines = grid.render_grid(status).split("\n")
        assert len(lines) == 5
        _assert_dividers_align(lines)

    def test_extreme_lengths_keep_alignment(self) -> None:
        status = grid.Status(
            model="m" * 4000,
            cwd="/" + "/".join(f"s{i}" for i in range(200)),
            five_hour=grid.RateLimitUsage(percent=99, resets_at=datetime(2026, 1, 1)),
        )
        lines = grid.render_grid(status).split("\n")
        assert len(lines) == 5
        _assert_dividers_align(lines)

    def test_wide_unicode_fields_keep_alignment(self) -> None:
        status = grid.Status(model="🤖-模型", effort="高", cwd="/home/中文/目录")
        lines = grid.render_grid(status).split("\n")
        assert len(lines) == 5
        _assert_dividers_align(lines)
