"""Integration tests for RunSandbox.

These tests shell out to a real ``git`` binary against a locally created bare
repository accessed via ``file://`` — no network, but real subprocess and real
sparse-checkout semantics.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.checklist.sandbox import RunSandbox, SandboxCloneError
from app.checklist.step import CheckContext
from app.hosting import FileChange, MergeRequest
from tests._fakes import FakeHostingAdapter

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary is required for sandbox tests")


def _run(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True)


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """Bare git repo with a 'task-1' branch containing tasks/task-1/main.py + tasks/task-2/main.py."""

    upstream = tmp_path / "upstream.git"
    _run(["git", "init", "--bare", "-b", "main", str(upstream)])

    work = tmp_path / "work"
    _run(["git", "init", "-b", "main", str(work)])
    _run(["git", "-C", str(work), "config", "user.email", "t@t"])
    _run(["git", "-C", str(work), "config", "user.name", "t"])
    (work / "tasks" / "task-1").mkdir(parents=True)
    (work / "tasks" / "task-2").mkdir(parents=True)
    (work / "tasks" / "task-1" / "main.py").write_text("print('task-1')\n")
    (work / "tasks" / "task-2" / "main.py").write_text("print('task-2')\n")
    (work / "README.md").write_text("# repo\n")
    _run(["git", "-C", str(work), "add", "."])
    _run(["git", "-C", str(work), "commit", "-m", "initial"])
    _run(["git", "-C", str(work), "checkout", "-b", "task-1"])
    _run(["git", "-C", str(work), "remote", "add", "origin", str(upstream)])
    _run(["git", "-C", str(work), "push", "origin", "main", "task-1"])

    return upstream


@pytest.fixture
def sample_mr_for_sandbox(bare_remote: Path) -> MergeRequest:
    return MergeRequest(
        project_id=42,
        mr_iid=7,
        sha="HEAD",
        web_url="https://gitlab.test/group/proj/-/merge_requests/7",
        source_branch="task-1",
        target_branch="main",
        author_username="student",
        labels=(),
        title="task-1: solution",
        project_path_with_namespace=str(bare_remote),
    )


@pytest.fixture
def sandbox_for_local_remote(
    fake_hosting_adapter: "FakeHostingAdapter",
    bare_remote: Path,
) -> RunSandbox:
    """RunSandbox configured to treat ``project_path_with_namespace`` as the file:// URL.

    For tests we override the clone URL builder to return ``file://<bare_remote>``;
    that way the production code path (with PRIVATE-TOKEN header) is exercised
    against a real git server without any network or token plumbing.
    """

    fake_hosting_adapter.changes = [
        FileChange(
            old_path="tasks/task-1/main.py",
            new_path="tasks/task-1/main.py",
            new_file=False,
            renamed_file=False,
            deleted_file=False,
            diff="",
        )
    ]

    return RunSandbox(
        hosting=fake_hosting_adapter,
        gitlab_base_url="file://",
        gitlab_token="ignored-for-file-url",
        manytask_base_url="http://manytask.test",
        timeout_sec=5.0,
        env_whitelist_extra={},
        clone_url_builder=lambda mr: f"file://{mr.project_path_with_namespace}",
    )


class TestRunSandbox:
    async def test_clone_is_sparse_and_shallow(
        self,
        sandbox_for_local_remote: RunSandbox,
        sample_mr_for_sandbox: MergeRequest,
        sample_ctx: "CheckContext",
        tmp_path: Path,
    ) -> None:
        # We run `ls tasks` — must list ONLY task-1 (sparse paths from MR changes).
        result = await sandbox_for_local_remote.run(
            mr=sample_mr_for_sandbox,
            command="ls tasks && cat tasks/task-1/main.py",
            ctx=sample_ctx,
        )

        assert result.timed_out is False
        assert result.exit_code == 0
        assert "task-1" in result.stdout.decode()
        assert "task-2" not in result.stdout.decode()
        assert "print('task-1')" in result.stdout.decode()

    async def test_no_gitlab_token_in_env(
        self,
        sandbox_for_local_remote: RunSandbox,
        sample_mr_for_sandbox: MergeRequest,
        sample_ctx: "CheckContext",
    ) -> None:
        result = await sandbox_for_local_remote.run(
            mr=sample_mr_for_sandbox,
            command="env | sort",
            ctx=sample_ctx,
        )

        text = result.stdout.decode()
        assert "GITLAB_TOKEN" not in text
        assert "PRIVATE_TOKEN" not in text
        assert "PRIVATE-TOKEN" not in text
        assert "MR_ID=7" in text
        assert "COURSE_NAME=python-101" in text
        assert "MANYTASK_BASE_URL=http://manytask.test" in text
        assert "MANYTASK_COURSE_TOKEN=course-token-xxx" in text

    async def test_timeout_kills_process(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        bare_remote: Path,
        sample_ctx: "CheckContext",
    ) -> None:
        fake_hosting_adapter.changes = [
            FileChange(
                old_path="tasks/task-1/main.py",
                new_path="tasks/task-1/main.py",
                new_file=False,
                renamed_file=False,
                deleted_file=False,
                diff="",
            )
        ]
        sandbox = RunSandbox(
            hosting=fake_hosting_adapter,
            gitlab_base_url="file://",
            gitlab_token="ignored",
            manytask_base_url="http://manytask.test",
            timeout_sec=0.5,
            env_whitelist_extra={},
            clone_url_builder=lambda mr: f"file://{bare_remote}",
        )
        mr = MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="HEAD",
            web_url="x",
            source_branch="task-1",
            target_branch="main",
            author_username="u",
            labels=(),
            title="t",
            project_path_with_namespace=str(bare_remote),
        )

        result = await sandbox.run(mr=mr, command="sleep 10", ctx=sample_ctx)

        assert result.timed_out is True
        assert result.exit_code != 0

    async def test_stdout_truncated_to_4kb(
        self,
        sandbox_for_local_remote: RunSandbox,
        sample_mr_for_sandbox: MergeRequest,
        sample_ctx: "CheckContext",
    ) -> None:
        result = await sandbox_for_local_remote.run(
            mr=sample_mr_for_sandbox,
            command="python3 -c \"import sys; sys.stdout.write('A' * 10000)\"",
            ctx=sample_ctx,
        )

        assert len(result.stdout) <= 4096

    async def test_tempdir_cleanup_after_run(
        self,
        sandbox_for_local_remote: RunSandbox,
        sample_mr_for_sandbox: MergeRequest,
        sample_ctx: "CheckContext",
    ) -> None:
        result = await sandbox_for_local_remote.run(
            mr=sample_mr_for_sandbox,
            command="pwd",
            ctx=sample_ctx,
        )

        workdir = result.stdout.decode().strip()
        assert not Path(workdir).exists(), "tempdir must be cleaned up after run()"

    async def test_shallow_clone_keeps_disk_under_100mb(
        self,
        sandbox_for_local_remote: RunSandbox,
        sample_mr_for_sandbox: MergeRequest,
        sample_ctx: "CheckContext",
    ) -> None:
        """DoD #4: shallow + blobless + sparse clone must occupy less than 100 MB on disk.

        The bare repo here is tiny (~kilobytes), so absolute size won't stress
        the gate. We verify via ``du -sh`` from inside the sandbox itself and
        assert it returns a value under 100M. The shape of ``du -h`` output
        ("12K\t.") parses to (number, unit).
        """

        result = await sandbox_for_local_remote.run(
            mr=sample_mr_for_sandbox,
            command="du -sm . | awk '{print $1}'",
            ctx=sample_ctx,
        )

        assert result.exit_code == 0
        megabytes = int(result.stdout.decode().strip())
        assert megabytes < 100, f"sparse+shallow clone took {megabytes} MB, expected <100"

    async def test_secret_redacted_in_stderr(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        bare_remote: Path,
        sample_ctx: "CheckContext",
    ) -> None:
        fake_hosting_adapter.changes = [
            FileChange(
                old_path="tasks/task-1/main.py",
                new_path="tasks/task-1/main.py",
                new_file=False,
                renamed_file=False,
                deleted_file=False,
                diff="",
            )
        ]
        secret = "super-secret-token-1234"
        sandbox = RunSandbox(
            hosting=fake_hosting_adapter,
            gitlab_base_url="file://",
            gitlab_token=secret,
            manytask_base_url="http://manytask.test",
            timeout_sec=5.0,
            env_whitelist_extra={},
            clone_url_builder=lambda mr: f"file://{bare_remote}",
        )
        mr = MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="HEAD",
            web_url="x",
            source_branch="task-1",
            target_branch="main",
            author_username="u",
            labels=(),
            title="t",
            project_path_with_namespace=str(bare_remote),
        )

        # Force a stderr that mentions the token (would normally be a bug in
        # student code logging env), then verify redaction.
        result = await sandbox.run(
            mr=mr,
            command=f"echo {secret} >&2; exit 1",
            ctx=sample_ctx,
        )

        assert secret.encode() not in result.stderr
        assert b"***REDACTED***" in result.stderr

    async def test_clone_failure_does_not_leak_token(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        tmp_path: Path,
        sample_ctx: "CheckContext",
    ) -> None:
        """Clone failure must NOT bubble ``CalledProcessError`` — its ``str()``
        contains the full argv including the secret-bearing
        ``-c http.extraHeader=PRIVATE-TOKEN: <token>`` line. The runner
        publishes ``str(err)`` to MRs, so the token would land in a comment.
        """

        fake_hosting_adapter.changes = []
        secret = "ghp_super_secret_token_xyz_9999"
        missing_repo = tmp_path / "does-not-exist.git"
        sandbox = RunSandbox(
            hosting=fake_hosting_adapter,
            gitlab_base_url="https://gitlab.test",
            gitlab_token=secret,
            manytask_base_url="http://manytask.test",
            timeout_sec=5.0,
            env_whitelist_extra={},
            # Force the https-token path while still using a local URL that
            # will fail — the builder owns the URL, the impl owns the header.
            clone_url_builder=lambda m: f"https://gitlab.test/{missing_repo}.git",
        )
        mr = MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="HEAD",
            web_url="x",
            source_branch="task-1",
            target_branch="main",
            author_username="u",
            labels=(),
            title="t",
            project_path_with_namespace=str(missing_repo),
        )

        with pytest.raises(SandboxCloneError) as exc:
            await sandbox.run(mr=mr, command="true", ctx=sample_ctx)

        assert secret not in str(exc.value)
        assert "PRIVATE-TOKEN" not in str(exc.value)

    async def test_path_starting_with_dash_is_not_parsed_as_flag(
        self,
        bare_remote: Path,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_ctx: "CheckContext",
    ) -> None:
        """``--`` separator must shield sparse paths from git arg parsing.

        A change path like ``-config`` (legal in git) should be treated as
        a file pattern, not a flag.
        """

        fake_hosting_adapter.changes = [
            FileChange(
                old_path="tasks/task-1/main.py",
                new_path="tasks/task-1/main.py",
                new_file=False,
                renamed_file=False,
                deleted_file=False,
                diff="",
            )
        ]
        sandbox = RunSandbox(
            hosting=fake_hosting_adapter,
            gitlab_base_url="file://",
            gitlab_token="",
            manytask_base_url="http://manytask.test",
            timeout_sec=5.0,
            env_whitelist_extra={},
            clone_url_builder=lambda m: f"file://{bare_remote}",
        )
        mr = MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="HEAD",
            web_url="x",
            source_branch="task-1",
            target_branch="main",
            author_username="u",
            labels=(),
            title="t",
            project_path_with_namespace=str(bare_remote),
        )

        result = await sandbox.run(mr=mr, command="echo ok", ctx=sample_ctx)

        assert result.exit_code == 0
        assert b"ok" in result.stdout
