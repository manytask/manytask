from __future__ import annotations

import tempfile
from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.cpp.runner import REPORT, Catch2Args, run_catch2
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppRunTestsPlugin(PluginABC):
    name = "cpp_run_tests"
    _REPORT = REPORT
    _UBSAN = "ubsan"
    _ASAN = "asan"
    _TSAN = "tsan"
    _FILES = [_REPORT, _UBSAN, _ASAN, _TSAN]

    class Args(Catch2Args):
        tests: list[str]
        no_detect_leaks: bool

    @staticmethod
    def _get_sanitizers_env(args: Args, path: Path) -> dict[str, str]:
        asan_opts = f"log_path={path / CppRunTestsPlugin._ASAN},color=always"
        if args.no_detect_leaks:
            asan_opts += ",detect_leaks=0"
        return {
            "UBSAN_OPTIONS": f"log_path={path / CppRunTestsPlugin._UBSAN},color=always,print_stacktrace=1",
            "ASAN_OPTIONS": asan_opts,
            "TSAN_OPTIONS": f"log_path={path / CppRunTestsPlugin._TSAN},color=always",
        }

    @staticmethod
    def _run_tests(
        args: Args, tmp_dir: Path, build_dir: Path, target: str, verbose: bool
    ) -> None:
        run_catch2(
            args,
            tmp_dir,
            build_dir,
            target,
            env_additional=CppRunTestsPlugin._get_sanitizers_env(args, tmp_dir),
            log_patterns=[file + "*" for file in CppRunTestsPlugin._FILES],
            verbose=verbose,
        )

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        targets = args.tests[::2]
        build_types = args.tests[1::2]
        if len(targets) != len(build_types):
            raise PluginExecutionFailed(
                "Wrong task config (len(targets) != len(build_types))"
            )

        if not targets:
            raise PluginExecutionFailed("No targets")

        for target, build_type in zip(targets, build_types):
            print_info(f"Running {target} ({build_type})...", color="orange")
            build_dir = args.root / f"build-{build_type.lower()}"
            with tempfile.TemporaryDirectory() as tmp_dir:
                CppRunTestsPlugin._run_tests(
                    args=args,
                    tmp_dir=Path(tmp_dir),
                    build_dir=build_dir,
                    target=target,
                    verbose=verbose,
                )
        return PluginOutput(output="Tests are passed")
