"""Tests for statusline.parsing and statusline.errors: payload -> Status."""

from datetime import datetime
from pathlib import Path

import pytest

from statusline import parsing
from statusline.errors import handle_exception
from statusline.models import RateLimitUsage, Status


class TestHandleException:
    def test_returns_fresh_copy_of_mutable_default(self) -> None:
        @handle_exception({}, ValueError)
        def boom() -> dict[str, int]:
            raise ValueError("nope")

        a, b = boom(), boom()
        a["x"] = 1
        assert b == {}


class TestAsDict:
    def test_dict_passthrough_else_empty(self) -> None:
        d = {"a": 1}
        assert parsing._as_dict(d) is d
        assert parsing._as_dict(None) == {}
        assert parsing._as_dict("x") == {}


class TestNestedGet:
    def test_walks_nested_dicts(self) -> None:
        assert parsing._nested_get({"a": {"b": {"c": 42}}}, ["a", "b", "c"]) == 42

    def test_missing_or_wrong_type_returns_default(self) -> None:
        assert parsing._nested_get({"a": {}}, ["a", "b"], "fallback") == "fallback"
        assert parsing._nested_get({"a": "not-dict"}, ["a", "b"], "fallback") == "fallback"
        assert parsing._nested_get(None, ["a"], "fallback") == "fallback"

    def test_falsy_value_collapses_to_default(self) -> None:
        """Real 0 / '' / None / False are indistinguishable from missing."""
        for falsy in (0, "", None, False):
            assert parsing._nested_get({"a": falsy}, ["a"], "default") == "default"


class TestProcessPercent:
    def test_int_and_float_truncate(self) -> None:
        assert parsing.process_percent(42) == 42
        assert parsing.process_percent(42.7) == 42
        assert parsing.process_percent("42.5") == 42

    def test_clamps_to_0_100(self) -> None:
        assert parsing.process_percent(-1) == 0
        assert parsing.process_percent(101) == 100

    def test_junk_becomes_zero(self) -> None:
        assert parsing.process_percent(None) == 0
        assert parsing.process_percent("junk") == 0
        assert parsing.process_percent("42%") == 0
        assert parsing.process_percent(float("nan")) == 0
        assert parsing.process_percent(float("inf")) == 0


class TestParseResetsAt:
    def test_epoch_int_and_string(self) -> None:
        ts = 1785665340
        from_int = parsing._parse_resets_at(ts)
        from_str = parsing._parse_resets_at(str(ts))
        assert from_int is not None and int(from_int.timestamp()) == ts
        assert from_str is not None and int(from_str.timestamp()) == ts

    def test_iso_and_suffix_truncation(self) -> None:
        assert parsing._parse_resets_at("2026-08-02T15:29:00") == datetime(2026, 8, 2, 15, 29, 0)
        assert parsing._parse_resets_at("2026-08-02T15:29:00Z") == datetime(2026, 8, 2, 15, 29, 0)
        assert parsing._parse_resets_at("2026-08-02T15:29:00.123456Z") == datetime(
            2026, 8, 2, 15, 29, 0
        )

    def test_unparseable_or_overflow_returns_none(self) -> None:
        assert parsing._parse_resets_at("not a timestamp") is None
        assert parsing._parse_resets_at(None) is None
        assert parsing._parse_resets_at(10**20) is None


class TestParseLimit:
    def test_empty_or_non_dict_returns_none(self) -> None:
        assert parsing._parse_limit(None) is None
        assert parsing._parse_limit({}) is None
        assert parsing._parse_limit([1]) is None

    def test_valid_with_and_without_reset(self) -> None:
        with_reset = parsing._parse_limit(
            {"used_percentage": 42, "resets_at": "2026-08-02T15:29:00"}
        )
        assert with_reset == RateLimitUsage(percent=42, resets_at=datetime(2026, 8, 2, 15, 29, 0))
        bare = parsing._parse_limit({"used_percentage": 30})
        assert bare == RateLimitUsage(percent=30, resets_at=None)

    def test_missing_or_zero_percent_and_bad_reset(self) -> None:
        missing = parsing._parse_limit({"resets_at": "2026-08-02T15:29:00"})
        assert missing is not None and missing.percent == 0
        zero = parsing._parse_limit({"used_percentage": 0})
        assert zero is not None and zero.percent == 0
        bad_reset = parsing._parse_limit({"used_percentage": 55, "resets_at": "nope"})
        assert bad_reset == RateLimitUsage(percent=55, resets_at=None)


