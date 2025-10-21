from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppRunBenchmarksPlugin(PluginABC):
    name = "cpp_run_benchmarks"
    _REPORT = "report.txt"
    _REPORT_XML = "report.xml"

    class Args(PluginABC.Args):
        root: Path
        benchmark: str | None
        timeout: float
        args: list[str]
        benchmark_values: list[str]

    @staticmethod
    def _print_logs(path: Path) -> None:
        file_path = path / CppRunBenchmarksPlugin._REPORT
        if file_path.exists():
            with open(file_path, "r") as f:
                print_info(f.read())

    @staticmethod
    def _parse_xml(tree: ET.ElementTree[ET.Element[str]]) -> dict[str, float]:
        bench_results: dict[str, float] = {}
        for results in tree.iter("BenchmarkResults"):
            name = results.get("name")
            if name is None:
                raise RuntimeError("'name' not found")
            mean = results.find("mean")
            if mean is None:
                raise RuntimeError("'mean' not found")
            bench_results[name] = float(mean.get("value", ""))
        return bench_results

    @staticmethod
    def _parse_benchmark_values(args: Args) -> dict[str, float]:
        bv = args.benchmark_values
        error = RuntimeError("Bad benchmark config")
        if len(bv) % 2:
            raise error

        result: dict[str, float] = {}
        for name, value in zip(bv[::2], bv[1::2]):
            result[name] = float(value)

        if 2 * len(result) != len(bv):
            raise error
        return result

    @staticmethod
    def _check_results(args: Args, tree: ET.ElementTree[ET.Element[str]]) -> None:
        results = CppRunBenchmarksPlugin._parse_xml(tree)
        targets = CppRunBenchmarksPlugin._parse_benchmark_values(args)
        if results.keys() != targets.keys():
            raise RuntimeError("Keys are different")

        error_messages = []
        for name, time in results.items():
            time *= 1e-9
            threshold = targets[name]
            if threshold >= 0 and time > threshold:
                error_messages.append(f"{name}: {time:g} > {threshold:g}")
            elif threshold < 0 and time < -threshold:
                error_messages.append(f"{name}: {time:g} < {-threshold:g}")
        if error_messages:
            message = "\n".join(error_messages)
            print_info(message, color="red")
            raise PluginExecutionFailed()

    @staticmethod
    def _run_benchmarks(args: Args, tmp_dir: Path, build_dir: Path, target: str, verbose: bool) -> None:
        xml_path = tmp_dir / CppRunBenchmarksPlugin._REPORT_XML
        run_args = SafeRunScriptPlugin.Args(
            origin=str(build_dir),
            script=[
                str(build_dir / target),
                "-r",
                f"xml::out={xml_path}",
                "-r",
                f"console::out={tmp_dir / CppRunBenchmarksPlugin._REPORT}::colour-mode=ansi",
                *args.args,
            ],
            timeout=args.timeout,
        )
        try:
            SafeRunScriptPlugin()._run(run_args, verbose=verbose)
        finally:
            CppRunBenchmarksPlugin._print_logs(tmp_dir)
        CppRunBenchmarksPlugin._check_results(args, ET.parse(xml_path))

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        if args.benchmark is None:
            raise RuntimeError("Unexpected benchmark name")
        build_type = "RelWithDebInfo"
        print_info(f"Running {args.benchmark} ({build_type})...", color="orange")
        build_dir = args.root / f"build-{build_type.lower()}"
        with tempfile.TemporaryDirectory() as tmp_dir:
            CppRunBenchmarksPlugin._run_benchmarks(
                args=args, tmp_dir=Path(tmp_dir), build_dir=build_dir, target=args.benchmark, verbose=verbose
            )
        return PluginOutput(output="Benchmark is passed")
