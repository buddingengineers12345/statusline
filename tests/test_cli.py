"""Tests for statusline.cli plus end-to-end hostile-payload runs."""

import sys
from io import BytesIO, StringIO, TextIOWrapper

import pytest

from statusline import cli, parsing, rendering
from tests.helpers import assert_dividers_align


class TestLoadDataAndMain:
    def test_load_valid_and_malformed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO('{"a": 1}'))
        assert cli.load_data() == {"a": 1}
        monkeypatch.setattr(sys, "stdin", StringIO("{not-json"))
        assert cli.load_data() == {}

    def test_main_happy_and_bad_stdin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO('{"model": {"id": "x"}}'))
        assert cli.main() == 0
        out = capsys.readouterr().out
        assert len(out.rstrip("\n").split("\n")) == 5
        assert "x" in out

        monkeypatch.setattr(sys, "stdin", StringIO("{{{"))
        assert cli.main() == 0
        assert len(capsys.readouterr().out.rstrip("\n").split("\n")) == 5

    def test_mis_encoded_stdin_degrades(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", TextIOWrapper(BytesIO(b"\xff\xfe{}"), encoding="utf-8"))
        assert cli.load_data() == {}
        monkeypatch.setattr(sys, "stdin", TextIOWrapper(BytesIO(b"\xff\xfe{}"), encoding="utf-8"))
        assert cli.main() == 0
        assert len(capsys.readouterr().out.rstrip("\n").split("\n")) == 5

    def test_non_dict_json_still_renders(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO("[]"))
        assert cli.main() == 0
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
        status = parsing.extract_status_info(payload)
        assert status.model == "?"
        assert status.cwd == 12345
        lines = rendering.render_grid(status).split("\n")
        assert len(lines) == 5
        assert_dividers_align(lines)

    def test_truthy_non_str_fields_still_render(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_EFFORT", raising=False)
        monkeypatch.setattr(parsing, "_settings_effort_level", lambda: None)
        status = parsing.extract_status_info(
            {
                "model": {"id": {"nested": "nope"}},
                "effort": {"level": ["high"]},  # non-str → ignored, effort stays "?"
                "context_window": {"used_percentage": {"v": 50}},
            }
        )
        assert status.model == {"nested": "nope"}
        assert status.effort == "?"
        assert status.context.percent == 0
        lines = rendering.render_grid(status).split("\n")
        assert len(lines) == 5
        assert_dividers_align(lines)
