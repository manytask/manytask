"""Preserve useful, redacted build diagnostics when the launcher times out."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from e2e import run


def test_timed_out_command_preserves_output_and_still_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run, "COMPONENT", tmp_path)
    stack = run.Stack("unix:///dedicated-test.sock")
    stack.password = "fake-test-password"
    stack.course_token = "fake-course-token"
    cleanup = Mock()
    monkeypatch.setattr(stack, "cleanup", cleanup)
    monkeypatch.setattr(run, "Stack", Mock(return_value=stack))
    monkeypatch.setattr(run.signal, "signal", Mock())
    monkeypatch.setattr(sys, "argv", ["run.py", "--docker-host", "unix:///dedicated-test.sock"])
    args = [
        sys.executable,
        "-u",
        "-c",
        "import sys, time; print('build step fake-test-password'); "
        "print('download fake-course-token', file=sys.stderr); time.sleep(30)",
    ]
    monkeypatch.setattr(stack, "run", lambda: run.command(args, timeout=1))

    with pytest.raises(run.subprocess.TimeoutExpired):
        run.main()

    expected = "build step <redacted>\ndownload <redacted>\n"
    assert (stack.directory / "command-error.log").read_text() == expected
    assert expected in capsys.readouterr().out
    assert json.loads((stack.directory / "result.json").read_text())["failure_type"] == "TimeoutExpired"
    cleanup.assert_called_once_with()


def test_build_failure_does_not_start_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "COMPONENT", tmp_path)
    build_timeout = 7
    stack = run.Stack("unix:///dedicated-test.sock", build_timeout=build_timeout)
    monkeypatch.setattr(stack, "prepare", Mock())
    execute = Mock(side_effect=run.CommandFailed(["docker", "build"], subprocess.CompletedProcess([], 1, "", "failed")))
    monkeypatch.setattr(run, "command", execute)

    with pytest.raises(run.CommandFailed):
        stack.run()

    assert execute.call_args.kwargs["timeout"] == build_timeout
    assert all("up" not in invocation.args[0] for invocation in execute.call_args_list)
