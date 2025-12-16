from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from checker.exceptions import PluginExecutionFailed

from .base import PluginABC, PluginOutput


class RunScriptPlugin(PluginABC):
    """Plugin for running scripts."""

    name = "run_script"

    class Args(PluginABC.Args):
        origin: str
        script: Union[str, list[str]]  # as pydantic does not support | in older python versions
        timeout: Union[float, None] = None  # as pydantic does not support | in older python versions
        env_additional: dict[str, str] = dict()
        env_whitelist: Optional[list[str]] = None
        input: Optional[Path] = None

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        import subprocess

        def set_up_env_sandbox() -> None:  # pragma: nocover
            import os

            if args.env_whitelist is not None:
                env = os.environ.copy()
                os.environ.clear()
                for variable in args.env_whitelist:
                    os.environ[variable] = env.get(variable, "")
            os.environ.update(args.env_additional)

        stdin = open(args.input, "r") if args.input else None

        try:
            result = subprocess.run(
                args.script,
                shell=isinstance(args.script, str),
                cwd=args.origin,
                timeout=args.timeout,  # kill process after timeout, raise TimeoutExpired
                check=True,  # raise CalledProcessError if return code is non-zero
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr & stdout to single output
                preexec_fn=set_up_env_sandbox,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            output = e.output or ""
            output = output if isinstance(output, str) else output.decode("utf-8")

            if isinstance(e, subprocess.TimeoutExpired):
                raise PluginExecutionFailed(
                    f"Script timed out after {e.timeout}s ({args.timeout}s limit)",
                    output=output,
                ) from e
            else:
                raise PluginExecutionFailed(
                    f"Script failed with exit code {e.returncode}",
                    output=output,
                ) from e
        finally:
            if stdin is not None:
                stdin.close()

        return PluginOutput(
            output=result.stdout.decode("utf-8"),
        )
