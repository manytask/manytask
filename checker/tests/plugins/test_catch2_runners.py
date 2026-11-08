from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from checker.exceptions import PluginExecutionFailed
from checker.plugins.base import PluginOutput
from checker.plugins.cpp_run_benchmarks import CppRunBenchmarksPlugin
from checker.plugins.cpp_run_tests import CppRunTestsPlugin
from checker.plugins.firejail import SafeRunScriptPlugin


@pytest.fixture
def sandbox(mocker: MockerFixture) -> Mock:
    return mocker.patch.object(
        SafeRunScriptPlugin, "_run", return_value=PluginOutput(output="")
    )


def test_tests_keep_target_order_and_sanitizer_settings(
    tmp_path: Path, sandbox: Mock
) -> None:
    result = CppRunTestsPlugin().run(
        {
            "root": tmp_path,
            "tests": ["unit_tests", "Debug", "integration_tests", "Release"],
            "timeout": 12,
            "no_detect_leaks": True,
            "args": ["[public]", "--durations", "yes"],
            "paths_whitelist": ["fixtures"],
            "lock_network": False,
        },
        verbose=True,
    )

    assert result.output == "Tests are passed"
    assert sandbox.call_count == 2
    for call, target, build_type in zip(
        sandbox.call_args_list,
        ["unit_tests", "integration_tests"],
        ["debug", "release"],
    ):
        args = call.args[0]
        assert args.origin == str(tmp_path / f"build-{build_type}")
        assert args.script[0] == str(tmp_path / f"build-{build_type}" / target)
        assert args.script[1] == "-r"
        assert args.script[2].startswith("console::out=")
        assert args.script[2].endswith("report.txt::colour-mode=ansi")
        assert args.script[3:] == ["[public]", "--durations", "yes"]
        assert args.timeout == 12
        assert args.paths_whitelist == [str(tmp_path / "fixtures")]
        assert args.lock_network is False
        assert args.allow_fallback is False
        assert args.env_whitelist == []
        assert args.env_additional["ASAN_OPTIONS"].endswith(
            ",color=always,detect_leaks=0"
        )
        assert args.env_additional["UBSAN_OPTIONS"].endswith(
            ",color=always,print_stacktrace=1"
        )
        assert args.env_additional["TSAN_OPTIONS"].endswith(",color=always")
        assert call.kwargs == {"verbose": True}


@pytest.mark.parametrize("fail", [False, True])
def test_tests_print_catch2_and_sanitizer_reports_on_success_and_failure(
    tmp_path: Path, sandbox: Mock, capsys: pytest.CaptureFixture[str], fail: bool
) -> None:
    (tmp_path / "report.txt").write_text("Catch2 results\n")
    (tmp_path / "asan.123").write_text("AddressSanitizer details\n")
    (tmp_path / "ubsan.123").write_text("UndefinedBehaviorSanitizer details\n")
    (tmp_path / "tsan.123").write_text("ThreadSanitizer details\n")
    args = CppRunTestsPlugin.Args(
        root=tmp_path,
        tests=["tests", "Debug"],
        timeout=10,
        no_detect_leaks=False,
        args=[],
        paths_whitelist=[],
    )
    if fail:
        sandbox.side_effect = PluginExecutionFailed("test failure")
        with pytest.raises(PluginExecutionFailed, match="test failure"):
            CppRunTestsPlugin._run_tests(args, tmp_path, tmp_path, "tests", False)
    else:
        CppRunTestsPlugin._run_tests(args, tmp_path, tmp_path, "tests", False)

    output = capsys.readouterr().err
    for text in (
        "Catch2 results",
        "AddressSanitizer details",
        "UndefinedBehaviorSanitizer details",
        "ThreadSanitizer details",
    ):
        assert text in output
    assert (
        "detect_leaks=0" not in sandbox.call_args.args[0].env_additional["ASAN_OPTIONS"]
    )


@pytest.mark.parametrize("tests", [[], ["tests"]])
def test_invalid_test_targets_fail_before_execution(
    tmp_path: Path, sandbox: Mock, tests: list[str]
) -> None:
    with pytest.raises(PluginExecutionFailed):
        CppRunTestsPlugin().run(
            {
                "root": tmp_path,
                "tests": tests,
                "timeout": 10,
                "no_detect_leaks": False,
                "args": [],
                "paths_whitelist": [],
            }
        )
    sandbox.assert_not_called()


@pytest.mark.parametrize("threshold", ["0.01", "-0.001"])
def test_benchmarks_generate_both_reports_and_check_thresholds(
    tmp_path: Path,
    sandbox: Mock,
    capsys: pytest.CaptureFixture[str],
    threshold: str,
) -> None:
    (tmp_path / "report.xml").write_text(
        '<Catch2TestRun><BenchmarkResults name="add">'
        '<mean value="2000000"/></BenchmarkResults></Catch2TestRun>'
    )
    (tmp_path / "report.txt").write_text("Benchmark details\n")
    args = CppRunBenchmarksPlugin.Args(
        root=tmp_path,
        benchmark="benchmarks",
        timeout=20,
        args=["[benchmark]"],
        benchmark_values=["add", threshold],
    )
    build_dir = tmp_path / "build-relwithdebinfo"
    CppRunBenchmarksPlugin._run_benchmarks(
        args, tmp_path, build_dir, "benchmarks", True
    )

    run_args = sandbox.call_args.args[0]
    assert run_args.script == [
        str(build_dir / "benchmarks"),
        "-r",
        f"xml::out={tmp_path / 'report.xml'}",
        "-r",
        f"console::out={tmp_path / 'report.txt'}::colour-mode=ansi",
        "[benchmark]",
    ]
    assert run_args.timeout == 20
    assert run_args.env_additional == {}
    assert run_args.env_whitelist == []
    assert run_args.lock_network is True
    assert run_args.paths_whitelist == []
    assert "Benchmark details" in capsys.readouterr().err


def test_benchmark_threshold_failure_still_prints_report(
    tmp_path: Path, sandbox: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "report.xml").write_text(
        '<Catch2TestRun><BenchmarkResults name="add">'
        '<mean value="2000000"/></BenchmarkResults></Catch2TestRun>'
    )
    (tmp_path / "report.txt").write_text("Slow benchmark details\n")
    args = CppRunBenchmarksPlugin.Args(
        root=tmp_path,
        benchmark="benchmarks",
        timeout=20,
        args=[],
        benchmark_values=["add", "0.001"],
    )
    with pytest.raises(PluginExecutionFailed):
        CppRunBenchmarksPlugin._run_benchmarks(
            args, tmp_path, tmp_path, "benchmarks", False
        )
    assert "Slow benchmark details" in capsys.readouterr().err


def test_benchmark_execution_failure_prints_report_without_reading_xml(
    tmp_path: Path, sandbox: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "report.txt").write_text("Partial benchmark results\n")
    sandbox.side_effect = PluginExecutionFailed("benchmark failure")
    args = CppRunBenchmarksPlugin.Args(
        root=tmp_path,
        benchmark="benchmarks",
        timeout=20,
        args=[],
        benchmark_values=[],
    )
    with pytest.raises(PluginExecutionFailed, match="benchmark failure"):
        CppRunBenchmarksPlugin._run_benchmarks(
            args, tmp_path, tmp_path, "benchmarks", False
        )
    assert "Partial benchmark results" in capsys.readouterr().err
