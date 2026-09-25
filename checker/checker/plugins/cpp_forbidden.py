from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import DEVNULL, run

from pydantic import Field

from checker.exceptions import PluginExecutionFailed
from checker.plugins.cpp.blacklist import get_cpp_blacklist
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


@dataclass(frozen = True)
class CompilerPaths:
    resource_dir: str
    system_include_dirs: list[str]


def query_compiler(compiler: Path = Path("clang++")) -> CompilerPaths:
    resource_dir = (
        run([compiler, "-print-resource-dir"], stdin=DEVNULL, capture_output=True, check=True)
        .stdout
        .decode()
        .strip()
    )

    # It might look like a joke, but this is more or less canonical way to extract
    # system include paths
    # https://github.com/llvm/llvm-project/blob/5808b2d513d1baa3355d078193006ab9384a4ee3/clang-tools-extra/clangd/SystemIncludeExtractor.cpp?plain=1#L8
    raw = (
        run(
            [compiler, "-E", "-v", "-x", "c++", "-"],
            stdin=DEVNULL,
            capture_output=True,
            check=True,
        )
        .stderr
        .decode()
    )

    START_LINE = "#include <...> search starts here:"
    END_LINE = "End of search list."
    system_include_dirs = []
    in_paths = False

    for line in map(str.strip, raw.split('\n')):
        if line == START_LINE:
            in_paths = True
            continue
        if line == END_LINE:
            in_paths = False
            continue
        if in_paths:
            system_include_dirs.append(line)

    return CompilerPaths(
        resource_dir=resource_dir,
        system_include_dirs=system_include_dirs,
    )


class CppForbiddenPlugin(PluginABC):
    name = "cpp_forbidden"

    class Args(PluginABC.Args):
        reference_root: Path
        build_dir: Path = Path("build")
        task_path: Path
        allow_change: list[str]
        white_list: list[str]
        forbidden: list[str] = Field(default_factory=list)
        forbidden_files: list[str] = Field(default_factory=list)
        query_compiler: bool = False
        forbidden_checker: str

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        files: list[str] = []
        for r in args.allow_change:
            if r in args.white_list:
                continue
            files += list(map(str, args.task_path.glob(r)))
        files = list(set(files))

        forbidden: list[str] = []
        # Workaround for firejail limit of 128 cli arguments.
        # Some problems have ~50 forbidden features,
        # which results in ~100 cli arguments from forbidden
        # features list alone if passed separately.
        if args.forbidden:
            forbidden += ["-f", ';'.join(args.forbidden)]
        if args.forbidden_files:
            forbidden += ["-ff", ';'.join(args.forbidden_files)]

        extra_args_before: list[str] = []
        if args.query_compiler:
            paths = query_compiler()
            extra_args_before.append(f"-resource-dir={paths.resource_dir}")
            for dir in paths.system_include_dirs:
                extra_args_before.extend(("-isystem", dir))

        checker_args = forbidden + files
        if not checker_args:
            raise PluginExecutionFailed("No arguments for the checker")

        run_args = SafeRunScriptPlugin.Args(
            origin=str(args.reference_root / args.build_dir),
            script=[
                args.forbidden_checker,
                "-p",
                ".",
                *checker_args,
                *map("--extra-arg-before={}".format, extra_args_before),
            ],
            paths_whitelist=[str(args.reference_root)],
            paths_blacklist=get_cpp_blacklist(args.reference_root),
        )
        output = SafeRunScriptPlugin()._run(run_args, verbose=verbose).output
        print_info(output)
        return PluginOutput(output="[No issues]")
