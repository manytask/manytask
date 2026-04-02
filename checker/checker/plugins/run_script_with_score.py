from __future__ import annotations

import re
from typing import Optional, Union

from pydantic import Field

from checker.exceptions import PluginExecutionFailed
from checker.plugins import PluginABC, PluginOutput
from checker.plugins.scripts import RunScriptPlugin


class RunScriptWithScorePlugin(RunScriptPlugin):
    """Plugin for running a custom script that reports a score.

    The script must print a single number in **[0.0, 1.0]** to stdout.
    That number is used directly as ``PluginOutput.percentage``.

    The score line is identified by the ``score_pattern`` regex (default:
    the *last* bare number found anywhere in the output).  If
    ``report_score`` is ``False`` (the default) the plugin behaves exactly
    like :class:`RunScriptPlugin` and the percentage stays at ``1.0``.

    Example script output (all accepted by the default pattern)::

        0.75
        0.5
        score: 1.0

    Configuration example::

        - name: run_script_with_score
          args:
            origin: .
            script: bash grade.sh
            report_score: true
            allow_failures: false
    """

    name = "run_script_with_score"

    class Args(PluginABC.Args):
        origin: str
        script: Union[str, list[str]]
        timeout: Union[float, None] = None
        env_additional: dict[str, str] = Field(default_factory=dict)
        env_whitelist: Optional[list[str]] = None

        # Score-specific fields
        report_score: bool = Field(default=False, description="If True, parse the script output for a score in [0, 1]")
        allow_failures: bool = Field(
            default=False,
            description="If True, a non-zero exit code is not treated as a failure (score may still be 0)",
        )
        score_pattern: str = Field(
            default=r"(?:^|[^\d.])(\d+(?:\.\d+)?)(?:[^\d.]|$)",
            description=(
                "Regex with one capture group that matches the score value in the script output. "
                "The *last* match in the output is used. The matched value must be in [0, 1]."
            ),
        )

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        script_cmd: str | list[str] = args.script
        if args.allow_failures or args.report_score:
            # Wrap the entire command so a non-zero exit does not abort the pipeline.
            # We always produce a shell string here so that `|| true` applies to the
            # whole command, not just the last segment (e.g. `echo 50; exit 1 || true`
            # would still exit 1 without the outer grouping).
            if isinstance(script_cmd, str):
                inner = script_cmd
            else:
                import shlex

                inner = " ".join(shlex.quote(part) for part in script_cmd)
            script_cmd = f"( {inner} ) || true"

        run_script_args = RunScriptPlugin.Args(
            origin=args.origin,
            script=script_cmd,
            timeout=args.timeout,
            env_additional=args.env_additional,
            env_whitelist=args.env_whitelist,
        )
        result = super()._run(run_script_args, verbose=verbose)

        if args.report_score:
            result.percentage = self._extract_percentage(result.output, args.score_pattern)

        return result

    @staticmethod
    def _extract_percentage(output: str, pattern: str) -> float:
        """Parse *output* for a score in [0, 1] using *pattern*.

        :param output: raw stdout of the script
        :param pattern: regex with one capture group containing the numeric score
        :returns: float in [0.0, 1.0]
        :raises PluginExecutionFailed: if no score can be found or the value is out of range
        """
        try:
            compiled = re.compile(pattern, re.MULTILINE)
        except re.error as exc:
            raise PluginExecutionFailed(f"Invalid score_pattern regex: {exc}", output=output) from exc

        matches = compiled.findall(output)
        if not matches:
            raise PluginExecutionFailed(
                f"No score found in script output (pattern: {pattern!r})",
                output=output,
            )

        # Use the last match; findall returns strings when there is one group
        raw_score = matches[-1] if isinstance(matches[-1], str) else matches[-1][0]

        try:
            score = float(raw_score)
        except ValueError as exc:
            raise PluginExecutionFailed(
                f"Could not convert matched score {raw_score!r} to float",
                output=output,
            ) from exc

        if not (0.0 <= score <= 1.0):
            raise PluginExecutionFailed(
                f"Score must be in [0, 1], got {score}",
                output=output,
            )

        return score
