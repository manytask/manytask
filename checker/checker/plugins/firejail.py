from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from checker.exceptions import PluginExecutionFailed

from .base import PluginOutput
from .scripts import PluginABC, RunScriptPlugin

HOME_PATH = str(Path.home())


class SafeRunScriptPlugin(PluginABC):
    """Wrapper over RunScriptPlugin to run students scripts safety.
    Plugin uses Firejail tool to create sandbox for the running process.
    It allows hide environment variables and control access to network and file system.
    If `allow_fallback=True` then if Firejail is not installed, it will fallback to RunScriptPlugin.
    """

    name = "safe_run_script"

    class Args(PluginABC.Args):
        origin: str
        script: Union[str, list[str]]  # as pydantic does not support | in older python versions
        timeout: Union[float, None] = None  # as pydantic does not support | in older python versions
        input: Optional[Path] = None

        env_additional: dict[str, str] = dict()
        env_whitelist: list[str] = list()
        paths_whitelist: list[str] = list()
        lock_network: bool = True
        allow_fallback: bool = False
        paths_blacklist: list[str] = list()

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]  # noqa: C901, PLR0912, PLR0915
        import subprocess

        # test if firejail script is available
        # TODO: test fallback
        result = subprocess.run(["firejail", "--version"], capture_output=True)
        if result.returncode != 0:
            if args.allow_fallback:
                # fallback to RunScriptPlugin
                run_args = RunScriptPlugin.Args(
                    origin=args.origin,
                    script=args.script,
                    timeout=args.timeout,
                    env_additional=args.env_additional,
                    env_whitelist=args.env_whitelist,
                )
                output = RunScriptPlugin()._run(args=run_args, verbose=verbose)
                if verbose:
                    output.output = f"Firejail is not installed. Fallback to RunScriptPlugin.\n{output.output}"
                return output
            else:
                # error
                raise PluginExecutionFailed("Firejail is not installed", output=result.stderr.decode("utf-8"))

        # Construct firejail command
        command: list[str] = ["firejail", "--quiet", "--noprofile", "--deterministic-exit-code"]

        # lock network access
        if args.lock_network:
            command.append("--net=none")

        # Collect all allow paths
        allow_paths = {*args.paths_whitelist, args.origin}
        # a bit tricky but if paths is only /tmp add ~/tmp instead of it
        if "/tmp" in allow_paths and len(allow_paths) == 1:
            allow_paths.add("~/tmp")
        # remove /tmp from paths as it causes error inside Firejail
        if "/tmp" in allow_paths:
            allow_paths.remove("/tmp")
        # replace ~ by the full home path
        for path in allow_paths:
            full_path = path if not path.startswith("~") else HOME_PATH + path[1:]
            # allow access to origin dir
            command.append(f"--whitelist={full_path}")

        for path in args.paths_blacklist:
            full_path = path if not path.startswith("~") else HOME_PATH + path[1:]
            command.append(f"--blacklist={full_path}")

        # Hide all environment variables except allowed
        command += ["env", "-i"]
        env: dict[str, str] = {}
        for e in args.env_whitelist:
            env[e] = os.environ.get(e, "")
        env.update(args.env_additional)
        for e, v in env.items():
            command.append(f"{e}={v}")

        # create actual command
        if isinstance(args.script, str):
            command.append(args.script)
        elif isinstance(args.script, list):
            command += args.script
        else:
            assert False, "Now Reachable"

        # Will use RunScriptPlugin to run Firejail+command
        run_args = RunScriptPlugin.Args(
            origin=args.origin,
            script=command,
            timeout=args.timeout,
            env_additional={},
            env_whitelist=None,
            input=args.input,
        )
        return RunScriptPlugin()._run(args=run_args, verbose=verbose)
