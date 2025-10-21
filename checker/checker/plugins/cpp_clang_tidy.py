from __future__ import annotations

from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.cpp.blacklist import get_cpp_blacklist
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppClangTidyPlugin(PluginABC):
    name = "cpp_clang_tidy"

    class Args(PluginABC.Args):
        reference_root: Path
        task_path: Path
        lint_patterns: list[str]

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        lint_files = []
        for f in args.lint_patterns:
            lint_files += list(map(str, args.task_path.glob(f)))
        lint_files = list(set(lint_files))

        if not lint_files:
            raise PluginExecutionFailed("No files")

        run_args = SafeRunScriptPlugin.Args(
            origin=str(args.reference_root / "build-asan"),
            script=["clang-tidy-19", "-p", ".", "--use-color", "--quiet", *lint_files],
            paths_whitelist=[str(args.reference_root)],
            paths_blacklist=get_cpp_blacklist(args.reference_root),
        )
        output = SafeRunScriptPlugin()._run(run_args, verbose=verbose).output
        print_info(output)
        return PluginOutput(output="[No issues]")
