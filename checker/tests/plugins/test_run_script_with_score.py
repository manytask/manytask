from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.run_script_with_score import RunScriptWithScorePlugin


class TestRunScriptWithScorePluginArgs:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            # minimal valid
            ({"origin": "/tmp", "script": "echo 0.5"}, None),
            # list-form script
            ({"origin": "/tmp", "script": ["echo", "0.5"]}, None),
            # with report_score
            ({"origin": "/tmp", "script": "echo 0.5", "report_score": True}, None),
            # script must be str or list
            ({"origin": "/tmp", "script": 123}, ValidationError),
            # timeout accepted
            ({"origin": "/tmp", "script": "echo 0.5", "timeout": 10}, None),
            # allow_failures accepted
            ({"origin": "/tmp", "script": "echo 0.5", "allow_failures": True}, None),
            # custom pattern accepted
            ({"origin": "/tmp", "script": "echo 0.5", "score_pattern": r"Score:\s*(\d+(?:\.\d+)?)"}, None),
        ],
    )
    def test_args_validation(self, parameters: dict[str, Any], expected_exception: type | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                RunScriptWithScorePlugin.Args(**parameters)
        else:
            RunScriptWithScorePlugin.Args(**parameters)


class TestRunScriptWithScorePluginExtractPercentage:
    """Unit-tests for the static helper that parses the score from output."""

    @pytest.mark.parametrize(
        "output, pattern, expected",
        [
            # bare float on its own line
            ("0.42\n", r"(?:^|[^\d.])(\d+(?:\.\d+)?)(?:[^\d.]|$)", 0.42),
            # integer 0 or 1
            ("0\n", r"(?:^|[^\d.])(\d+(?:\.\d+)?)(?:[^\d.]|$)", 0.0),
            ("1\n", r"(?:^|[^\d.])(\d+(?:\.\d+)?)(?:[^\d.]|$)", 1.0),
            # score embedded in text – last match wins
            ("score: 0.3\nscore: 0.8\n", r"score:\s*(\d+(?:\.\d+)?)", 0.80),
            # custom key=value pattern
            ("SCORE=0.55\n", r"SCORE=(\d+(?:\.\d+)?)", 0.55),
            # exactly 1.0
            ("1.0\n", r"(?:^|[^\d.])(\d+(?:\.\d+)?)(?:[^\d.]|$)", 1.0),
        ],
    )
    def test_valid_outputs(self, output: str, pattern: str, expected: float) -> None:
        result = RunScriptWithScorePlugin._extract_percentage(output, pattern)
        assert abs(result - expected) < 1e-9

    @pytest.mark.parametrize(
        "output, pattern, error_fragment",
        [
            # no match at all
            ("no numbers here\n", r"Score:\s*(\d+)", "No score found"),
            # invalid regex
            ("0.5\n", r"[invalid(", "Invalid score_pattern regex"),
            # score > 1
            ("1.5\n", r"(?:^|[^\d.])(\d+(?:\.\d+)?)(?:[^\d.]|$)", "Score must be in [0, 1]"),
            # score < 0  (negative sign not captured by default pattern, but test explicit pattern)
            ("-0.1\n", r"(-?\d+(?:\.\d+)?)", "Score must be in [0, 1]"),
        ],
    )
    def test_invalid_outputs(self, output: str, pattern: str, error_fragment: str) -> None:
        with pytest.raises(PluginExecutionFailed) as exc_info:
            RunScriptWithScorePlugin._extract_percentage(output, pattern)
        assert error_fragment in str(exc_info.value)


class TestRunScriptWithScorePluginRun:
    """Integration-style tests that actually run subprocesses."""

    def test_no_report_score_returns_full_percentage(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(origin="/tmp", script="echo 0.5", report_score=False)
        result = plugin._run(args)
        assert result.percentage == 1.0
        assert "0.5" in result.output

    def test_report_score_parses_output(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(origin="/tmp", script="echo 0.75", report_score=True)
        result = plugin._run(args)
        assert abs(result.percentage - 0.75) < 1e-9

    def test_report_score_zero(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(origin="/tmp", script="echo 0", report_score=True)
        result = plugin._run(args)
        assert result.percentage == 0.0

    def test_report_score_one(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(origin="/tmp", script="echo 1", report_score=True)
        result = plugin._run(args)
        assert result.percentage == 1.0

    def test_report_score_out_of_range_raises(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(origin="/tmp", script="echo 1.5", report_score=True)
        with pytest.raises(PluginExecutionFailed, match=r"Score must be in \[0, 1\]"):
            plugin._run(args)

    def test_allow_failures_non_zero_exit(self) -> None:
        """Script exits non-zero but allow_failures=True → no exception."""
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script="echo 0.5; exit 1",
            report_score=True,
            allow_failures=True,
        )
        result = plugin._run(args)
        assert abs(result.percentage - 0.5) < 1e-9

    def test_non_zero_exit_with_report_score_still_runs(self) -> None:
        """report_score=True implicitly allows failures so score is still parsed."""
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script="echo 0.6; exit 1",
            report_score=True,
        )
        result = plugin._run(args)
        assert abs(result.percentage - 0.6) < 1e-9

    def test_custom_score_pattern(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script='echo "Score: 0.88"',
            report_score=True,
            score_pattern=r"Score:\s*(\d+(?:\.\d+)?)",
        )
        result = plugin._run(args)
        assert abs(result.percentage - 0.88) < 1e-9

    def test_last_match_wins(self) -> None:
        """When multiple score lines appear, the last one is used."""
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script='printf "Score: 0.1\\nScore: 0.9\\n"',
            report_score=True,
            score_pattern=r"Score:\s*(\d+(?:\.\d+)?)",
        )
        result = plugin._run(args)
        assert abs(result.percentage - 0.90) < 1e-9

    def test_no_score_in_output_raises(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script='echo "no numbers here"',
            report_score=True,
            score_pattern=r"Score:\s*(\d+)",
        )
        with pytest.raises(PluginExecutionFailed, match="No score found"):
            plugin._run(args)

    def test_list_script_form(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script=["bash", "-c", "echo 0.55"],
            report_score=True,
        )
        result = plugin._run(args)
        assert abs(result.percentage - 0.55) < 1e-9

    def test_timeout_respected(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(origin="/tmp", script="sleep 5", timeout=0.2)
        with pytest.raises(PluginExecutionFailed, match="timed out"):
            plugin._run(args)

    def test_env_whitelist_passed_through(self) -> None:
        plugin = RunScriptWithScorePlugin()
        args = RunScriptWithScorePlugin.Args(
            origin="/tmp",
            script="echo $MY_VAR",
            env_additional={"MY_VAR": "hello"},
            env_whitelist=["MY_VAR"],
        )
        with patch.dict("os.environ", {}, clear=True):
            result = plugin._run(args)
        assert "hello" in result.output
