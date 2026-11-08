from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pydantic import Field

from checker.plugins.base import PluginABC
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

REPORT = "report.txt"
REPORT_XML = "report.xml"


class Catch2Args(PluginABC.Args):
    """Execution settings shared by Catch2 tests and benchmarks."""

    root: Path
    timeout: float
    args: list[str]
    paths_whitelist: list[str] = Field(default_factory=list)
    lock_network: bool = True


def run_catch2(
    args: Catch2Args,
    report_dir: Path,
    build_dir: Path,
    target: str,
    *,
    xml_report: bool = False,
    env_additional: dict[str, str] | None = None,
    log_patterns: Sequence[str] = (REPORT,),
    verbose: bool = False,
) -> None:
    """Run a Catch2 binary in the sandbox and print reports even on failure."""
    reporters = ["-r", f"console::out={report_dir / REPORT}::colour-mode=ansi"]
    if xml_report:
        reporters = ["-r", f"xml::out={report_dir / REPORT_XML}", *reporters]

    run_args = SafeRunScriptPlugin.Args(
        origin=str(build_dir),
        script=[str(build_dir / target), *reporters, *args.args],
        timeout=args.timeout,
        env_additional=env_additional or {},
        paths_whitelist=[str(args.root / path) for path in args.paths_whitelist],
        lock_network=args.lock_network,
    )
    try:
        SafeRunScriptPlugin()._run(run_args, verbose=verbose)
    finally:
        for pattern in log_patterns:
            for path in report_dir.glob(pattern):
                print_info(path.read_text())
