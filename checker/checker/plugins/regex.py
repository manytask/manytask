from __future__ import annotations

from checker.exceptions import PluginExecutionFailed

from .base import PluginABC, PluginOutput


class CheckRegexpsPlugin(PluginABC):
    """Plugin for checking forbidden regexps in a files."""

    name = "check_regexps"

    class Args(PluginABC.Args):
        origin: str
        patterns: list[str]
        regexps: list[str]
        # TODO: Add validation for patterns and regexps

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        # TODO: add verbose output with files list
        import re
        from pathlib import Path

        # TODO: move to Args validation
        if not Path(args.origin).exists():
            raise PluginExecutionFailed(
                f"Origin '{args.origin}' does not exist",
                output=f"Origin {args.origin} does not exist",
            )

        for pattern in args.patterns:
            for file in Path(args.origin).glob(pattern):
                if file.is_file():
                    with file.open() as f:
                        file_content = f.read()

                    for regexp in args.regexps:
                        if re.search(regexp, file_content, re.MULTILINE):
                            raise PluginExecutionFailed(
                                f"File '{file.name}' matches regexp '{regexp}'",
                                output=f"File '{file}' matches regexp '{regexp}'",
                            )
        return PluginOutput(
            output="No forbidden regexps found",
        )
