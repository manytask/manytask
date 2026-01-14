from __future__ import annotations

import os
import shutil
from pathlib import Path

from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CopyFilesPlugin(PluginABC):
    name = "copy_files"

    class Args(PluginABC.Args):
        source_dir: Path
        target_dir: Path
        patterns: list[str]
        ignore_patterns: list[str]

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        CopyFilesPlugin._copy_files(
            source=args.source_dir,
            target=args.target_dir,
            patterns=args.patterns,
            ignore_patterns=args.ignore_patterns,
            verbose=True,
        )
        return PluginOutput(output="Files have been copied")

    @staticmethod
    def _copy_files(
        source: Path, target: Path, patterns: list[str], ignore_patterns: list[str], verbose: bool = False
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)
        ignore_entries: list[Path] = sum([list(source.glob(ignore_pattern)) for ignore_pattern in ignore_patterns], [])
        for pattern in patterns:
            for entry in source.glob(pattern):
                if entry not in ignore_entries:
                    CopyFilesPlugin._copy_entry(
                        entry=entry,
                        source=source,
                        target=target,
                        patterns=patterns,
                        ignore_patterns=ignore_patterns,
                        verbose=verbose,
                    )

    @staticmethod
    def _copy_entry(
        entry: Path, source: Path, target: Path, patterns: list[str], ignore_patterns: list[str], verbose: bool = False
    ) -> None:
        relative_path = entry.relative_to(source)
        source_path = source / relative_path
        target_path = target / relative_path
        if entry.is_dir():
            CopyFilesPlugin._copy_files(
                source=source_path,
                target=target_path,
                patterns=patterns,
                ignore_patterns=ignore_patterns,
                verbose=verbose,
            )
            return
        if verbose:
            print_info(f"Copy {source_path}\n  to {target_path}")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        if source_path != target_path:
            shutil.copyfile(source_path, target_path)
