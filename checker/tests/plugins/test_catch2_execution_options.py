import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from checker.configs.checker import CheckerSubConfig
from checker.exceptions import PluginExecutionFailed
from checker.pipeline import (
    GlobalPipelineVariables,
    PipelineContext,
    PipelineRunner,
    TaskPipelineVariables,
)
from checker.plugins.base import PluginOutput
from checker.plugins.cpp_run_benchmarks import CppRunBenchmarksPlugin
from checker.plugins.cpp_run_tests import CppRunTestsPlugin
from checker.plugins.firejail import SafeRunScriptPlugin


@pytest.mark.parametrize("benchmark", [False, True])
def test_execution_options_apply_to_tests_and_benchmarks(
    tmp_path: Path, mocker: MockerFixture, benchmark: bool
) -> None:
    sandbox = mocker.patch.object(
        SafeRunScriptPlugin,
        "_run",
        return_value=PluginOutput(output="tool diagnostics"),
    )
    prefix = ["/opt/tools/tool with spaces", "--mode", "literal $value; argument"]
    common = {
        "root": tmp_path,
        "timeout": 123,
        "args": ["[gpu]"],
        "command_prefix": prefix,
        "env_whitelist": ["CUDA_VISIBLE_DEVICES"],
        "paths_whitelist": ["fixtures"],
        "lock_network": False,
    }
    if benchmark:
        (tmp_path / "report.xml").write_text("<Catch2TestRun/>")
        CppRunBenchmarksPlugin._run_benchmarks(
            CppRunBenchmarksPlugin.Args(
                **common, benchmark="benchmarks", benchmark_values=[]
            ),
            tmp_path,
            tmp_path,
            "benchmarks",
            False,
        )
        target = "benchmarks"
    else:
        CppRunTestsPlugin._run_tests(
            CppRunTestsPlugin.Args(
                **common, tests=["tests", "Debug"], no_detect_leaks=False
            ),
            tmp_path,
            tmp_path,
            "tests",
            False,
        )
        target = "tests"

    args = sandbox.call_args.args[0]
    assert args.script[:4] == [*prefix, str(tmp_path / target)]
    assert args.script[-1] == "[gpu]"
    assert args.env_whitelist == ["CUDA_VISIBLE_DEVICES"]
    assert args.paths_whitelist == [str(tmp_path / "fixtures")]
    assert args.lock_network is False
    assert args.timeout == 123
    assert args.allow_fallback is False


@pytest.mark.parametrize("exit_code", [0, 42])
def test_real_wrapper_execution_preserves_environment_reports_and_failures(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exit_code: int,
) -> None:
    # Exercise real subprocesses without requiring Firejail or a GPU on the host.
    # Production continues to use SafeRunScriptPlugin with fallback disabled.
    mocker.patch.object(
        SafeRunScriptPlugin,
        "_run",
        side_effect=SafeRunScriptPlugin()._fallback_to_run_script,
    )
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2")
    monkeypatch.setenv("CHECKER_TEST_UNRELATED", "not forwarded")
    wrapper = tmp_path / "wrapper with spaces.py"
    wrapper.write_text(
        "import os, subprocess, sys\n"
        "assert os.environ['CUDA_VISIBLE_DEVICES'] == '2'\n"
        "assert 'CHECKER_TEST_UNRELATED' not in os.environ\n"
        "assert 'ASAN_OPTIONS' in os.environ\n"
        "assert sys.argv[1] == 'literal $value; argument'\n"
        "print('wrapper diagnostics', flush=True)\n"
        "raise SystemExit(subprocess.call(sys.argv[2:]))\n"
    )
    binary = tmp_path / "test binary"
    binary.write_text(
        "#!/bin/sh\n"
        "report=${2#console::out=}\n"
        "report=${report%::colour-mode=ansi}\n"
        'printf "Catch2 report from binary\\n" > "$report"\n'
        f"exit {exit_code}\n"
    )
    binary.chmod(0o755)
    args = CppRunTestsPlugin.Args(
        root=tmp_path,
        tests=[binary.name, "Debug"],
        timeout=10,
        no_detect_leaks=False,
        args=[],
        command_prefix=[sys.executable, str(wrapper), "literal $value; argument"],
        env_whitelist=["CUDA_VISIBLE_DEVICES"],
    )
    if exit_code:
        with pytest.raises(PluginExecutionFailed) as error:
            CppRunTestsPlugin._run_tests(args, tmp_path, tmp_path, binary.name, False)
        assert "exit code 42" in error.value.message
        assert "wrapper diagnostics" in error.value.output
    else:
        CppRunTestsPlugin._run_tests(args, tmp_path, tmp_path, binary.name, False)

    output = capsys.readouterr().err
    assert "Catch2 report from binary" in output
    if not exit_code:
        assert "wrapper diagnostics" in output


