"""Sandboxed runner for the ``run:`` checklist step.

Security model:
* Shallow sparse clone — only the files changed in the MR exist on disk.
* No GITLAB_TOKEN in the subprocess env — token leaves the bot process only
  via ``git -c http.extraHeader=...`` and is purged from logged stderr.
* 60s default timeout. Process is killed if it exceeds the limit.
* Non-root execution is enforced by the container's USER directive
  (Dockerfile), not by Python — running ``setuid`` from inside a privileged
  process is unreliable and pulls in unnecessary complexity.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from loguru import logger

from app.checklist.step import CheckContext
from app.hosting import HostingAdapter, MergeRequest

_STDOUT_LIMIT_BYTES: Final = 4096
_REDACTED_MARKER: Final = b"***REDACTED***"
_CLONE_TIMEOUT_SEC: Final = 60.0


class SandboxCloneError(RuntimeError):
    """Raised when the source-branch clone fails.

    Wraps ``subprocess.CalledProcessError`` from ``git clone`` so the
    GITLAB_TOKEN smuggled in ``-c http.extraHeader=…`` never reaches the
    student-visible ``CheckResult.message``. The original error is logged
    by ``RunSandbox._sparse_clone_blocking`` with the token redacted.
    """


@dataclass(frozen=True, slots=True)
class SandboxResult:
    timed_out: bool
    exit_code: int
    stdout: bytes
    stderr: bytes


CloneUrlBuilder = Callable[[MergeRequest], str]


def _default_clone_url_builder(base_url: str) -> CloneUrlBuilder:
    base = base_url.rstrip("/")

    def builder(mr: MergeRequest) -> str:
        if not mr.project_path_with_namespace:
            raise ValueError("MergeRequest.project_path_with_namespace is empty; cannot build clone URL")
        return f"{base}/{mr.project_path_with_namespace}.git"

    return builder


class RunSandbox:
    def __init__(
        self,
        *,
        hosting: HostingAdapter,
        gitlab_base_url: str,
        gitlab_token: str,
        manytask_base_url: str,
        timeout_sec: float,
        env_whitelist_extra: dict[str, str] | None = None,
        clone_url_builder: CloneUrlBuilder | None = None,
    ) -> None:
        self._hosting = hosting
        self._gitlab_base_url = gitlab_base_url
        self._gitlab_token = gitlab_token
        self._manytask_base_url = manytask_base_url
        self._timeout_sec = timeout_sec
        self._env_whitelist_extra = dict(env_whitelist_extra or {})
        self._clone_url_builder = clone_url_builder or _default_clone_url_builder(gitlab_base_url)

    async def run(
        self,
        *,
        mr: MergeRequest,
        command: str,
        ctx: CheckContext,
    ) -> SandboxResult:
        changes = await self._hosting.get_changes(mr)
        sparse_paths = [c.new_path for c in changes if not c.deleted_file and c.new_path]

        loop = asyncio.get_running_loop()
        with tempfile.TemporaryDirectory(prefix="mrr-run-") as workdir_str:
            workdir = Path(workdir_str)
            clone_url = self._clone_url_builder(mr)
            await loop.run_in_executor(
                None,
                self._sparse_clone_blocking,
                clone_url,
                mr.source_branch,
                sparse_paths,
                workdir,
            )

            env = self._build_env(mr=mr, ctx=ctx, workdir=workdir)

            # ``start_new_session=True`` puts ``bash`` and every grandchild
            # into a fresh process group, so we can SIGKILL the whole group on
            # timeout instead of orphaning sleep/curl/etc. children.
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                command,
                cwd=str(workdir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_sec)
            except asyncio.TimeoutError:
                self._kill_process_group(proc)
                try:
                    await proc.wait()
                except Exception:
                    pass
                logger.warning(
                    "run: step timed out after {}s on mr {}!{}",
                    self._timeout_sec,
                    mr.project_path_with_namespace,
                    mr.mr_iid,
                )
                return SandboxResult(timed_out=True, exit_code=-1, stdout=b"", stderr=b"timeout")

            stdout_truncated = self._redact_secrets(stdout_b[:_STDOUT_LIMIT_BYTES])
            stderr_redacted = self._redact_secrets(stderr_b)
            return SandboxResult(
                timed_out=False,
                exit_code=proc.returncode if proc.returncode is not None else -1,
                stdout=stdout_truncated,
                stderr=stderr_redacted,
            )

    @staticmethod
    def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
        if proc.pid is None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    def _sparse_clone_blocking(
        self,
        clone_url: str,
        branch: str,
        sparse_paths: list[str],
        workdir: Path,
    ) -> None:
        extra_header_args: list[str] = []
        # Only attach token header for https URLs; file:// doesn't need (or
        # accept) PRIVATE-TOKEN. This keeps tests using file:// clean.
        if self._gitlab_token and clone_url.startswith("https://"):
            extra_header_args = [
                "-c",
                f"http.extraHeader=PRIVATE-TOKEN: {self._gitlab_token}",
            ]

        clone_cmd = [
            "git",
            *extra_header_args,
            "clone",
            "--depth=1",
            "--filter=blob:none",
            "--sparse",
            "--single-branch",
            "--branch",
            branch,
            clone_url,
            str(workdir),
        ]
        # Log without the token. We must NEVER bubble CalledProcessError
        # up as-is: ``str(err)`` embeds the full argv including the
        # ``-c http.extraHeader=PRIVATE-TOKEN: <secret>`` line, and any
        # outer ``except`` that stringifies it would leak the token into
        # the student-visible MR comment.
        log_cmd = [
            arg.replace(self._gitlab_token, "***REDACTED***") if self._gitlab_token else arg for arg in clone_cmd
        ]
        logger.debug("sparse-clone: {}", " ".join(log_cmd))
        try:
            subprocess.run(clone_cmd, check=True, capture_output=True, timeout=_CLONE_TIMEOUT_SEC)
        except subprocess.CalledProcessError as err:
            stderr = self._redact_secrets(err.stderr or b"").decode(errors="replace").strip()
            logger.error("sparse-clone failed (exit {}): {}", err.returncode, stderr)
            raise SandboxCloneError(f"clone failed (exit {err.returncode})") from None
        except subprocess.TimeoutExpired:
            logger.error("sparse-clone timed out after {}s", _CLONE_TIMEOUT_SEC)
            raise SandboxCloneError("clone timed out") from None

        if sparse_paths:
            # ``--no-cone`` lets us pass exact file paths (not only directory
            # prefixes) as sparse patterns — matches MR ``changes`` granularity.
            # ``--`` guards against paths starting with ``-`` being parsed as
            # git flags.
            try:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(workdir),
                        "sparse-checkout",
                        "set",
                        "--no-cone",
                        "--",
                        *sparse_paths,
                    ],
                    check=True,
                    capture_output=True,
                    timeout=_CLONE_TIMEOUT_SEC,
                )
            except subprocess.CalledProcessError as err:
                stderr = self._redact_secrets(err.stderr or b"").decode(errors="replace").strip()
                logger.error("sparse-checkout failed (exit {}): {}", err.returncode, stderr)
                raise SandboxCloneError(f"sparse-checkout failed (exit {err.returncode})") from None

    def _build_env(
        self,
        *,
        mr: MergeRequest,
        ctx: CheckContext,
        workdir: Path,
    ) -> dict[str, str]:
        env: dict[str, str] = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(workdir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "MR_ID": str(mr.mr_iid),
            "MR_URL": mr.web_url,
            "COURSE_NAME": ctx.course_name,
            "MANYTASK_BASE_URL": self._manytask_base_url,
            "MANYTASK_COURSE_TOKEN": ctx.course_token,
        }
        env.update(self._env_whitelist_extra)
        # Explicit blocklist as defence-in-depth: even if the caller put one of
        # these into env_whitelist_extra, drop them here.
        for blocked in ("GITLAB_TOKEN", "PRIVATE_TOKEN", "PRIVATE-TOKEN"):
            env.pop(blocked, None)
        return env

    def _redact_secrets(self, data: bytes) -> bytes:
        if not data:
            return data
        if not self._gitlab_token:
            return data
        return data.replace(self._gitlab_token.encode(), _REDACTED_MARKER)
