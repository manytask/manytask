from __future__ import annotations

import tempfile
from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppRunTestsPlugin(PluginABC):
    name = "cpp_run_tests"
    _REPORT = "report.txt"
    _UBSAN = "ubsan"
    _ASAN = "asan"
    _TSAN = "tsan"
    _FILES = [_REPORT, _UBSAN, _ASAN, _TSAN]

    class Args(PluginABC.Args):
        root: Path
        tests: list[str]
        timeout: float
        no_detect_leaks: bool
        args: list[str]
        paths_whitelist: list[str]
        lock_network: bool = True

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
    def _print_logs(path: Path) -> None:
        for file in CppRunTestsPlugin._FILES:
            for file_path in path.glob(file + "*"):
                with open(file_path, "r") as f:
                    print_info(f.read())

    @staticmethod
    def _run_tests(args: Args, tmp_dir: Path, build_dir: Path, target: str, verbose: bool) -> None:
        env = CppRunTestsPlugin._get_sanitizers_env(args, tmp_dir)
        paths_whitelist = [str(args.root / p) for p in args.paths_whitelist]
        run_args = SafeRunScriptPlugin.Args(
            origin=str(build_dir),
            script=[
                str(build_dir / target),
                "-r",
                f"console::out={tmp_dir / CppRunTestsPlugin._REPORT}::colour-mode=ansi",
                *args.args,
            ],
            env_additional=env,
            timeout=args.timeout,
            paths_whitelist=paths_whitelist,
            lock_network=args.lock_network,
        )
        try:
            SafeRunScriptPlugin()._run(run_args, verbose=verbose)
        finally:
            CppRunTestsPlugin._print_logs(tmp_dir)

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        targets = args.tests[::2]
        build_types = args.tests[1::2]
        if len(targets) != len(build_types):
            raise PluginExecutionFailed("Wrong task config (len(targets) != len(build_types))")

        if not targets:
            raise PluginExecutionFailed("No targets")

        for target, build_type in zip(targets, build_types):
            print_info(f"Running {target} ({build_type})...", color="orange")
            build_dir = args.root / f"build-{build_type.lower()}"
            with tempfile.TemporaryDirectory() as tmp_dir:
                CppRunTestsPlugin._run_tests(
                    args=args, tmp_dir=Path(tmp_dir), build_dir=build_dir, target=target, verbose=verbose
                )
        return PluginOutput(output="Tests are passed")