class TestParseStatus:
    def test_empty_dict_produces_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: None)
        assert parsing.extract_status_info({}) == Status()

    def test_effort_prefers_payload_over_fallbacks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_EFFORT", "low")
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: "medium")
        assert parsing.extract_status_info({"effort": {"level": "xhigh"}}).effort == "xhigh"

    def test_effort_falls_back_to_env_when_payload_omits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Haiku omits effort from stdin; $CLAUDE_EFFORT still applies when set."""
        monkeypatch.setenv("CLAUDE_EFFORT", "high")
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: "medium")
        assert parsing.extract_status_info({"model": {"id": "claude-haiku-4-5"}}).effort == "high"

    def test_effort_falls_back_to_settings_when_payload_and_env_omit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: "high")
        assert parsing.extract_status_info({}).effort == "high"

    def test_effort_falls_back_to_project_settings(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Project effortLevel applies when payload/env omit effort (agentspace posture)."""
        project = tmp_path / "proj"
        claude_dir = project / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"effortLevel": "medium"}', encoding="utf-8")
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: None)
        payload = {"cwd": str(project), "model": {"id": "claude-haiku-4-5"}}
        assert parsing.extract_status_info(payload).effort == "medium"

    def test_session_id_from_payload(self) -> None:
        sid = "abc123-session-id"
        assert parsing.extract_status_info({"session_id": sid}).session_id == sid
        assert parsing.extract_status_info({}).session_id == "?"
        assert parsing.extract_status_info({"session_id": ""}).session_id == "?"

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
        result = parsing.extract_status_info(payload)
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
        assert parsing.extract_status_info({"fast_mode": True}).fast == "on"
        assert parsing.extract_status_info({"fast_mode": "true"}).fast == "off"
        assert parsing.extract_status_info({"fast_mode": 1}).fast == "off"
        assert parsing.extract_status_info({"thinking": {"enabled": True}}).thinking == "on"
        assert parsing.extract_status_info({"thinking": {"enabled": "yes"}}).thinking == "off"

    def test_empty_text_fields_fall_back_to_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: None)
        payload = {
            "model": {"id": ""},
            "effort": {"level": ""},
            "output_style": {"name": ""},
        }
        result = parsing.extract_status_info(payload)
        assert result.model == "?"
        assert result.effort == "?"
        assert result.style == "default"

    def test_cwd_fallback_and_precedence(self) -> None:
        assert parsing.extract_status_info({"workspace": {"current_dir": "/ws"}}).cwd == "/ws"
        assert (
            parsing.extract_status_info({"cwd": "", "workspace": {"current_dir": "/ws"}}).cwd
            == "/ws"
        )
        assert (
            parsing.extract_status_info(
                {"cwd": "/explicit", "workspace": {"current_dir": "/ws"}}
            ).cwd
            == "/explicit"
        )

    def test_whitespace_cwd_does_not_fall_back(self) -> None:
        """Spaces are truthy — unlike '' they skip workspace.current_dir."""
        payload = {"cwd": "   ", "workspace": {"current_dir": "/real"}}
        assert parsing.extract_status_info(payload).cwd == "   "

    def test_partial_and_wrong_type_rate_limits(self) -> None:
        only_five = parsing.extract_status_info(
            {"rate_limits": {"five_hour": {"used_percentage": 30}}}
        )
        assert only_five.five_hour is not None and only_five.seven_day is None
        only_seven = parsing.extract_status_info(
            {"rate_limits": {"seven_day": {"used_percentage": 10}}}
        )
        assert only_seven.five_hour is None and only_seven.seven_day is not None
        junk = parsing.extract_status_info({"rate_limits": "oops"})
        assert junk.five_hour is None and junk.seven_day is None