@pytest.mark.parametrize("fail_sanitizer", [False, True])
def test_cuda_example_resolves_and_runs_separate_instrumented_stage(
    tmp_path: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    fail_sanitizer: bool,
) -> None:
    example = Path(__file__).parents[3] / "course-template" / "cuda" / ".group.yml"
    config = CheckerSubConfig.from_yaml(example)
    assert config.parameters is not None
    assert config.task_pipeline is not None
    context: PipelineContext = {
        "global": GlobalPipelineVariables(
            ref_dir=str(tmp_path),
            repo_dir=str(tmp_path),
            temp_dir=str(tmp_path),
            task_names=["vector_add_cuda"],
            task_sub_paths=["cuda/vector_add_cuda"],
        ),
        "task": TaskPipelineVariables(
            task_name="vector_add_cuda",
            task_sub_path="cuda/vector_add_cuda",
            task_score_percent=1,
        ),
        "parameters": config.parameters.root,
        "env": {},
        "outputs": {},
    }

    def run(args: SafeRunScriptPlugin.Args, *, verbose: bool) -> PluginOutput:
        assert isinstance(args.script, list)
        for token in args.script:
            if token.startswith("console::out="):
                Path(
                    token.removeprefix("console::out=").removesuffix(
                        "::colour-mode=ansi"
                    )
                ).write_text("Catch2 results from GPU worker\n")
            elif token.startswith("xml::out="):
                Path(token.removeprefix("xml::out=")).write_text(
                    '<Catch2TestRun><BenchmarkResults name="vector_add">'
                    '<mean value="2000000"/></BenchmarkResults></Catch2TestRun>'
                )
        if args.script[0] == "/usr/local/cuda/bin/compute-sanitizer":
            if fail_sanitizer:
                raise PluginExecutionFailed(
                    "sanitizer failed", output="Invalid __global__ read"
                )
            return PluginOutput(output="Compute Sanitizer: no errors")
        return PluginOutput(output="")

    sandbox: Mock = mocker.patch.object(SafeRunScriptPlugin, "_run", side_effect=run)
    runner = PipelineRunner(
        config.task_pipeline,
        {
            plugin.name: plugin
            for plugin in (
                SafeRunScriptPlugin,
                CppRunTestsPlugin,
                CppRunBenchmarksPlugin,
            )
        },
    )
    runner.validate(context)
    result = runner.run(context)

    assert result.failed is fail_sanitizer
    assert sandbox.call_count == (4 if fail_sanitizer else 5)
    calls = [call.args[0] for call in sandbox.call_args_list]
    root = tmp_path / "cuda" / "vector_add_cuda" / "build-relwithdebinfo"
    assert calls[2].script[0] == str(root / "cuda_tests")
    assert calls[3].script[:8] == [
        "/usr/local/cuda/bin/compute-sanitizer",
        "--tool",
        "memcheck",
        "--leak-check",
        "full",
        "--error-exitcode",
        "1",
        str(root / "cuda_tests"),
    ]
    assert calls[3].timeout == 120
    assert calls[3].env_additional["ASAN_OPTIONS"]
    for call in calls[2:]:
        assert call.env_whitelist == ["PATH", "CUDA_VISIBLE_DEVICES", "LD_LIBRARY_PATH"]
        assert call.lock_network is True
        assert call.allow_fallback is False
    if fail_sanitizer:
        assert result.stage_results[-1].name == "CUDA memory checks"
        assert "Invalid __global__ read" in capsys.readouterr().err
    else:
        assert calls[4].script[0] == str(root / "cuda_benchmarks")
        assert calls[4].timeout == 30
        assert "Compute Sanitizer: no errors" in capsys.readouterr().err
