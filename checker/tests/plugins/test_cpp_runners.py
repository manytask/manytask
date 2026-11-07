from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from checker.exceptions import PluginExecutionFailed
from checker.plugins.base import PluginOutput
from checker.plugins.cpp_run_benchmarks import CppRunBenchmarksPlugin
from checker.plugins.cpp_run_tests import CppRunTestsPlugin
from checker.plugins.firejail import SafeRunScriptPlugin


@pytest.fixture(params=[CppRunTestsPlugin, CppRunBenchmarksPlugin])
def plugin(
    request: pytest.FixtureRequest,
) -> CppRunTestsPlugin | CppRunBenchmarksPlugin:
    return request.param()


@pytest.fixture
def args(tmp_path: Path) -> dict[str, Any]:
    return {
        "root": tmp_path,
        "tests": ["test_target", "Debug"],
        "benchmark": "benchmark_target",
        "timeout": 42,
        "no_detect_leaks": True,
        "args": ["--reporter-option", "argument with spaces"],
        "paths_whitelist": ["data"],
        "benchmark_values": ["example", "1"],
    }


def write_reports(run_args: SafeRunScriptPlugin.Args) -> None:
    assert isinstance(run_args.script, list)
    for argument in run_args.script:
        if argument.startswith("console::out="):
            path = argument.removeprefix("console::out=").split("::")[0]
            Path(path).write_text("test report\n")
        elif argument.startswith("xml::out="):
            Path(argument.removeprefix("xml::out=")).write_text(
                '<Catch2TestRun><BenchmarkResults name="example">'
                '<mean value="1000000"/></BenchmarkResults></Catch2TestRun>'
            )


@pytest.mark.parametrize(
    ("whitelist", "show"),
    [
        ([], []),
        (["CUDA_VISIBLE_DEVICES"], []),
        (["CUDA_VISIBLE_DEVICES"], ["CUDA_VISIBLE_DEVICES"]),
        ([], ["CHECKER_TEST_LABEL", "CHECKER_TEST_UNSET"]),
    ],
)
def test_environment_forwarding_and_logging_are_independent(
    plugin: CppRunTestsPlugin | CppRunBenchmarksPlugin,
    args: dict[str, Any],
    whitelist: list[str],
    show: list[str],
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2")
    monkeypatch.setenv("CHECKER_TEST_LABEL", "synthetic-label")
    monkeypatch.setenv("CHECKER_TEST_PRIVATE", "synthetic-private-value")
    monkeypatch.delenv("CHECKER_TEST_UNSET", raising=False)
    args.update(env_whitelist=whitelist, show_env_variables=show)

    def run(run_args: SafeRunScriptPlugin.Args, *, verbose: bool) -> PluginOutput:
        assert run_args.env_whitelist == whitelist
        assert run_args.timeout == 42
        assert run_args.script[-2:] == args["args"]
        assert verbose is True
        write_reports(run_args)
        return PluginOutput(output="")

    mocker.patch.object(SafeRunScriptPlugin, "_run", side_effect=run)
    plugin.run(args, verbose=True)
    output = capsys.readouterr().err
    assert "test report" in output
    expected_values = {
        "CUDA_VISIBLE_DEVICES": "2",
        "CHECKER_TEST_LABEL": "synthetic-label",
        "CHECKER_TEST_UNSET": "None",
        "CHECKER_TEST_PRIVATE": "synthetic-private-value",
    }
    for name, value in expected_values.items():
        assert (f"{name} is set to `{value}`" in output) == (name in show)
    assert "synthetic-private-value" not in output


@pytest.mark.parametrize(
    "prefix",
    [
        [],
        ["valgrind", "--error-exitcode=1"],
        [
            "/usr/local/cuda/bin/compute-sanitizer",
            "--leak-check",
            "full",
            "--error-exitcode",
            "1",
        ],
    ],
)
@pytest.mark.parametrize("no_detect_leaks", [False, True])
def test_test_runner_prefix_preserves_sandbox_and_sanitizers(
    args: dict[str, Any],
    prefix: list[str],
    no_detect_leaks: bool,
    mocker: MockerFixture,
) -> None:
    args.update(run_prefix=prefix, no_detect_leaks=no_detect_leaks, lock_network=False)

    def run(run_args: SafeRunScriptPlugin.Args, *, verbose: bool) -> PluginOutput:
        assert isinstance(run_args.script, list)
        assert run_args.script[: len(prefix) + 2] == [
            *prefix,
            str(args["root"] / "build-debug" / "test_target"),
            "-r",
        ]
        assert run_args.script[-2:] == args["args"]
        assert run_args.origin == str(args["root"] / "build-debug")
        assert run_args.paths_whitelist == [str(args["root"] / "data")]
        assert run_args.lock_network is False
        assert run_args.allow_fallback is False
        assert run_args.env_whitelist == []
        assert set(run_args.env_additional) == {
            "ASAN_OPTIONS",
            "UBSAN_OPTIONS",
            "TSAN_OPTIONS",
        }
        assert (
            "detect_leaks=0" in run_args.env_additional["ASAN_OPTIONS"]
        ) == no_detect_leaks
        command = SafeRunScriptPlugin()._build_firejail_command(run_args)
        assert command[-len(run_args.script) :] == run_args.script
        write_reports(run_args)
        return PluginOutput(output="")

    mocker.patch.object(SafeRunScriptPlugin, "_run", side_effect=run)
    CppRunTestsPlugin().run(args)


def test_default_options_and_failure_still_print_reports(
    plugin: CppRunTestsPlugin | CppRunBenchmarksPlugin,
    args: dict[str, Any],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def run(run_args: SafeRunScriptPlugin.Args, *, verbose: bool) -> PluginOutput:
        assert run_args.env_whitelist == []
        assert isinstance(run_args.script, list)
        assert run_args.script[0].startswith(str(args["root"]))
        write_reports(run_args)
        raise PluginExecutionFailed("runner failed")

    mocker.patch.object(SafeRunScriptPlugin, "_run", side_effect=run)
    with pytest.raises(PluginExecutionFailed, match="runner failed"):
        plugin.run(args)
    output = capsys.readouterr().err
    assert "test report" in output
    assert "is set to" not in output
