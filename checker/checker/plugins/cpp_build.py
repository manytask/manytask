from __future__ import annotations

from pathlib import Path
from typing import Optional

from checker.exceptions import PluginExecutionFailed
from checker.plugins.cpp.blacklist import get_cpp_blacklist
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppBuildPlugin(PluginABC):
    name = "cpp_build"

    class Args(PluginABC.Args):
        root: Path
        tests: list[str]
        benchmark: Optional[str] = None

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        targets = args.tests[::2]
        build_types = args.tests[1::2]
        if len(targets) != len(build_types):
            raise PluginExecutionFailed("Wrong task config (len(targets) != len(build_types))")

        if args.benchmark is not None:
            targets.append(args.benchmark)
            build_types.append("RelWithDebInfo")

        if not targets:
            raise PluginExecutionFailed("No targets")

        for target, build_type in zip(targets, build_types):
            build_dir = args.root / f"build-{build_type.lower()}"
            print_info(f"Building {target} ({build_type})...", color="orange")
            run_args = SafeRunScriptPlugin.Args(
                origin=str(build_dir),
                script=["ninja", "-v", target],
                env_whitelist=["PATH"],
                env_additional={"CLICOLOR_FORCE": "1"},
                paths_whitelist=[str(args.root)],
                paths_blacklist=get_cpp_blacklist(args.root),
            )
            output = SafeRunScriptPlugin()._run(run_args, verbose=verbose).output
            print_info(output)
        return PluginOutput(output="Build is finished")
